import frappe
from datetime import timedelta
from frappe.utils.user import get_users_with_role

_log = lambda msg: frappe.logger("huge_app").info(msg)


def after_insert(doc, method=None):
    company = doc.company
    if not company:
        frappe.log_error(
            "Project after_insert — Missing Company",
            f"Project {doc.name} has no company set. Cannot create CC or Warehouse."
        )
        return

    abbr         = _get_abbr(company)
    project_name = doc.project_name or doc.name

    cc_name = _create_cost_center(project_name, company, abbr)
    wh_name = _create_site_warehouse(project_name, company, abbr)

    if cc_name:
        frappe.db.set_value("Project", doc.name, "cost_center", cc_name)
        frappe.db.commit()

    _log(f"[after_insert] {doc.name} → CC: {cc_name}, WH: {wh_name}")


def on_update(doc, method=None):
    if doc.flags.ignore_unidome_hooks:
        return
    _unidome_final_design_sla(doc)
    _unidome_cost_reconciliation_gate(doc)
    _unidome_project_stage_material_planning(doc)
    _unidome_execution_completed_invoice(doc)


# ─── Script 7: Final Design SLA ──────────────────────────────────────────────

def _unidome_final_design_sla(doc):
    if doc.status != "Final Design Requested":
        return

    prev_doc = doc.get_doc_before_save()
    if prev_doc and prev_doc.status == "Final Design Requested":
        return

    due_date = _add_business_days(frappe.utils.today(), 7)
    frappe.db.set_value("Project", doc.name, "custom_final_design_due_date", due_date)

    recipients = get_users_with_role("UNIDOME External Designer")
    if recipients:
        frappe.sendmail(
            recipients=recipients,
            subject=f"[UNIDOME] طلب تصميم نهائي – {doc.project_name}",
            message=f"""
<p>تم طلب التصميم النهائي للمشروع: <strong>{doc.project_name}</strong></p>
<p>تاريخ الاستحقاق: <strong>{due_date}</strong></p>
<p>يرجى الالتزام بالموعد المحدد (7 أيام عمل).</p>
""",
        )

    frappe.enqueue(
        "huge_app.custom.project.project._check_final_design_sla_escalation",
        queue="long",
        is_async=True,
        project_name=doc.name,
        due_date=str(due_date),
        job_name=f"final_design_sla_{doc.name}",
        at_front=False,
    )


def _check_final_design_sla_escalation(project_name, due_date):
    current_status = frappe.db.get_value("Project", project_name, "status")
    if current_status != "Final Design Requested":
        return

    if frappe.utils.getdate(frappe.utils.today()) <= frappe.utils.getdate(due_date):
        return

    managers = list(set(
        get_users_with_role("UNIDOME Operations Manager")
        + get_users_with_role("Project Manager")
    ))
    if managers:
        frappe.sendmail(
            recipients=managers,
            subject=f"[UNIDOME] تجاوز SLA التصميم النهائي – {project_name}",
            message=f"<p>المشروع <strong>{project_name}</strong> تجاوز مهلة التصميم النهائي ({due_date}).</p>",
        )


# ─── Script 9: Cost Reconciliation Gate ──────────────────────────────────────

def _unidome_cost_reconciliation_gate(doc):
    status = doc.get("custom_cost_reconciliation_status")
    if not status:
        return

    prev_doc = doc.get_doc_before_save()
    if not prev_doc:
        return
    if prev_doc.get("custom_cost_reconciliation_status") == status:
        return

    if status == "Passed":
        _create_milestone_invoice(doc, 30, "دفعة انطلاق المشروع 30%")
        _unidome_create_material_request(doc)

    elif status == "Failed - Margin":
        frappe.log_error(
            "UNIDOME Cost Reconciliation — Margin Failure",
            f"Project {doc.name}: cost reconciliation failed (margin). Redirect to Opportunity re-pricing."
        )

    elif status == "Failed - Scope Change":
        frappe.log_error(
            "UNIDOME Cost Reconciliation — Scope Change",
            f"Project {doc.name}: cost reconciliation failed (scope change). Redirect to Final Design revision."
        )


# ─── Script 20: UNIDOME Project Workflow → Material Planning creates MR ──────

def _unidome_project_stage_material_planning(doc):
    stage = doc.get("custom_project_stage")
    if stage != "Material Planning":
        return

    prev_doc = doc.get_doc_before_save()
    if not prev_doc:
        return
    if prev_doc.get("custom_project_stage") == "Material Planning":
        return

    _unidome_create_material_request(doc)


# ─── Script 10: Create Material Request from Opportunity BOQ ─────────────────

def _unidome_create_material_request(project_doc):
    opp_name = project_doc.get("custom_opportunity")
    if not opp_name or not frappe.db.exists("Opportunity", opp_name):
        frappe.log_error(
            "UNIDOME Create MR — Missing Opportunity",
            f"Project {project_doc.name} has no linked Opportunity. MR not created."
        )
        return

    existing_mr = frappe.get_all(
        "Material Request",
        filters=[
            ["Material Request Item", "project", "=", project_doc.name],
            ["Material Request", "docstatus", "!=", 2],
        ],
        pluck="name",
        limit=1,
    )
    if existing_mr:
        return

    opp         = frappe.get_doc("Opportunity", opp_name)
    unidome_qty = frappe.utils.flt(opp.get("custom_unidome_qty") or 0)
    item_code   = opp.get("custom_unidome_size")

    if not unidome_qty or not item_code:
        frappe.log_error(
            "UNIDOME Create MR — Missing BOQ Data",
            f"Opportunity {opp_name} has no custom_unidome_qty/custom_unidome_size. MR not created."
        )
        return

    if not frappe.db.exists("Item", item_code):
        frappe.log_error(
            "UNIDOME Create MR — Unknown Item",
            f"Opportunity {opp_name} custom_unidome_size '{item_code}' is not a valid Item. MR not created."
        )
        return

    mr = frappe.new_doc("Material Request")
    mr.material_request_type = "Manufacture"
    mr.company               = project_doc.company
    mr.transaction_date      = frappe.utils.today()
    mr.schedule_date         = frappe.utils.add_days(frappe.utils.today(), 14)

    default_warehouse = f"Stores - {_get_abbr(project_doc.company)}"

    available = _get_bin_qty(item_code, default_warehouse)
    net_qty   = max(0, unidome_qty - available)
    if net_qty > 0:
        mr.append("items", {
            "item_code"    : item_code,
            "qty"          : net_qty,
            "warehouse"    : default_warehouse,
            "schedule_date": mr.schedule_date,
            "project"      : project_doc.name,
        })

    if mr.items:
        mr.flags.ignore_unidome_hooks = True
        mr.insert(ignore_permissions=True)
        _log(f"[MR created] {mr.name} for Project {project_doc.name}")


def _get_bin_qty(item_code, warehouse):
    bin_data = frappe.db.get_value(
        "Bin",
        {"item_code": item_code, "warehouse": warehouse},
        ["actual_qty", "reserved_qty"],
        as_dict=True
    )
    if not bin_data:
        return 0.0
    return max(0, (bin_data.actual_qty or 0) - (bin_data.reserved_qty or 0))


# ─── Script 14: Execution Completed → 30% Invoice ────────────────────────────

def _unidome_execution_completed_invoice(doc):
    if doc.status != "Execution Completed":
        return

    prev_doc = doc.get_doc_before_save()
    if prev_doc and prev_doc.status == "Execution Completed":
        return

    frappe.db.set_value(
        "Project", doc.name,
        "custom_execution_completed_date", frappe.utils.today()
    )

    _create_milestone_invoice(doc, 30, "دفعة التسليم 30%")


# ─── Shared invoice helper ────────────────────────────────────────────────────

def _create_milestone_invoice(project_doc, percentage, description):
    so_name = project_doc.get("sales_order")
    if not so_name or not frappe.db.exists("Sales Order", so_name):
        frappe.log_error(
            f"UNIDOME Invoice ({description}) — Missing SO",
            f"Project {project_doc.name} has no linked Sales Order. Invoice not created."
        )
        return None

    so = frappe.get_doc("Sales Order", so_name)
    if not so.items:
        frappe.log_error(
            f"UNIDOME Invoice ({description}) — No Items",
            f"SO {so_name} has no items. Invoice not created."
        )
        return None

    total      = frappe.utils.flt(so.grand_total) * (percentage / 100.0)
    first_item = so.items[0]

    si = frappe.new_doc("Sales Invoice")
    si.customer           = so.customer
    si.company            = so.company
    si.posting_date       = frappe.utils.today()
    si.currency           = so.currency
    si.conversion_rate    = so.conversion_rate or 1
    si.selling_price_list = so.selling_price_list
    si.remarks = f"{description} | المشروع: {project_doc.project_name} | SO: {so_name}"

    si.append("items", {
        "item_code"     : first_item.item_code,
        "item_name"     : first_item.item_name,
        "description"   : description,
        "qty"           : 1,
        "rate"          : total,
        "uom"           : first_item.uom,
        "income_account": first_item.income_account,
        "cost_center"   : first_item.cost_center,
    })

    si.flags.ignore_unidome_hooks = True
    si.insert(ignore_permissions=True)
    _log(f"[Invoice {percentage}%] {si.name} for Project {project_doc.name}")
    return si.name


# ─── Utilities ────────────────────────────────────────────────────────────────

def _get_abbr(company):
    return frappe.db.get_value("Company", company, "abbr") or ""


def _add_business_days(start_date, num_days):
    current = frappe.utils.getdate(start_date)
    added   = 0
    while added < num_days:
        current += timedelta(days=1)
        if current.weekday() not in (4, 5):  # 4=Fri, 5=Sat (Jordan weekend)
            added += 1
    return current


def _create_cost_center(project_name, company, abbr):
    cc_name = f"{project_name} - {abbr}"
    if frappe.db.exists("Cost Center", cc_name):
        return cc_name

    parent_cc = f"Projects - {abbr}"
    if not frappe.db.exists("Cost Center", parent_cc):
        parent_cc = frappe.db.get_value("Company", company, "cost_center")
        if not parent_cc:
            frappe.log_error(
                "Project after_insert — Missing Parent CC",
                f"Cannot find parent Cost Center for company '{company}'. Create 'Projects - {abbr}' manually."
            )
            return None

    cc = frappe.new_doc("Cost Center")
    cc.cost_center_name   = project_name
    cc.parent_cost_center = parent_cc
    cc.company            = company
    cc.is_group           = 0
    cc.insert(ignore_permissions=True)
    return cc.name


def _create_site_warehouse(project_name, company, abbr):
    wh_name = f"{project_name} - Site - {abbr}"
    if frappe.db.exists("Warehouse", wh_name):
        return wh_name

    parent_wh = f"All Warehouses - {abbr}"
    if not frappe.db.exists("Warehouse", parent_wh):
        frappe.log_error(
            "Project after_insert — Missing Parent Warehouse",
            f"Parent Warehouse 'All Warehouses - {abbr}' not found for company '{company}'."
        )
        return None

    wh = frappe.new_doc("Warehouse")
    wh.warehouse_name   = f"{project_name} - Site"
    wh.parent_warehouse = parent_wh
    wh.company          = company
    wh.warehouse_type   = "Transit"
    wh.insert(ignore_permissions=True)
    return wh.name

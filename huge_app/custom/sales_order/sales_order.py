import frappe

TEMPLATE_NAME = "Unidome Project Template"

UNIDOME_TASKS = [
    "تأهيل الفرصة",
    "التصميم المبدئي",
    "المراجعة الفنية",
    "التسعير والتفاوض",
    "توقيع العقد",
    "التصميم النهائي",
    "اعتماد التصميم",
    "تخطيط الموارد",
    "التصنيع",
    "الشحن",
    "التنفيذ الميداني",
    "الإغلاق والتسليم",
]


def before_submit(doc, method=None):
    if doc.flags.ignore_unidome_hooks:
        return
    _unidome_contract_signed_validation(doc)


def on_submit(doc, method=None):
    if doc.flags.ignore_unidome_hooks:
        return

    already_created = doc.get("custom_project_created") or 0
    if already_created:
        return

    opp_details   = _get_opportunity_details(doc)
    project_name  = _get_project_name_from_so(doc)
    floor_count   = int(doc.get("custom_floor_count") or 1)

    created_project = _create_project_from_template(project_name, doc, opp_details)

    if created_project:
        frappe.db.set_value("Sales Order", doc.name, "custom_project_created", 1)

        additional_floors = []
        if floor_count > 1:
            additional_floors = _create_additional_floors(doc, project_name, floor_count)

        _create_kickoff_invoice(doc)

        frappe.db.commit()
        frappe.logger("huge_app").info(
            f"[SO Submit] {doc.name} → Project: {created_project}. Floors: {additional_floors}"
        )


# ─── Script 5: before_submit — contract signed + quotation validation ─────────

def _unidome_contract_signed_validation(doc):
    opp_name = doc.get("custom_opportunity")
    if not opp_name:
        return

    contract_signed = frappe.db.get_value(
        "Opportunity", opp_name, "custom_contract_signed"
    )
    if not contract_signed:
        frappe.throw(
            "لا يمكن إنشاء Sales Order قبل توقيع العقد وتقديم عرض السعر"
        )

    submitted_qt = frappe.db.get_value(
        "Quotation",
        {"opportunity": opp_name, "docstatus": 1},
        "name"
    )
    if not submitted_qt:
        frappe.throw(
            "لا يمكن إنشاء Sales Order قبل توقيع العقد وتقديم عرض السعر"
        )


# ─── Script 6: on_submit — create Project ────────────────────────────────────

def _get_project_name_from_so(so_doc):
    customer = so_doc.customer or "Unknown"
    return f"{customer} — {so_doc.name} — Floor 1"


def _get_opportunity_details(so_doc):
    opp_name = so_doc.get("custom_opportunity")
    if opp_name and frappe.db.exists("Opportunity", opp_name):
        opp = frappe.get_doc("Opportunity", opp_name)
        return {
            "name"        : opp_name,
            "project_name": opp.get("custom_project_name") or opp.title,
            "area_m2"     : opp.get("custom_total_slab_area") or 0,
        }
    return {}


def _create_project_from_template(project_name, so_doc, opp_details):
    if not frappe.db.exists("Project Template", TEMPLATE_NAME):
        frappe.log_error(
            "SO Submit → Project — Missing Template",
            f"Project Template '{TEMPLATE_NAME}' not found. Falling back to manual task creation."
        )
        return _create_project_with_tasks(project_name, so_doc, opp_details)

    project = frappe.new_doc("Project")
    project.project_name        = project_name
    project.company             = so_doc.company
    project.customer            = so_doc.customer
    project.status              = "Open"
    project.expected_start_date = frappe.utils.today()
    project.sales_order         = so_doc.name
    project.project_template    = TEMPLATE_NAME

    if opp_details.get("name") and hasattr(project, "custom_opportunity"):
        project.custom_opportunity = opp_details["name"]
    if opp_details.get("area_m2") and hasattr(project, "custom_total_area_m2"):
        project.custom_total_area_m2 = opp_details["area_m2"]

    project.insert(ignore_permissions=True)
    return project.name


def _create_project_with_tasks(project_name, so_doc, opp_details):
    project = frappe.new_doc("Project")
    project.project_name        = project_name
    project.company             = so_doc.company
    project.customer            = so_doc.customer
    project.status              = "Open"
    project.expected_start_date = frappe.utils.today()
    project.sales_order         = so_doc.name

    if opp_details.get("name") and hasattr(project, "custom_opportunity"):
        project.custom_opportunity = opp_details["name"]
    if opp_details.get("area_m2") and hasattr(project, "custom_total_area_m2"):
        project.custom_total_area_m2 = opp_details["area_m2"]

    project.insert(ignore_permissions=True)

    for task_name in UNIDOME_TASKS:
        task = frappe.new_doc("Task")
        task.project     = project.name
        task.subject     = task_name
        task.status      = "Open"
        task.insert(ignore_permissions=True)

    return project.name


def _create_additional_floors(so_doc, base_project_name, floor_count):
    created = []
    for floor_num in range(2, floor_count + 1):
        floor_project_name = base_project_name.replace("Floor 1", f"Floor {floor_num}")

        if frappe.db.exists("Project", floor_project_name):
            continue

        floor_project = frappe.new_doc("Project")
        floor_project.project_name  = floor_project_name
        floor_project.company       = so_doc.company
        floor_project.customer      = so_doc.customer
        floor_project.status        = "Open"
        floor_project.sales_order   = so_doc.name
        floor_project.project_template = TEMPLATE_NAME

        if hasattr(floor_project, "custom_floor_number"):
            floor_project.custom_floor_number = floor_num

        floor_project.insert(ignore_permissions=True)
        created.append(floor_project.name)

    return created


def _create_kickoff_invoice(so_doc):
    try:
        so_items = so_doc.items
        if not so_items:
            return None

        first_item = so_items[0]
        total_30pct = frappe.utils.flt(so_doc.grand_total) * 0.30

        si = frappe.new_doc("Sales Invoice")
        si.customer          = so_doc.customer
        si.company           = so_doc.company
        si.posting_date      = frappe.utils.today()
        si.currency          = so_doc.currency
        si.conversion_rate   = so_doc.conversion_rate or 1
        si.selling_price_list = so_doc.selling_price_list
        si.remarks = f"دفعة مقدمة 30% – Kickoff | Sales Order: {so_doc.name}"

        si.append("items", {
            "item_code"     : first_item.item_code,
            "item_name"     : first_item.item_name,
            "description"   : "دفعة مقدمة 30% – Kickoff",
            "qty"           : 1,
            "rate"          : total_30pct,
            "uom"           : first_item.uom,
            "income_account": first_item.income_account,
            "cost_center"   : first_item.cost_center,
        })

        si.flags.ignore_unidome_hooks = True
        si.insert(ignore_permissions=True)

        frappe.logger("huge_app").info(
            f"[Kickoff Invoice] {si.name} created for SO {so_doc.name} (30% = {total_30pct})"
        )
        return si.name

    except Exception as exc:
        frappe.log_error(
            "SO Submit → Kickoff Invoice — Error",
            f"Failed to create kickoff invoice for SO {so_doc.name}: {exc}"
        )
        return None

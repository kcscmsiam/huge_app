import frappe
from frappe.utils.user import get_users_with_role

_log = lambda msg: frappe.logger("huge_app").info(msg)


def on_submit(doc, method=None):
    if doc.flags.ignore_unidome_hooks:
        return
    _unidome_fgqc_gate(doc)


def _unidome_fgqc_gate(doc):
    project    = doc.project or ""
    work_order = doc.work_order or ""

    if doc.result == "Accept":
        so_name = None
        if project:
            so_name = frappe.db.get_value("Project", project, "sales_order")

        if so_name:
            existing_dn = frappe.db.get_value(
                "Delivery Note",
                {"against_sales_order": so_name, "docstatus": ["!=", 2]},
                "name"
            )
            if not existing_dn:
                _create_delivery_note(so_name, project, doc.company)

        if project:
            frappe.db.set_value("Project", project, "status", "Ready for Shipment")

    elif doc.result == "Reject":
        frappe.log_error(
            "UNIDOME FG QC — Non-Conformance",
            f"FG QC Inspection {doc.name} rejected. Defect: {doc.defect_description or 'N/A'}"
        )

        if project:
            qa_managers = get_users_with_role("UNIDOME Quality Inspector")
            factory_managers = get_users_with_role("UNIDOME Factory User")
            recipients = list(set(qa_managers + factory_managers))
            if recipients:
                frappe.sendmail(
                    recipients=recipients,
                    subject=f"[UNIDOME] رفض فحص الجودة – {doc.name}",
                    message=f"""
<p>تم رفض فحص الجودة للمشروع: <strong>{project}</strong></p>
<p>وصف العيب: {doc.defect_description or '—'}</p>
<p>يرجى مراجعة العمل وإعادة الإنتاج.</p>
""",
                )

        if work_order:
            _reopen_work_order(work_order, doc.company)


def _create_delivery_note(so_name, project, company):
    so = frappe.get_doc("Sales Order", so_name)
    dn = frappe.new_doc("Delivery Note")
    dn.customer            = so.customer
    dn.company             = company
    dn.project             = project
    dn.against_sales_order = so_name
    dn.posting_date        = frappe.utils.today()

    for so_item in so.items:
        pending_qty = frappe.utils.flt(so_item.qty) - frappe.utils.flt(so_item.delivered_qty)
        if pending_qty <= 0:
            continue
        dn.append("items", {
            "item_code"             : so_item.item_code,
            "item_name"             : so_item.item_name,
            "description"           : so_item.description,
            "qty"                   : pending_qty,
            "uom"                   : so_item.uom,
            "against_sales_order"   : so_name,
            "so_detail"             : so_item.name,
            "warehouse"             : so_item.warehouse or f"Finished Goods - {_get_abbr(company)}",
        })

    if dn.items:
        dn.flags.ignore_unidome_hooks = True
        dn.insert(ignore_permissions=True)
        _log(f"[FG QC Accept] Delivery Note {dn.name} created for SO {so_name}")


def _reopen_work_order(wo_name, company):
    try:
        wo = frappe.get_doc("Work Order", wo_name)
        new_wo = frappe.new_doc("Work Order")
        new_wo.production_item    = wo.production_item
        new_wo.bom_no             = wo.bom_no
        new_wo.qty                = wo.qty
        new_wo.project            = wo.project
        new_wo.company            = company
        new_wo.planned_start_date = frappe.utils.nowdate()
        new_wo.fg_warehouse       = wo.fg_warehouse
        new_wo.flags.ignore_unidome_hooks = True
        new_wo.insert(ignore_permissions=True)
        new_wo.submit()
        _log(f"[FG QC Reject] New WO {new_wo.name} created to replace rejected WO {wo_name}")
    except Exception as exc:
        frappe.log_error(
            "UNIDOME FG QC Reject — WO Reopen Error",
            f"Failed to reopen WO {wo_name}: {exc}"
        )


def _get_abbr(company):
    return frappe.db.get_value("Company", company, "abbr") or ""

import frappe

SHIELD_ASSEMBLY_BOM_ITEM  = "Shield Assembly"
UNIFIX_ASSEMBLY_ITEM      = "Unifix Assembly"
UNIDOME_PRODUCTION_ITEM   = "Unidome Production"
UNIDOME_MODULE_ITEM       = "4-Unidome Module"

WO_SEQUENCE = [
    SHIELD_ASSEMBLY_BOM_ITEM,
    UNIFIX_ASSEMBLY_ITEM,
    UNIDOME_PRODUCTION_ITEM,
    UNIDOME_MODULE_ITEM,
]

_log = lambda msg: frappe.logger("huge_app").info(msg)


def on_submit(doc, method=None):
    if doc.flags.ignore_unidome_hooks:
        return
    _unidome_work_order_chain(doc)


def _unidome_work_order_chain(doc):
    if doc.status != "Completed":
        return

    production_item = doc.production_item or ""
    project         = doc.project or ""

    try:
        current_idx = WO_SEQUENCE.index(production_item)
    except ValueError:
        return

    next_idx = current_idx + 1
    if next_idx >= len(WO_SEQUENCE):
        if production_item == UNIDOME_MODULE_ITEM:
            _issue_stock_to_finished_goods(doc)
        return

    next_item = WO_SEQUENCE[next_idx]

    existing_next_wo = frappe.db.get_value(
        "Work Order",
        {
            "project"         : project,
            "production_item" : next_item,
            "docstatus"       : ["!=", 2],
        },
        "name"
    )
    if existing_next_wo:
        return

    bom_name = frappe.db.get_value(
        "BOM",
        {"item": next_item, "is_active": 1, "docstatus": 1, "is_default": 1},
        "name"
    )
    if not bom_name:
        bom_name = frappe.db.get_value(
            "BOM",
            {"item": next_item, "is_active": 1, "docstatus": 1},
            "name"
        )

    if not bom_name:
        frappe.log_error(
            "UNIDOME Work Order Chain — Missing BOM",
            f"No active BOM found for {next_item}. WO chain stopped at {doc.name}."
        )
        return

    new_wo = frappe.new_doc("Work Order")
    new_wo.production_item    = next_item
    new_wo.bom_no             = bom_name
    new_wo.qty                = doc.qty
    new_wo.project            = project
    new_wo.company            = doc.company
    new_wo.planned_start_date = frappe.utils.nowdate()

    fg_warehouse = frappe.db.get_value("Company", doc.company, "default_warehouse") or \
                   f"Finished Goods - {_get_abbr(doc.company)}"
    new_wo.fg_warehouse = fg_warehouse

    new_wo.flags.ignore_unidome_hooks = True
    new_wo.insert(ignore_permissions=True)
    new_wo.submit()

    _log(f"[WO Chain] {doc.name} ({production_item}) completed → {new_wo.name} ({next_item}) created.")


def _issue_stock_to_finished_goods(doc):
    fg_warehouse = frappe.db.get_value("Company", doc.company, "default_warehouse") or \
                   f"Finished Goods - {_get_abbr(doc.company)}"

    se = frappe.new_doc("Stock Entry")
    se.stock_entry_type = "Material Transfer"
    se.purpose          = "Material Transfer"
    se.project          = doc.project
    se.company          = doc.company
    se.posting_date     = frappe.utils.today()
    se.remarks          = f"Finished Goods transfer for WO {doc.name}"

    se.append("items", {
        "item_code"     : doc.production_item,
        "qty"           : doc.qty,
        "s_warehouse"   : doc.fg_warehouse,
        "t_warehouse"   : fg_warehouse,
    })

    se.flags.ignore_unidome_hooks = True
    try:
        se.insert(ignore_permissions=True)
        se.submit()
        _log(f"[WO Chain FG] Stock Entry {se.name} → {fg_warehouse}")
    except Exception as exc:
        frappe.log_error(
            "UNIDOME WO Chain — FG Stock Entry Error",
            f"Failed to create FG Stock Entry for WO {doc.name}: {exc}"
        )


def _get_abbr(company):
    return frappe.db.get_value("Company", company, "abbr") or ""

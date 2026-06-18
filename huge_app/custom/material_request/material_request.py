import frappe


def before_save(doc, method=None):
    if (doc.material_request_type or "") != "Manufacture":
        return
    company   = doc.company or "Huge Contracting & Engineering Group"
    warehouse = doc.set_warehouse or get_default_warehouse(company)

    for item_row in doc.items:
        item_code    = item_row.item_code
        qty_required = item_row.qty or 1

        has_bom = frappe.db.exists("BOM", {"item": item_code, "is_active": 1, "docstatus": 1})
        if has_bom:
            result = get_best_bom(item_code, qty_required, warehouse)
            if hasattr(item_row, "custom_recommended_bom"):
                item_row.custom_recommended_bom = result["selected_bom"]
            if hasattr(item_row, "custom_bom_feasible"):
                item_row.custom_bom_feasible = result["feasible"]
            if hasattr(item_row, "custom_bom_note"):
                item_row.custom_bom_note = result["note"]


def get_default_warehouse(company):
    abbr = frappe.db.get_value("Company", company, "abbr") or "HC&EG"
    return f"Stores - {abbr}"

def get_projected_qty(item_code, warehouse):
    bin_data = frappe.db.get_value(
        "Bin",
        {"item_code": item_code, "warehouse": warehouse},
        ["actual_qty", "reserved_qty", "reserved_qty_for_production", "ordered_qty"],
        as_dict=True
    )
    if not bin_data:
        return 0.0
    return (
        (bin_data.actual_qty or 0)
        - (bin_data.reserved_qty or 0)
        - (bin_data.reserved_qty_for_production or 0)
        + (bin_data.ordered_qty or 0)
    )

def get_best_bom(item_code, qty_required, warehouse):
    boms = frappe.get_all(
        "BOM",
        filters={"item": item_code, "is_active": 1, "docstatus": 1},
        fields=["name", "quantity", "is_default"],
        order_by="is_default desc, name asc"
    )
    if not boms:
        return {"selected_bom": None, "feasible": 0, "note": "No active BOM found"}

    fallback_bom = boms[0]["name"]
    for bom in boms:
        bom_qty    = bom["quantity"] or 1
        components = frappe.get_all(
            "BOM Item",
            filters={"parent": bom["name"]},
            fields=["item_code", "qty", "source_warehouse"]
        )
        sufficient = True
        for comp in components:
            required  = (comp.qty / bom_qty) * qty_required
            check_wh  = comp.source_warehouse or warehouse
            projected = get_projected_qty(comp.item_code, check_wh)
            if projected < required:
                sufficient = False
                break

        if sufficient:
            return {"selected_bom": bom["name"], "feasible": 1, "note": "✅ Optimal BOM — sufficient stock"}

    return {"selected_bom": fallback_bom, "feasible": 0, "note": "⚠️ No fully feasible BOM — fallback to default. Check stock."}


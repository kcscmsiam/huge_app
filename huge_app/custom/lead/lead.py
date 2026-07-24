import frappe


def on_update(doc, method=None):
    if doc.flags.ignore_unidome_hooks:
        return
    _unidome_lead_converted(doc)


def _unidome_lead_converted(doc):
    if doc.status != "Converted":
        return

    existing = frappe.db.get_value(
        "Opportunity",
        {"party_name": doc.name, "opportunity_from": "Lead", "docstatus": ["!=", 2]},
        "name"
    )
    if existing:
        return

    opp = frappe.new_doc("Opportunity")
    opp.opportunity_from = "Lead"
    opp.party_name = doc.name
    opp.custom_unidome_opportunity_state = "Needs Analysis"
    opp.status = "Open"

    if doc.get("custom_project_location"):
        opp.custom_project_location = doc.custom_project_location
    if doc.get("custom_project_type"):
        opp.custom_project_type = doc.custom_project_type

    opp.flags.ignore_unidome_hooks = True
    opp.insert(ignore_permissions=True)

    frappe.logger("huge_app").info(
        f"[UNIDOME] Opportunity {opp.name} created from Lead {doc.name}"
    )

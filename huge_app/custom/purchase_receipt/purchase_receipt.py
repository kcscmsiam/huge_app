import frappe


def on_submit(doc, method=None):
    pr_opportunity = doc.get("custom_opportunity")
    if not pr_opportunity:
        return

    if frappe.db.exists("Opportunity", pr_opportunity):
        frappe.db.set_value(
            "Opportunity",
            pr_opportunity,
            "prelim_design_status",
            "Received"
        )
        frappe.db.commit()
        frappe.log_error(
            f"Opportunity {pr_opportunity} prelim_design_status → Received (triggered by PR {doc.name})",
            "PR Submit → Opportunity Update — Success"
        )
    else:
        frappe.log_error(
            f"PR {doc.name} references non-existent Opportunity: {pr_opportunity}",
            "PR Submit → Opportunity Update — Missing Opportunity"
        )


def on_update(doc, method=None):
    current_state = doc.workflow_state or ""
    if current_state != "Approved":
        return

    if doc.get("custom_boq_created"):
        return

    pr_opportunity = doc.get("custom_opportunity")

    if not pr_opportunity:
        frappe.log_error(
            f"PR {doc.name} approved but has no linked Opportunity. BOQ not created.",
            "PR Approved → BOQ — Missing Opportunity"
        )
        return

    if not frappe.db.exists("Opportunity", pr_opportunity):
        frappe.log_error(
            f"PR {doc.name} references non-existent Opportunity: {pr_opportunity}",
            "PR Approved → BOQ — Invalid Opportunity"
        )
        return

    existing_boq = frappe.get_all(
        "Project BOQ",
        filters={"opportunity": pr_opportunity, "docstatus": ("!=", 2)},
        fields=["name"]
    )
    if existing_boq:
        frappe.log_error(
            f"BOQ already exists for Opportunity {pr_opportunity}: {existing_boq[0]['name']}",
            "PR Approved → BOQ — Duplicate Skipped"
        )
        return

    opp = frappe.get_doc("Opportunity", pr_opportunity)

    boq = frappe.new_doc("Project BOQ")
    boq.opportunity      = pr_opportunity
    boq.company          = opp.company
    boq.customer         = opp.party_name
    boq.project_name     = opp.get("custom_project_name") or opp.title
    boq.total_area_m2    = opp.get("total_project_area_m2") or 0
    boq.purchase_receipt = doc.name
    boq.status           = "Draft"
    boq.date             = frappe.utils.today()
    boq.unidome_supplier = opp.company
    boq.steel_supplier   = "Customer"
    boq.concrete_supplier = "Customer"

    boq.insert(ignore_permissions=True)

    frappe.db.set_value("Purchase Receipt", doc.name, "custom_boq_created", 1)
    frappe.db.commit()

    frappe.log_error(
        f"BOQ {boq.name} created for Opportunity {pr_opportunity} from PR {doc.name}",
        "PR Approved → BOQ — Success"
    )

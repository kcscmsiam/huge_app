import frappe

_log = lambda msg: frappe.logger("huge_app").info(msg)


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
        _log(f"[PR Submit] Opportunity {pr_opportunity} prelim_design_status → Received (PR {doc.name})")
    else:
        frappe.log_error(
            "PR Submit → Opportunity Update — Missing Opportunity",
            f"PR {doc.name} references non-existent Opportunity: {pr_opportunity}"
        )


def on_update(doc, method=None):
    current_state = doc.get("review_status") or ""
    if current_state != "Approved":
        return

    if doc.get("custom_boq_created"):
        return

    pr_opportunity = doc.get("custom_opportunity")

    if not pr_opportunity:
        frappe.log_error(
            "PR Approved → BOQ — Missing Opportunity",
            f"PR {doc.name} approved but has no linked Opportunity. BOQ not created."
        )
        return

    if not frappe.db.exists("Opportunity", pr_opportunity):
        frappe.log_error(
            "PR Approved → BOQ — Invalid Opportunity",
            f"PR {doc.name} references non-existent Opportunity: {pr_opportunity}"
        )
        return

    existing_boq = frappe.get_all(
        "Project BOQ",
        filters={"opportunity": pr_opportunity, "docstatus": ("!=", 2)},
        fields=["name"]
    )
    if existing_boq:
        _log(f"[PR Approved] BOQ already exists for Opportunity {pr_opportunity}: {existing_boq[0]['name']}")
        return

    opp = frappe.get_doc("Opportunity", pr_opportunity)
    project = frappe.db.get_value("Project", {"custom_opportunity": pr_opportunity})

    boq = frappe.new_doc("Project BOQ")
    boq.opportunity       = pr_opportunity
    boq.project           = project
    boq.total_slab_area_m2 = frappe.utils.flt(opp.get("custom_total_slab_area"))
    boq.status            = "Draft"
    boq.notes             = f"تم الإنشاء تلقائياً من Purchase Receipt {doc.name}"

    boq.insert(ignore_permissions=True)

    frappe.db.set_value("Purchase Receipt", doc.name, "custom_boq_created", 1)
    frappe.db.commit()

    _log(f"[PR Approved] BOQ {boq.name} created for Opportunity {pr_opportunity} from PR {doc.name}")

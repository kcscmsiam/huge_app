"""
Add custom_project_stage field to Project doctype.
This is the workflow_state_field for UNIDOME Project Workflow.
"""
import frappe


def execute():
    if frappe.db.exists("Custom Field", "Project-custom_project_stage"):
        return

    cf = frappe.new_doc("Custom Field")
    cf.dt           = "Project"
    cf.fieldname    = "custom_project_stage"
    cf.label        = "Project Stage (UNIDOME)"
    cf.fieldtype    = "Data"
    cf.read_only    = 1
    cf.insert_after = "status"
    cf.module       = "UNIDOME"
    cf.insert(ignore_permissions=True)
    frappe.db.commit()

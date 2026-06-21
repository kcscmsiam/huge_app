import frappe


def run(method=None):
    _unidome_d30_retention_invoice()


def _unidome_d30_retention_invoice():
    today = frappe.utils.today()
    target_date = frappe.utils.add_days(today, -30)

    projects = frappe.get_all(
        "Project",
        filters={
            "status"                           : "Execution Completed",
            "custom_execution_completed_date"  : target_date,
        },
        fields=["name", "project_name", "sales_order", "customer", "company"]
    )

    for project in projects:
        _process_retention(project)


def _process_retention(project):
    project_name = project.name
    so_name      = project.sales_order
    company      = project.company

    if not so_name or not frappe.db.exists("Sales Order", so_name):
        frappe.log_error(
            "UNIDOME D+30 Retention — Missing SO",
            f"Project {project_name} has no Sales Order. Retention invoice skipped."
        )
        return

    existing_invoice = frappe.db.get_value(
        "Sales Invoice",
        {
            "remarks": ["like", f"%Retention%{project_name}%"],
            "docstatus": ["!=", 2],
        },
        "name"
    )
    if existing_invoice:
        return

    so = frappe.get_doc("Sales Order", so_name)
    total_10pct = frappe.utils.flt(so.grand_total) * 0.10

    if not so.items:
        return

    first_item = so.items[0]
    si = frappe.new_doc("Sales Invoice")
    si.customer          = so.customer
    si.company           = company
    si.posting_date      = frappe.utils.today()
    si.currency          = so.currency
    si.conversion_rate   = so.conversion_rate or 1
    si.selling_price_list = so.selling_price_list
    si.remarks = f"دفعة الثبات 10% – Retention | المشروع: {project_name}"

    si.append("items", {
        "item_code"     : first_item.item_code,
        "item_name"     : first_item.item_name,
        "description"   : "دفعة الثبات 10% – Retention",
        "qty"           : 1,
        "rate"          : total_10pct,
        "uom"           : first_item.uom,
        "income_account": first_item.income_account,
        "cost_center"   : first_item.cost_center,
    })

    si.flags.ignore_unidome_hooks = True
    si.insert(ignore_permissions=True)

    _create_satisfaction_survey(project, so.customer)
    _create_snag_task(project)

    frappe.logger("huge_app").info(
        f"[D+30 Retention] SI {si.name} created for Project {project_name}"
    )


def _create_satisfaction_survey(project, customer):
    existing = frappe.db.get_value(
        "Customer Satisfaction Survey",
        {"project": project.name, "docstatus": ["!=", 2]},
        "name"
    )
    if existing:
        return

    survey = frappe.new_doc("Customer Satisfaction Survey")
    survey.project     = project.name
    survey.customer    = customer
    survey.survey_date = frappe.utils.today()
    survey.flags.ignore_unidome_hooks = True
    survey.insert(ignore_permissions=True)


def _create_snag_task(project):
    task = frappe.new_doc("Task")
    task.project  = project.name
    task.subject  = "مراجعة قائمة الملاحظات (Snag List) – D+30"
    task.status   = "Open"
    task.due_date = frappe.utils.add_days(frappe.utils.today(), 7)
    task.insert(ignore_permissions=True)

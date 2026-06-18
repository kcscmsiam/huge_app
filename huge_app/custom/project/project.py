import frappe


def after_insert(doc, method=None):
    company = doc.company
    if not company:
        frappe.log_error(
            f"Project {doc.name} has no company set. Cannot create CC or Warehouse.",
            "Project after_insert — Missing Company"
        )
        return
    abbr         = get_abbr(company)
    project_name = doc.project_name or doc.name

    cc_name = create_cost_center(project_name, company, abbr)
    wh_name = create_site_warehouse(project_name, company, abbr)

    if cc_name:
        frappe.db.set_value("Project", doc.name, "cost_center", cc_name)
        frappe.db.commit()

    frappe.log_error(
        f"Project {doc.name} [{company}] → CC: {cc_name}, Warehouse: {wh_name}",
        "Project after_insert — Success"
    )


def get_abbr(company):
    return frappe.db.get_value("Company", company, "abbr") or ""

def create_cost_center(project_name, company, abbr):
    cc_name = f"{project_name} - {abbr}"
    if frappe.db.exists("Cost Center", cc_name):
        return cc_name

    parent_cc = f"Projects - {abbr}"
    if not frappe.db.exists("Cost Center", parent_cc):
        # Try company root cost center as fallback
        parent_cc = frappe.db.get_value("Company", company, "cost_center")
        if not parent_cc:
            frappe.log_error(
                f"Cannot find parent Cost Center for company '{company}' (abbr: {abbr}). "
                f"Create 'Projects - {abbr}' manually first.",
                "Project after_insert — Missing Parent CC"
            )
            return None

    cc = frappe.new_doc("Cost Center")
    cc.cost_center_name  = project_name
    cc.parent_cost_center = parent_cc
    cc.company           = company
    cc.is_group          = 0
    cc.insert(ignore_permissions=True)
    return cc.name

def create_site_warehouse(project_name, company, abbr):
    wh_name = f"{project_name} - Site - {abbr}"
    if frappe.db.exists("Warehouse", wh_name):
        return wh_name

    parent_wh = f"All Warehouses - {abbr}"
    if not frappe.db.exists("Warehouse", parent_wh):
        frappe.log_error(
            f"Parent Warehouse 'All Warehouses - {abbr}' not found for company '{company}'. "
            f"Site warehouse not created.",
            "Project after_insert — Missing Parent Warehouse"
        )
        return None

    wh = frappe.new_doc("Warehouse")
    wh.warehouse_name   = f"{project_name} - Site"
    wh.parent_warehouse = parent_wh
    wh.company          = company
    wh.warehouse_type   = "Transit"
    wh.insert(ignore_permissions=True)
    return wh.name


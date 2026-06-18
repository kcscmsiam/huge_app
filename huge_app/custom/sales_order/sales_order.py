import frappe

TEMPLATE_NAME = "Unidome Project Template"


def on_submit(doc, method=None):
    already_created = doc.get("custom_project_created") or 0
    if already_created:
        return

    opp_details   = get_opportunity_details(doc)
    project_name  = get_project_name_from_so(doc)
    floor_count   = int(doc.get("custom_floor_count") or 1)

    created_project = create_project_from_template(project_name, doc, opp_details)

    if created_project:
        frappe.db.set_value("Sales Order", doc.name, "custom_project_created", 1)

        additional_floors = []
        if floor_count > 1:
            additional_floors = create_additional_floors(doc, project_name, floor_count)

        frappe.db.commit()

        frappe.log_error(
            f"SO {doc.name} → Project created: {created_project}. Additional floors: {additional_floors}",
            "SO Submit → Project — Success"
        )


def get_project_name_from_so(so_doc):
    """Generate project name from Sales Order context."""
    customer   = so_doc.customer or "Unknown"
    so_name    = so_doc.name
    # Format: Customer — SO-YYYY-NNNNN — Floor 1
    return f"{customer} — {so_name} — Floor 1"


def get_opportunity_details(so_doc):
    """Retrieve linked Opportunity details if available."""
    opp_name = so_doc.get("custom_opportunity")
    if opp_name and frappe.db.exists("Opportunity", opp_name):
        opp = frappe.get_doc("Opportunity", opp_name)
        return {
            "name":         opp_name,
            "project_name": opp.get("custom_project_name") or opp.title,
            "area_m2":      opp.get("total_project_area_m2") or 0,
            "cost_center":  opp.get("cost_center") or None,
        }
    return {}


def create_project_from_template(project_name, so_doc, opp_details):
    """
    Create a Project using the Unidome Project Template.
    Links back to Sales Order and Opportunity.
    """
    # Check if template exists
    if not frappe.db.exists("Project Template", TEMPLATE_NAME):
        frappe.log_error(
            f"Project Template '{TEMPLATE_NAME}' not found. Project not created for SO {so_doc.name}.",
            "SO Submit → Project — Missing Template"
        )
        return None

    project = frappe.new_doc("Project")
    project.project_name    = project_name
    project.company         = so_doc.company
    project.customer        = so_doc.customer
    project.status          = "Open"
    project.expected_start_date = frappe.utils.today()

    # Link to Sales Order
    project.sales_order     = so_doc.name

    # Link to Opportunity if available
    if opp_details.get("name"):
        if hasattr(project, "custom_opportunity"):
            project.custom_opportunity = opp_details["name"]

    # Set area if available
    if opp_details.get("area_m2") and hasattr(project, "custom_total_area_m2"):
        project.custom_total_area_m2 = opp_details["area_m2"]

    # Apply project template — this loads the 7 task groups
    project.project_template = TEMPLATE_NAME

    project.insert(ignore_permissions=True)

    # after_insert hook fires automatically → creates CC + Warehouse

    return project.name


def create_additional_floors(so_doc, base_project_name, floor_count):
    """
    For multi-floor projects: create additional floor projects (floors 2+).
    Each floor is a separate Project linked to same Sales Order.
    """
    created = []
    for floor_num in range(2, floor_count + 1):
        floor_project_name = base_project_name.replace("Floor 1", f"Floor {floor_num}")

        # Check if already exists
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



app_name = "huge_app"
app_title = "Huge App"
app_publisher = "Msiam"
app_description = "Huge APP"
app_email = "siam.moh@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "huge_app",
# 		"logo": "/assets/huge_app/logo.png",
# 		"title": "Huge App",
# 		"route": "/huge_app",
# 		"has_permission": "huge_app.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/huge_app/css/huge_app.css"
# app_include_js = "/assets/huge_app/js/huge_app.js"

# include js, css files in header of web template
# web_include_css = "/assets/huge_app/css/huge_app.css"
# web_include_js = "/assets/huge_app/js/huge_app.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "huge_app/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "huge_app/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "huge_app.utils.jinja_methods",
# 	"filters": "huge_app.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "huge_app.install.before_install"
# after_install = "huge_app.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "huge_app.uninstall.before_uninstall"
# after_uninstall = "huge_app.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "huge_app.utils.before_app_install"
# after_app_install = "huge_app.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "huge_app.utils.before_app_uninstall"
# after_app_uninstall = "huge_app.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "huge_app.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }
doc_events = {
	"Lead": {
		"on_update": "huge_app.custom.lead.lead.on_update",
	},
	"Opportunity": {
		"on_update": "huge_app.custom.opportunity.opportunity.on_update",
	},
	"Purchase Receipt": {
		"on_submit": "huge_app.custom.purchase_receipt.purchase_receipt.on_submit",
		"on_update": "huge_app.custom.purchase_receipt.purchase_receipt.on_update",
	},
	"Project": {
		"after_insert": "huge_app.custom.project.project.after_insert",
		"on_update"   : "huge_app.custom.project.project.on_update",
	},
	"Sales Order": {
		"before_submit": "huge_app.custom.sales_order.sales_order.before_submit",
		"on_submit"    : "huge_app.custom.sales_order.sales_order.on_submit",
	},
	"Material Request": {
		"before_save": "huge_app.custom.material_request.material_request.before_save",
	},
	"Work Order": {
		"on_submit": "huge_app.custom.work_order.work_order.on_submit",
	},
	"Delivery Note": {
		"on_submit": "huge_app.custom.delivery_note.delivery_note.on_submit",
	},
	"FG QC Inspection": {
		"on_submit": "huge_app.custom.fg_qc_inspection.fg_qc_inspection.on_submit",
	},
	"Customer Satisfaction Survey": {
		"on_submit": "huge_app.custom.customer_satisfaction_survey.customer_satisfaction_survey.on_submit",
	},
}
# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"huge_app.tasks.all"
# 	],
# 	"daily": [
# 		"huge_app.tasks.daily"
# 	],
# 	"hourly": [
# 		"huge_app.tasks.hourly"
# 	],
# 	"weekly": [
# 		"huge_app.tasks.weekly"
# 	],
# 	"monthly": [
# 		"huge_app.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "huge_app.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "huge_app.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "huge_app.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "huge_app.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["huge_app.utils.before_request"]
# after_request = ["huge_app.utils.after_request"]

# Job Events
# ----------
# before_job = ["huge_app.utils.before_job"]
# after_job = ["huge_app.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"huge_app.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

scheduler_events = {
    "daily": [
        "huge_app.custom.scheduled_tasks.run"
    ]
}

fixtures = [
    "Role",
    {"dt": "Workflow Action Master", "filters": [["workflow_action_name", "in", [
        "Submit for Qualification", "Request Preliminary Design", "Mark Received",
        "Submit for Review", "Approve Preliminary Design", "Reject - Request Revision",
        "Request Design Revision", "Re-request Design", "Approve Costing",
        "Send Quotation", "Mark as Under Negotiation", "Revise Pricing",
        "Mark Won", "Mark Lost"
    ]]]},
    {
        "dt": "Custom Field",
        "filters": [
            [
                "name", "in", [
                    "Opportunity-custom_project_name",
                    "Opportunity-custom_external_designer",
                    "Opportunity-custom_external_designer_items",
                    "Opportunity-custom_external_items",
                    "Purchase Order Item-custom_note",
                ]
            ]
        ]
    },
    {
        "dt": "Custom Field",
        "filters": [["module", "=", "UNIDOME"]]
    },
    {
        "dt": "Workflow",
        "filters": [["name", "=", "UNIDOME Opportunity Workflow"]]
    },
    {"dt": "Workflow State"},
]
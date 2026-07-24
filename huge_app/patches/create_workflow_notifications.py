"""
Creates System Notification + Email alerts for every state of the two
active UNIDOME workflows, so the role responsible for a state is notified
the moment a document enters it. Safe to re-run (skips existing names).
"""
import frappe

NAME_PREFIX = "UNIDOME WF Notify"

WORKFLOWS = [
    {
        "workflow_name": "UNIDOME Opportunity Workflow",
        "doctype": "Opportunity",
        "field": "custom_unidome_opportunity_state",
        "label": "Opportunity",
    },
    {
        "workflow_name": "UNIDOME Project Workflow",
        "doctype": "Project",
        "field": "custom_project_stage",
        "label": "Project",
    },
]

CHANNELS = ["System Notification", "Email"]


def execute():
    for wf_conf in WORKFLOWS:
        _create_for_workflow(**wf_conf)
    frappe.db.commit()


def _create_for_workflow(workflow_name, doctype, field, label):
    wf = frappe.get_doc("Workflow", workflow_name)

    for state in wf.states:
        if not state.allow_edit:
            continue

        for channel in CHANNELS:
            name = f"{NAME_PREFIX}: {label} - {state.state} ({channel})"
            if frappe.db.exists("Notification", name):
                continue

            n = frappe.new_doc("Notification")
            n.name = name
            n.subject = f"[UNIDOME] {{{{ doc.name }}}} — {state.state}"
            n.document_type = doctype
            n.event = "Value Change"
            n.value_changed = field
            n.condition = f"doc.{field} == {state.state!r}"
            n.channel = channel
            n.enabled = 1
            n.message = (
                f"<p>الوثيقة <strong>{{{{ doc.name }}}}</strong> "
                f"وصلت إلى الحالة: <strong>{state.state}</strong></p>"
                f"<p>يتطلب إجراءً من الدور: <strong>{state.allow_edit}</strong></p>"
            )
            n.append("recipients", {"receiver_by_role": state.allow_edit})
            n.insert(ignore_permissions=True)

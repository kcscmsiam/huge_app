"""
huge_app/custom/opportunity/opportunity.py

IMPORTANT: كل الكود يجب أن يكون داخل دوال
           لا يجوز كتابة أي كود في مستوى الـ module خارج الدوال
"""

import frappe

WORKFLOW_NAME = "Outsourced Designer"

# --- إنشاء PO ---
PO_FROM_STATE      = "Preliminary Design Requested"
PO_ACTION          = "Approve"

# --- إلغاء PO ---
CANCEL_FROM_STATE  = "Preliminary Design Check"
CANCEL_ACTION      = "Reject"


def on_update(doc, method=None):
    _handle_workflow_approved(doc)
    _handle_workflow_rejected(doc)


# ──────────────────────────────────────────────
# إنشاء PO عند Approve من Preliminary Design Requested
# ──────────────────────────────────────────────

def _handle_workflow_approved(doc):

    curr_state = doc.sales_stage
    if not curr_state:
        return

    prev_doc   = doc.get_doc_before_save()
    prev_state = prev_doc.sales_stage if prev_doc else None

    if prev_state != PO_FROM_STATE:
        return

    approved_next_state = _get_transition_next_state(PO_FROM_STATE, PO_ACTION)
    if not approved_next_state or curr_state != approved_next_state:
        return

    # --- التحقق من الحقول المطلوبة ---
    supplier = doc.get("custom_external_designer")
    qty      = frappe.utils.flt(doc.get("custom_qty_for_external_designer"))
    rate     = frappe.utils.flt(doc.get("custom_rate_for_external_designer"))
    note     = doc.get("custom_notes_for_external_designer")

    if not supplier:
        frappe.throw("يرجى تحديد المصمم الخارجي (External Designer) قبل الموافقة.")

    # if not doc.custom_external_items.qty:
    #     frappe.throw("يرجى إدخال الكمية (Qty for External Designer) قبل الموافقة.")

    if not doc.custom_external_items:
        frappe.throw("يرجى إضافة الأصناف (External Designer Items) في الفرصة قبل الموافقة.")

    # --- التحقق من عدم وجود PO سابق ---
    existing_po = frappe.db.get_value("Purchase Order", {
        "custom_opportunity": doc.name,
        "docstatus"         : ["!=", 2],
    })
    if existing_po:
        frappe.msgprint(
            f"أمر الشراء <b>{existing_po}</b> موجود مسبقاً لهذه الفرصة.",
            title="تنبيه", indicator="orange"
        )
        return

    # --- إنشاء PO ---
    po = frappe.new_doc("Purchase Order")
    po.supplier           = supplier
    po.custom_opportunity = doc.name
    po.schedule_date      = frappe.utils.add_days(frappe.utils.nowdate(), 7)

    for item in doc.custom_external_items:
        po.append("items", {
            "item_code"    : item.item_code,
            "qty"          : item.qty,
            "rate"         : item.rate,
            "schedule_date": frappe.utils.add_days(frappe.utils.nowdate(), 7),
            "custom_note"  : item.description,
        })

    po.insert(ignore_permissions=True)
    po.submit()

    frappe.publish_realtime(
        "msgprint",
        {
            "message"  : f"✅ تم إنشاء أمر الشراء <b><a href='/app/purchase-order/{po.name}'>{po.name}</a></b>",
            "title"    : "Purchase Order Created",
            "indicator": "green",
        },
        user=frappe.session.user
    )

    frappe.logger("huge_app").info(
        f"[huge_app] PO {po.name} created for Opportunity {doc.name}"
    )


# ──────────────────────────────────────────────
# إلغاء PO عند Reject من Preliminary Design Check
# ──────────────────────────────────────────────

def _handle_workflow_rejected(doc):

    curr_state = doc.sales_stage
    if not curr_state:
        return

    prev_doc   = doc.get_doc_before_save()
    prev_state = prev_doc.sales_stage if prev_doc else None

    if prev_state != CANCEL_FROM_STATE:
        return

    reject_next_state = _get_transition_next_state(CANCEL_FROM_STATE, CANCEL_ACTION)
    if not reject_next_state or curr_state != reject_next_state:
        return

    # --- إيجاد الـ PO المرتبط ---
    po_name = frappe.db.get_value("Purchase Order", {
        "custom_opportunity": doc.name,
        "docstatus"         : 1,          # مسلّم فقط
    })

    if not po_name:
        frappe.msgprint(
            "لا يوجد أمر شراء مسلّم مرتبط بهذه الفرصة.",
            title="تنبيه", indicator="orange"
        )
        return

    # --- إلغاء الـ PO ---
    po = frappe.get_doc("Purchase Order", po_name)
    po.cancel()

    frappe.publish_realtime(
        "msgprint",
        {
            "message"  : f"🚫 تم إلغاء أمر الشراء <b><a href='/app/purchase-order/{po.name}'>{po.name}</a></b>",
            "title"    : "Purchase Order Cancelled",
            "indicator": "red",
        },
        user=frappe.session.user
    )

    frappe.logger("huge_app").info(
        f"[huge_app] PO {po.name} cancelled for Opportunity {doc.name}"
    )


# ──────────────────────────────────────────────
# Helper
# ──────────────────────────────────────────────

def _get_transition_next_state(from_state, action):
    """إيجاد الحالة التالية لانتقال معين في الـ Workflow"""
    return frappe.db.get_value(
        "Workflow Transition",
        {
            "parent": WORKFLOW_NAME,
            "state" : from_state,
            "action": action,
        },
        "next_state"
    )

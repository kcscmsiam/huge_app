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

    curr_state = doc.workflow_state
    if not curr_state:
        return

    prev_doc   = doc.get_doc_before_save()
    prev_state = prev_doc.workflow_state if prev_doc else None

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
        "opportunity": doc.name,
        "docstatus"  : ["!=", 2],
    })
    if existing_po:
        frappe.msgprint(
            f"أمر الشراء <b>{existing_po}</b> موجود مسبقاً لهذه الفرصة.",
            title="تنبيه", indicator="orange"
        )
        return

    # --- إنشاء PO ---
    po = frappe.new_doc("Purchase Order")
    po.supplier      = supplier
    po.opportunity   = doc.name
    po.schedule_date = frappe.utils.add_days(frappe.utils.nowdate(), 7)

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

    curr_state = doc.workflow_state
    if not curr_state:
        return

    prev_doc   = doc.get_doc_before_save()
    prev_state = prev_doc.workflow_state if prev_doc else None

    if prev_state != CANCEL_FROM_STATE:
        return

    reject_next_state = _get_transition_next_state(CANCEL_FROM_STATE, CANCEL_ACTION)
    if not reject_next_state or curr_state != reject_next_state:
        return

    # --- إيجاد الـ PO المرتبط ---
    po_name = frappe.db.get_value("Purchase Order", {
        "opportunity": doc.name,
        "docstatus"  : 1,          # مسلّم فقط
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
"""
SERVER SCRIPT: unidome:opportunity_cost_transfer
DocType:       Opportunity
Event:         on_update
ERPNext:       v15.x — Huge Group (HC&EG / HC&EP / HC&EM)

PURPOSE:
When Opportunity reaches Won or Lost terminal state,
create Purchase Invoice for pre-contract design costs
that were received via Purchase Receipt (sitting in GRNI).

  WON  → PI posted to Project Cost Center (direct project expense)
  LOST → PI posted to design department expense account

MULTI-ENTITY: derives company abbreviation from doc.company dynamically.
"""

# ─── COMPANY ABBREVIATION (dynamic) ──────────────────────────────────────────
def get_abbr(company):
    abbr = frappe.db.get_value("Company", company, "abbr")
    return abbr or ""

# ─── TERMINAL STATE DEFINITIONS ──────────────────────────────────────────────
WON_STATES  = {"Won", "Contract Signed", "Order Confirmed"}
LOST_STATES = {"Lost", "Cancelled", "Rejected", "No Go"}

# ─── ACCOUNT NAME BUILDERS ────────────────────────────────────────────────────
def get_accounts(company):
    abbr = get_abbr(company)
    return {
        "project_expense": f"تكاليف تصميم مشاريع - {abbr}",
        "lost_expense":    f"مصاريف عطاءات خاسرة - {abbr}",
    }

# ─── HELPERS ─────────────────────────────────────────────────────────────────
def get_linked_purchase_receipts(opportunity_name):
    return frappe.get_all(
        "Purchase Receipt",
        filters={
            "custom_opportunity": opportunity_name,
            "docstatus": 1,
            "status": ("!=", "Completed")
        },
        fields=["name", "supplier", "company", "posting_date", "currency", "conversion_rate"]
    )

def create_purchase_invoice(pr_name, target_account, target_cost_center, opportunity_name):
    existing = frappe.get_all(
        "Purchase Invoice",
        filters={"custom_opportunity": opportunity_name, "docstatus": ("!=", 2)},
        fields=["name"]
    )
    if existing:
        frappe.log_error(
            f"PI already exists for Opportunity {opportunity_name}: {existing[0]['name']}",
            "Cost Transfer — Duplicate Skipped"
        )
        return None

    pr  = frappe.get_doc("Purchase Receipt", pr_name)
    pi  = frappe.new_doc("Purchase Invoice")
    pi.supplier         = pr.supplier
    pi.company          = pr.company
    pi.posting_date     = frappe.utils.today()
    pi.set_posting_time = 1
    pi.update_stock     = 0
    pi.currency         = pr.currency
    pi.conversion_rate  = pr.conversion_rate or 1

    if hasattr(pi, "custom_opportunity"):
        pi.custom_opportunity = opportunity_name

    for pr_item in pr.items:
        row = pi.append("items", {})
        row.item_code        = pr_item.item_code
        row.item_name        = pr_item.item_name
        row.description      = pr_item.description or pr_item.item_name
        row.qty              = pr_item.qty
        row.uom              = pr_item.uom
        row.rate             = pr_item.rate
        row.amount           = pr_item.amount
        row.expense_account  = target_account
        row.cost_center      = target_cost_center
        row.purchase_receipt = pr_name
        row.pr_detail        = pr_item.name

    for pr_tax in pr.taxes:
        row = pi.append("taxes", {})
        row.charge_type   = pr_tax.charge_type
        row.account_head  = pr_tax.account_head
        row.rate          = pr_tax.rate
        row.tax_amount    = pr_tax.tax_amount
        row.description   = pr_tax.description

    pi.insert(ignore_permissions=True)
    frappe.log_error(
        f"PI {pi.name} created → Opportunity {opportunity_name} | PR {pr_name} | Account {target_account}",
        "Cost Transfer — Success"
    )
    return pi.name


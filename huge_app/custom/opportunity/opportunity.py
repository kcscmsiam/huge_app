"""
huge_app/custom/opportunity/opportunity.py

Handlers:
  1. Outsourced Designer workflow — PO creation / cancellation (existing)
  2. UNIDOME Scripts 2, 3, 4, 8 — state-machine automations
"""

import frappe
from datetime import date, timedelta
from frappe.utils.user import get_users_with_role

WORKFLOW_NAME = "Outsourced Designer"

PO_FROM_STATE     = "Preliminary Design Requested"
PO_ACTION         = "Approve"

CANCEL_FROM_STATE = "Preliminary Design Check"
CANCEL_ACTION     = "Reject"

UNIDOME_SCORE_THRESHOLD = 7


def on_update(doc, method=None):
    if doc.flags.ignore_unidome_hooks:
        return

    # Existing: Outsourced Designer PO logic
    _handle_workflow_approved(doc)
    _handle_workflow_rejected(doc)

    # UNIDOME automations
    _unidome_sync_external_items_rate(doc)
    _unidome_create_po_for_external_designer(doc)
    _unidome_sla_preliminary_design(doc)
    _unidome_final_design_validate_fields(doc)
    _unidome_preliminary_design_approved_create_pr(doc)
    _unidome_costing_approved_create_quotation(doc)
    _unidome_negotiation_lost_reason(doc)


# ─── Outsourced Designer: create PO on Approve ───────────────────────────────

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

    supplier = doc.get("custom_external_designer")
    if not supplier:
        frappe.throw("يرجى تحديد المصمم الخارجي (External Designer) قبل الموافقة.")

    if not doc.custom_external_items:
        frappe.throw("يرجى إضافة الأصناف (External Designer Items) في الفرصة قبل الموافقة.")

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

    frappe.publish_realtime("msgprint", {
        "message"  : f"✅ تم إنشاء أمر الشراء <b><a href='/app/purchase-order/{po.name}'>{po.name}</a></b>",
        "title"    : "Purchase Order Created",
        "indicator": "green",
    }, user=frappe.session.user)

    frappe.logger("huge_app").info(
        f"[huge_app] PO {po.name} created for Opportunity {doc.name}"
    )


# ─── Outsourced Designer: cancel PO on Reject ────────────────────────────────

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

    po_name = frappe.db.get_value("Purchase Order", {
        "opportunity": doc.name,
        "docstatus"  : 1,
    })

    if not po_name:
        frappe.msgprint(
            "لا يوجد أمر شراء مسلّم مرتبط بهذه الفرصة.",
            title="تنبيه", indicator="orange"
        )
        return

    po = frappe.get_doc("Purchase Order", po_name)
    po.cancel()

    frappe.publish_realtime("msgprint", {
        "message"  : f"🚫 تم إلغاء أمر الشراء <b><a href='/app/purchase-order/{po.name}'>{po.name}</a></b>",
        "title"    : "Purchase Order Cancelled",
        "indicator": "red",
    }, user=frappe.session.user)

    frappe.logger("huge_app").info(
        f"[huge_app] PO {po.name} cancelled for Opportunity {doc.name}"
    )


# ─── Script 18: Sync custom_external_items rate from supplier's Price List ──

def _unidome_sync_external_items_rate(doc):
    supplier = doc.get("custom_external_designer")
    if not supplier or not doc.get("custom_external_items"):
        return

    price_list = frappe.db.get_value("Supplier", supplier, "default_price_list")
    if not price_list:
        return

    for row in doc.custom_external_items:
        if not row.item_code:
            continue

        price_list_rate = _get_item_price_list_rate(row.item_code, price_list, supplier)
        if price_list_rate and row.rate != price_list_rate:
            row.rate = price_list_rate
            frappe.db.set_value(
                "External Item Details", row.name, "rate", price_list_rate,
                update_modified=False,
            )


def _get_item_price_list_rate(item_code, price_list, supplier):
    # External Item Details has no UOM field, so match on item_code + price_list
    # only — prefer a row tied to this supplier, fall back to a general one.
    rows = frappe.get_all(
        "Item Price",
        filters={"item_code": item_code, "price_list": price_list, "buying": 1},
        fields=["supplier", "price_list_rate"],
        order_by="valid_from desc",
    )
    for row in rows:
        if row.supplier == supplier:
            return row.price_list_rate
    for row in rows:
        if not row.supplier:
            return row.price_list_rate
    return None


# ─── Script 2a: UNIDOME workflow → create PO for external designer ──────────

def _unidome_create_po_for_external_designer(doc):
    unidome_state = doc.get("custom_unidome_opportunity_state")
    if unidome_state != "Preliminary Design Requested":
        return

    prev_doc = doc.get_doc_before_save()
    if not prev_doc:
        return
    if prev_doc.get("custom_unidome_opportunity_state") == "Preliminary Design Requested":
        return

    supplier = doc.get("custom_external_designer")
    if not supplier:
        frappe.throw("يرجى تحديد المصمم الخارجي (External Designer) قبل طلب التصميم المبدئي.")

    if not doc.custom_external_items:
        frappe.throw("يرجى إضافة الأصناف (External Designer Items) في الفرصة قبل طلب التصميم المبدئي.")

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

    po = frappe.new_doc("Purchase Order")
    po.supplier      = supplier
    po.opportunity   = doc.name
    po.schedule_date = frappe.utils.add_days(frappe.utils.nowdate(), 7)

    company = po.company or frappe.defaults.get_user_default("company")
    abbr    = frappe.db.get_value("Company", company, "abbr")
    default_warehouse = f"Stores - {abbr}" if abbr else None

    for item in doc.custom_external_items:
        po.append("items", {
            "item_code"    : item.item_code,
            "qty"          : item.qty,
            "rate"         : item.rate,
            "schedule_date": frappe.utils.add_days(frappe.utils.nowdate(), 7),
            "custom_note"  : item.description,
            "warehouse"    : default_warehouse,
        })

    po.flags.ignore_unidome_hooks = True
    po.insert(ignore_permissions=True)
    po.submit()

    frappe.publish_realtime("msgprint", {
        "message"  : f"✅ تم إنشاء أمر الشراء <b><a href='/app/purchase-order/{po.name}'>{po.name}</a></b>",
        "title"    : "Purchase Order Created",
        "indicator": "green",
    }, user=frappe.session.user)

    frappe.logger("huge_app").info(
        f"[huge_app] PO {po.name} created for Opportunity {doc.name} (UNIDOME workflow)"
    )


# ─── Script 2: SLA for Preliminary Design ────────────────────────────────────

def _unidome_sla_preliminary_design(doc):
    unidome_state = doc.get("custom_unidome_opportunity_state")
    if unidome_state != "Preliminary Design Requested":
        return

    prev_doc = doc.get_doc_before_save()
    if not prev_doc:
        return
    if prev_doc.get("custom_unidome_opportunity_state") == "Preliminary Design Requested":
        return

    due_date = _add_business_days(frappe.utils.today(), 5)
    frappe.db.set_value(
        "Opportunity", doc.name,
        "custom_sla_design_due_date", due_date
    )

    recipients = get_users_with_role("UNIDOME External Designer")
    if recipients:
        frappe.sendmail(
            recipients=recipients,
            subject=f"[UNIDOME] طلب تصميم مبدئي – {doc.name}",
            message=f"""
<p>تم طلب تصميم مبدئي للفرصة: <strong>{doc.name}</strong></p>
<p>موقع المشروع: {doc.get('custom_project_location') or '—'}</p>
<p>تاريخ الاستحقاق (SLA): <strong>{due_date}</strong></p>
<p>يرجى الالتزام بالموعد المحدد.</p>
""",
        )

    today_date = frappe.utils.getdate(frappe.utils.today())
    sla_date   = doc.get("custom_sla_design_due_date")
    if sla_date and frappe.utils.getdate(sla_date) < today_date:
        managers = get_users_with_role("UNIDOME Operations Manager")
        if managers:
            frappe.sendmail(
                recipients=managers,
                subject=f"[UNIDOME] تنبيه تجاوز SLA – {doc.name}",
                message=f"<p>الفرصة <strong>{doc.name}</strong> تجاوزت مهلة التصميم المبدئي.</p>",
            )


# ─── Script 17: Preliminary Design Review Approved → Create Purchase Receipt ─

def _unidome_preliminary_design_approved_create_pr(doc):
    unidome_state = doc.get("custom_unidome_opportunity_state")
    if unidome_state != "Costing and Saving Analysis":
        return

    prev_doc = doc.get_doc_before_save()
    if not prev_doc:
        return
    if prev_doc.get("custom_unidome_opportunity_state") != "Preliminary Design Review":
        return

    po_name = frappe.db.get_value("Purchase Order", {
        "opportunity": doc.name,
        "docstatus"  : 1,
    })
    if not po_name:
        frappe.throw(
            "لا يوجد أمر شراء مسلّم للمصمم الخارجي مرتبط بهذه الفرصة — "
            "لا يمكن إنشاء إشعار استلام التصميم المبدئي."
        )

    existing_pr = frappe.db.get_value("Purchase Receipt", {
        "custom_opportunity": doc.name,
        "docstatus"         : ["!=", 2],
    })
    if existing_pr:
        frappe.msgprint(
            f"إشعار الاستلام <b>{existing_pr}</b> موجود مسبقاً لهذه الفرصة.",
            title="تنبيه", indicator="orange"
        )
        return

    actual_area = frappe.utils.flt(doc.get("custom_actual_desgined_area_m2"))
    if not actual_area:
        frappe.throw(
            "يرجى إدخال المساحة المصممة الفعلية (custom_actual_desgined_area_m2) "
            "قبل الموافقة على التصميم المبدئي."
        )

    from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt

    pr = make_purchase_receipt(po_name)
    pr.custom_opportunity = doc.name
    for item in pr.items:
        item.qty = actual_area

    pr.flags.ignore_unidome_hooks = True
    pr.insert(ignore_permissions=True)
    pr.submit()

    frappe.publish_realtime("msgprint", {
        "message"  : f"✅ تم إنشاء إشعار استلام التصميم المبدئي "
                     f"<b><a href='/app/purchase-receipt/{pr.name}'>{pr.name}</a></b>",
        "title"    : "Purchase Receipt Created",
        "indicator": "green",
    }, user=frappe.session.user)

    frappe.logger("huge_app").info(
        f"[huge_app] Purchase Receipt {pr.name} created for Opportunity {doc.name} "
        f"(Preliminary Design Review approved → Costing and Saving Analysis)"
    )


# ─── Script 3: Costing Approved → Auto-create Quotation ─────────────────────

def _unidome_costing_approved_create_quotation(doc):
    unidome_state = doc.get("custom_unidome_opportunity_state")
    if unidome_state != "Quotation Ready":
        return

    prev_doc = doc.get_doc_before_save()
    if not prev_doc:
        return
    if prev_doc.get("custom_unidome_opportunity_state") == "Quotation Ready":
        return

    existing_qt = frappe.db.get_value(
        "Quotation",
        {"opportunity": doc.name, "docstatus": ["!=", 2]},
        "name"
    )
    if existing_qt:
        return

    party_type = doc.opportunity_from or "Lead"
    party = doc.party_name

    if not doc.get("items"):
        frappe.throw(
            "لا يمكن إنشاء عرض سعر تلقائي بدون أصناف في جدول Items الخاص بالفرصة",
            frappe.ValidationError
        )

    qt = frappe.new_doc("Quotation")
    qt.quotation_to  = party_type
    qt.party_name    = party
    qt.opportunity   = doc.name
    qt.valid_till    = frappe.utils.add_days(frappe.utils.today(), 30)
    qt.order_type    = "Sales"

    for row in doc.get("items"):
        qt.append("items", {
            "item_code"  : row.item_code,
            "item_name"  : row.item_name,
            "description": row.description,
            "qty"        : row.qty,
            "uom"        : row.uom,
            "rate"       : row.rate,
        })

    qt.flags.ignore_unidome_hooks = True
    qt.insert(ignore_permissions=True)

    frappe.publish_realtime("msgprint", {
        "message"  : f"✅ تم إنشاء عرض السعر <b><a href='/app/quotation/{qt.name}'>{qt.name}</a></b>",
        "title"    : "Quotation Created",
        "indicator": "green",
    }, user=frappe.session.user)


# ─── Script 4: Closed Lost → require lost reason ─────────────────────────────

def _unidome_negotiation_lost_reason(doc):
    unidome_state = doc.get("custom_unidome_opportunity_state")
    if unidome_state != "Closed Lost":
        return

    if not doc.get("custom_lost_reason"):
        frappe.throw(
            "يرجى تعبئة سبب الخسارة (Lost Reason) قبل إغلاق الفرصة",
            frappe.ValidationError
        )

    frappe.logger("huge_app").info(
        f"[Closed Lost] {doc.name} | Reason: {doc.custom_lost_reason}"
    )


# ─── Script 8: Final Design → validate BOQ fields ────────────────────────────

def _unidome_final_design_validate_fields(doc):
    unidome_state = doc.get("custom_unidome_opportunity_state")
    if unidome_state != "Costing and Saving Analysis":
        return

    prev_doc = doc.get_doc_before_save()
    if not prev_doc:
        return
    if prev_doc.get("custom_unidome_opportunity_state") == "Costing and Saving Analysis":
        return

    required_fields = {
        "custom_unidome_qty"      : "كمية وحدات Unidome",
        "custom_unidome_size"     : "مقاس وحدة Unidome",
        "custom_steel_qty_kg"     : "كمية الحديد (كغ)",
        "custom_concrete_qty_m3"  : "كمية الخرسانة (م³)",
        "custom_slab_thickness_mm": "سماكة البلاطة (مم)",
    }

    missing = [
        label for field, label in required_fields.items()
        if not doc.get(field)
    ]

    if missing:
        frappe.throw(
            "يرجى إدخال قيم حقول التصميم النهائي قبل الانتقال إلى مرحلة التسعير: "
            + "، ".join(missing),
            frappe.ValidationError
        )


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _get_transition_next_state(from_state, action):
    return frappe.db.get_value(
        "Workflow Transition",
        {"parent": WORKFLOW_NAME, "state": from_state, "action": action},
        "next_state"
    )


def _add_business_days(start_date, num_days):
    current = frappe.utils.getdate(start_date)
    added   = 0
    while added < num_days:
        current += timedelta(days=1)
        if current.weekday() not in (4, 5):  # 4=Fri, 5=Sat (Jordan weekend)
            added += 1
    return current


# ─── Cost Transfer helpers (not called directly via hook) ────────────────────

def get_abbr(company):
    abbr = frappe.db.get_value("Company", company, "abbr")
    return abbr or ""


WON_STATES  = {"Won", "Contract Signed", "Order Confirmed"}
LOST_STATES = {"Lost", "Cancelled", "Rejected", "No Go"}


def get_accounts(company):
    abbr = get_abbr(company)
    return {
        "project_expense": f"تكاليف تصميم مشاريع - {abbr}",
        "lost_expense"   : f"مصاريف عطاءات خاسرة - {abbr}",
    }


def get_linked_purchase_receipts(opportunity_name):
    return frappe.get_all(
        "Purchase Receipt",
        filters={
            "custom_opportunity": opportunity_name,
            "docstatus"         : 1,
            "status"            : ("!=", "Completed")
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
        frappe.logger("huge_app").info(
            f"[Cost Transfer] PI already exists for Opportunity {opportunity_name}: {existing[0]['name']}"
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
        row.charge_type  = pr_tax.charge_type
        row.account_head = pr_tax.account_head
        row.rate         = pr_tax.rate
        row.tax_amount   = pr_tax.tax_amount
        row.description  = pr_tax.description

    pi.insert(ignore_permissions=True)
    frappe.logger("huge_app").info(
        f"[Cost Transfer] PI {pi.name} → Opp {opportunity_name} | PR {pr_name} | Acct {target_account}"
    )
    return pi.name

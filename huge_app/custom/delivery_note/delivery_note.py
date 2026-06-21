import frappe

_log = lambda msg: frappe.logger("huge_app").info(msg)


def on_submit(doc, method=None):
    if doc.flags.ignore_unidome_hooks:
        return
    _unidome_delivery_note_stock_entry(doc)


def _unidome_delivery_note_stock_entry(doc):
    project = doc.project or ""

    se = frappe.new_doc("Stock Entry")
    se.stock_entry_type = "Material Issue"
    se.purpose          = "Material Issue"
    se.project          = project
    se.company          = doc.company
    se.posting_date     = frappe.utils.today()
    se.remarks          = f"Material issue for Delivery Note {doc.name}"

    for dn_item in doc.items:
        if not dn_item.warehouse:
            continue
        se.append("items", {
            "item_code"  : dn_item.item_code,
            "qty"        : dn_item.qty,
            "s_warehouse": dn_item.warehouse,
            "uom"        : dn_item.uom,
        })

    if not se.items:
        return

    se.flags.ignore_unidome_hooks = True
    try:
        se.insert(ignore_permissions=True)
        se.submit()
        _log(f"[DN Submit] Stock Entry {se.name} created from DN {doc.name}")
    except Exception as exc:
        frappe.log_error(
            "UNIDOME DN → Stock Entry — Error",
            f"Failed to create Stock Entry from DN {doc.name}: {exc}"
        )

    if project and frappe.db.exists("Project", project):
        frappe.db.set_value("Project", project, "status", "Shipped")

    customer_email = frappe.db.get_value("Customer", doc.customer, "email_id")
    if customer_email:
        frappe.sendmail(
            recipients=[customer_email],
            subject=f"[UNIDOME] شحن طلبكم – {doc.name}",
            message=f"""
<p>عزيزنا العميل،</p>
<p>يسعدنا إبلاغكم بأنه تم شحن طلبكم (<strong>{doc.name}</strong>) بتاريخ {frappe.utils.today()}.</p>
<p>شكراً لثقتكم بنا.</p>
""",
        )

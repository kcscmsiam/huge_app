__version__ = "0.0.1"


def _patch_erpnext_prospect_make_customer():
	# erpnext.crm.doctype.prospect.prospect.make_customer never sets
	# Customer.prospect_name (unlike the equivalent Lead flow, which sets
	# Customer.lead_name). Quotation._make_customer relies on that field to
	# detect an existing Customer for a Prospect before creating a new one,
	# so every "Create > Sales Order" from a Quotation linked to a Prospect
	# created a duplicate Customer instead of reusing the existing one.
	import erpnext.crm.doctype.prospect.prospect as prospect_module

	original_make_customer = prospect_module.make_customer

	def make_customer_with_prospect_link(source_name, target_doc=None):
		customer = original_make_customer(source_name, target_doc)
		customer.prospect_name = source_name
		return customer

	prospect_module.make_customer = make_customer_with_prospect_link


_patch_erpnext_prospect_make_customer()


def _patch_quotation_make_customer_dedup():
	# Belt-and-suspenders dedup: even if the Lead/Prospect link field on an
	# existing Customer is missing, empty, or the linked Customer gets
	# deleted later, never create a second Customer with the exact same
	# customer_name — always reuse the existing one instead.
	import frappe
	import erpnext.selling.doctype.quotation.quotation as quotation_module

	original_make_customer = quotation_module._make_customer

	def make_customer_with_name_dedup(source_name, ignore_permissions=False):
		quotation = frappe.db.get_value(
			"Quotation", source_name,
			["quotation_to", "party_name", "customer_name"], as_dict=1,
		)
		target_name = quotation.customer_name or quotation.party_name
		if target_name:
			existing = frappe.db.get_value("Customer", {"customer_name": target_name})
			if existing:
				return frappe.get_doc("Customer", existing)

		return original_make_customer(source_name, ignore_permissions)

	quotation_module._make_customer = make_customer_with_name_dedup


_patch_quotation_make_customer_dedup()

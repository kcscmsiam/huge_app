import frappe

CAPA_SCORE_THRESHOLD = 7


def on_submit(doc, method=None):
    if doc.flags.ignore_unidome_hooks:
        return
    _unidome_capa_trigger(doc)


def _unidome_capa_trigger(doc):
    overall_score = frappe.utils.cint(doc.overall_score or 10)
    project       = doc.project or ""

    has_critical_snag = any(
        item.severity == "Critical" and item.status == "Open"
        for item in (doc.snag_list or [])
    )

    if overall_score < CAPA_SCORE_THRESHOLD or has_critical_snag:
        reasons = []
        if overall_score < CAPA_SCORE_THRESHOLD:
            reasons.append(f"تقييم منخفض: {overall_score}/10")
        if has_critical_snag:
            reasons.append("توجد عناصر حرجة في قائمة الملاحظات")

        capa = frappe.new_doc("CAPA Record")
        capa.project     = project
        capa.source      = "Customer Survey"
        capa.description = " | ".join(reasons)
        capa.status      = "Open"

        if has_critical_snag:
            capa.vsm_flag = 1

        capa.flags.ignore_unidome_hooks = True
        capa.insert(ignore_permissions=True)

        if project:
            frappe.db.set_value("Project", project, "custom_vsm_review_required", 1)

        frappe.logger("huge_app").info(
            f"[CAPA] {capa.name} opened for Survey {doc.name} (Score: {overall_score}, Critical: {has_critical_snag})"
        )

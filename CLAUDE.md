# CLAUDE.md — huge_app

دليل مرجعي شامل للتطبيق. يُقرأ هذا الملف تلقائياً في بداية كل جلسة.
**آخر تحديث:** 2026-07-24 — يشمل: Quotation بأصناف حقيقية من الفرصة، Purchase Receipt تلقائي عند اعتماد التصميم المبدئي، مزامنة سعر `custom_external_items` من Price List المورد، إصلاح ربط Sales Order↔Opportunity وProject↔Opportunity، Material Request تلقائي عند دخول Material Planning، ومونكي-باتش على أخطاء جذرية في ERPNext (تكرار Customer عند التحويل من Prospect).

---

## 1. بيئة التشغيل

| العنصر | القيمة |
|--------|--------|
| Bench path | `/home/erpadmin/frappe-bench` |
| Site | `erp.huge.ps` |
| DB name | `db_huge` |
| DB user | `db_huge` |
| DB password | من `sites/erp.huge.ps/site_config.json` |
| App path | `apps/huge_app/` |
| frappe | 15.107.3 |
| erpnext | 15.108.0 |
| crm | 1.71.2 |
| huge_app | 0.0.1 |

### إعادة تشغيل الخادم

> **⚠️ اكتُشف 2026-07-24:** الـ gunicorn هنا يعمل بخيار `--preload` — هذا يعني أن `kill -HUP` **غير موثوق** لتحميل تعديلات Python: الماستر يُعيد تشغيل الـ workers لكنها قد ترث الكود القديم من العملية الأم المُحمَّلة مسبقاً. لوحظ فعلياً سلوك غير متسق (بعض الطلبات نفّذت الكود الجديد وبعضها القديم بعد نفس HUP). **استخدم `kill -TERM` (إعادة تشغيل كاملة) دائماً بعد أي تعديل على ملف `.py`.**

```bash
# إعادة تشغيل كاملة — الطريقة الموثوقة الوحيدة بعد تعديل .py (بدون sudo)
kill -TERM $(pgrep -f "gunicorn -b 127.0.0.1" | head -1)
# supervisor يعيد تشغيله تلقائياً (autorestart=true)
sleep 8
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://127.0.0.1:8000 -H "Host: erp.huge.ps"

# Graceful reload (غير موثوق هنا — لا تعتمد عليه وحده لتحميل كود جديد)
kill -HUP $(pgrep -f "gunicorn -b 127.0.0.1" | head -1)
```

---

## 2. هيكل التطبيق

```
apps/huge_app/
├── CLAUDE.md
├── patches.txt                             ← قائمة patches (تُنفَّذ مرة واحدة عند migrate)
├── huge_app/
│   ├── hooks.py                            ← نقطة التسجيل الرئيسية
│   ├── patches/
│   │   ├── __init__.py
│   │   ├── create_unidome_project_template.py  ← ينشئ Template + 13 Task
│   │   └── add_project_stage_field.py          ← ينشئ حقل custom_project_stage على Project
│   ├── fixtures/
│   │   ├── custom_field.json               ← 43 حقل مخصص (5 قديمة + 38 UNIDOME)
│   │   ├── role.json                       ← 10 أدوار UNIDOME
│   │   ├── workflow.json                   ← UNIDOME Opportunity Workflow
│   │   ├── workflow_state.json             ← 24 حالة (13 Opportunity + 11 Project)
│   │   ├── workflow_action_master.json     ← 24 action (14 Opportunity + 10 Project)
│   │   └── project_workflow.json           ← UNIDOME Project Workflow
│   ├── custom/
│   │   ├── lead/
│   │   │   └── lead.py                     ← Script 1: Lead محوّل → Opportunity
│   │   ├── opportunity/
│   │   │   └── opportunity.py              ← Outsourced Designer PO + Scripts 2,3,4,8,17,18
│   │   ├── sales_order/
│   │   │   └── sales_order.py              ← Scripts 5,6,19: التحقق + إنشاء Project + فاتورة + تعبئة custom_opportunity
│   │   ├── project/
│   │   │   └── project.py                  ← CC+Warehouse + Scripts 7,9,10,14,20
│   │   ├── purchase_receipt/
│   │   │   └── purchase_receipt.py         ← تحديث Opportunity + إنشاء BOQ
│   │   ├── material_request/
│   │   │   └── material_request.py         ← BOM optimizer (before_save)
│   │   ├── work_order/
│   │   │   └── work_order.py               ← Script 11: سلسلة Work Orders
│   │   ├── delivery_note/
│   │   │   └── delivery_note.py            ← Script 13: Stock Entry + إشعار العميل
│   │   ├── fg_qc_inspection/
│   │   │   └── fg_qc_inspection.py         ← Script 12: بوابة QC النهائي
│   │   ├── customer_satisfaction_survey/
│   │   │   └── customer_satisfaction_survey.py ← Script 16: CAPA trigger
│   │   └── scheduled_tasks.py              ← Script 15: فاتورة الثبات D+30
│   ├── public/
│   │   └── js/opportunity.js               ← ملاحظة فقط (لا منطق)
│   └── huge_app/
│       └── doctype/
│           ├── project_boq/
│           ├── project_boq_client_item/
│           ├── project_boq_company_item/
│           ├── engineering_solutions_settings/
│           ├── external_item_details/
│           ├── site_inspection_report/     ← UNIDOME جديد
│           ├── site_inspection_checklist_item/ ← Child Table
│           ├── fg_qc_inspection/           ← UNIDOME جديد
│           ├── customer_satisfaction_survey/ ← UNIDOME جديد
│           ├── snag_list_item/             ← Child Table
│           └── capa_record/               ← UNIDOME جديد
```

---

## 3. DocTypes المخصصة

### 3.1 Project BOQ
DocType رئيسي لعروض الكميات.

| الحقل | النوع | الخيارات |
|-------|-------|----------|
| project | Link | Project — **اختياري (مُصلَح 2026-07-13)**، كان `reqd=1` مما يمنع إنشاء BOQ قبل وجود Project (BOQ يُنشأ في مرحلة التصميم المبدئي، قبل SO/Project) |
| opportunity | Link | Opportunity |
| floor_number | Int | |
| revision | Int | |
| status | Select | Draft / Pending Client Approval / Pending Auditor Review / Approved / Rejected |
| approved_by_auditor | Check | |
| approved_by_client | Check | |
| approval_date | Date | |
| company_items | Table | Project BOQ Company Item |
| client_items | Table | Project BOQ Client Item |
| total_slab_area_m2 | Float | |
| total_unidome_units | Int | |
| design_file | Attach | |
| notes | Text Editor | |

> **ملاحظة:** الحقول project/opportunity هي الحقول الحقيقية الوحيدة القابلة للربط بمصدر البيانات عند الإنشاء التلقائي من `purchase_receipt.py`. لا توجد حقول company/customer/project_name/purchase_receipt/date/unidome_supplier/steel_supplier/concrete_supplier على هذا الـ DocType — كانت موجودة كأسطر معطوبة في الكود القديم (تُضبط على doc بايثون بصمت دون أي تأثير).

### 3.2 Project BOQ Company Item / Client Item (Child Tables)
شركة: item_code, uom, qty, notes. عميل: description, uom, qty, notes.

### 3.3 Engineering Solutions Settings (Single)
إعدادات الحسابات والمراكز المالية للتطبيق.

### 3.4 External Item Details (Child Table)
مرتبطة بـ Opportunity عبر `custom_external_items`: item_code, qty, rate, description.

---

### 3.5 UNIDOME: Site Inspection Report
قابل للإرسال (is_submittable). الأدوار: UNIDOME Site Engineer, UNIDOME Quality Inspector.

| الحقل | النوع | تفاصيل |
|-------|-------|---------|
| project | Link → Project | مطلوب |
| inspection_stage | Select | Lower Steel Network / Unidome Installation / Upper Steel Network / Concrete Pouring |
| inspection_date | Date | مطلوب |
| site_engineer | Link → User | مطلوب |
| checklist | Table → Site Inspection Checklist Item | |
| photos | Attach Multiple | |
| result | Select | Approved / Rejected |
| rejection_notes | Text | يظهر عند الرفض |
| capa_opened | Check | Read Only — تُعيّنه السكريبت |

**Child Table: Site Inspection Checklist Item**
الحقول: check_item (Data), status (Pass/Fail), notes (Small Text).

---

### 3.6 UNIDOME: FG QC Inspection
قابل للإرسال. الأدوار: UNIDOME Quality Inspector, UNIDOME Factory User.

| الحقل | النوع |
|-------|-------|
| work_order | Link → Work Order |
| project | Link → Project |
| inspection_date | Date |
| inspector | Link → User |
| result | Select: Accept / Reject |
| defect_description | Text |
| photos | Attach Multiple |

**on_submit:**
- Accept → ينشئ Delivery Note من SO + يُحدّث Project status = "Ready for Shipment"
- Reject → يُسجّل Non-Conformance + يُعيد فتح WO جديد + يُرسل إشعار لـ Quality Inspector و Factory User

---

### 3.7 UNIDOME: Customer Satisfaction Survey
قابل للإرسال. يُنشئ تلقائياً بعد D+30 من اكتمال التنفيذ.

| الحقل | النوع |
|-------|-------|
| project | Link → Project |
| customer | Link → Customer |
| survey_date | Date |
| overall_score | Int (1-10) |
| design_score | Int |
| execution_score | Int |
| timeline_score | Int |
| comments | Text |
| snag_list | Table → Snag List Item |

**Child Table: Snag List Item**
الحقول: issue (Data), severity (Minor/Major/Critical), status (Open/Closed), resolution (Text).

**on_submit:** إذا كان التقييم < 7 أو يوجد عنصر حرج → ينشئ CAPA Record تلقائياً.

---

### 3.8 UNIDOME: CAPA Record
لإدارة الإجراءات التصحيحية والوقائية.

| الحقل | النوع |
|-------|-------|
| project | Link → Project |
| source | Select: Site Inspection / FG QC / Customer Survey / Internal Audit |
| status | Select: Open / In Progress / Closed |
| vsm_flag | Check — مُعلَّم لمراجعة VSM السنوية |
| description | Text |
| root_cause | Text |
| corrective_action | Text |
| preventive_action | Text |
| responsible_party | Link → User |
| due_date | Date |

---

## 4. الحقول المخصصة (Custom Fields)

**الملف:** `fixtures/custom_field.json` — **43 حقل إجمالاً.**

### على Opportunity — حقول قديمة (module: null)

| fieldname | النوع | insert_after |
|-----------|-------|-------------|
| `custom_project_name` | Data | opportunity_owner |
| `custom_external_designer` | Link → Supplier | total |
| `custom_external_designer_items` | Section Break | custom_external_designer |
| `custom_external_items` | Table → External Item Details | custom_external_designer_items |

> **`custom_external_designer` و `custom_external_items` — `depends_on`/`mandatory_depends_on` (مُصلَح 2026-07-14):**
> كانا `eval:doc.sales_stage=="Preliminary Design Requested"` فقط — أي أن الحقلين يظهران/يصبحان إلزاميين فقط **بعد** دخول هذه الحالة، بينما دالة `_unidome_create_po_for_external_designer` (راجع 6.2) تتطلبهما **معبَّأين مسبقاً** لحظة تنفيذ انتقال "Request Preliminary Design" — تسلسل مستحيل عملياً عبر الواجهة (المستخدم لا يرى الحقل ليعبّئه قبل الضغط على الزر). أصبح الشرط: `eval:doc.sales_stage=='Qualified' || doc.sales_stage=='Preliminary Design Requested'` — يظهر الحقلان منذ حالة "Qualified" (خطوة واحدة قبل الطلب) ليتمكّن المستخدم من تعبئتهما قبل تنفيذ الانتقال.

### على Opportunity — حقول UNIDOME (module: UNIDOME)

**مجموعة بيانات المشروع:**

| fieldname | النوع |
|-----------|-------|
| `custom_unidome_project_data_section` | Section Break (Collapsible) |
| `custom_project_location` | Data |
| `custom_project_type` | Select: سكني / تجاري / صناعي |
| `custom_total_slab_area` | Float (م²) |
| `custom_num_floors` | Int |
| `custom_client_budget` | Currency |

**مجموعة مدخلات التصميم:**

| fieldname | النوع |
|-----------|-------|
| `custom_unidome_design_inputs_section` | Section Break (Collapsible) |
| `custom_preliminary_design_file` | Attach |
| `custom_preliminary_design_date` | Date |
| `custom_sla_design_due_date` | Date (Read Only — تُعيّنه السكريبت) |
| `custom_preliminary_design_notes` | Text |

**مجموعة مخرجات التصميم:**

| fieldname | النوع |
|-----------|-------|
| `custom_unidome_design_outputs_section` | Section Break (Collapsible) |
| `custom_unidome_qty` | Float |
| `custom_unidome_size` | Data — **الصنف الفعلي المُستخدَم في Material Request** (Script 20، راجع 6.3) والـ PO للمصمم الخارجي. ملاحظة 2026-07-24: كان حقل `module` له قد أُفرغ (NULL) بشكل غير مقصود خارج هذه الجلسة، مما أسقطه صامتاً من فلتر تصدير fixtures (`module = 'UNIDOME'`) — أُعيد ضبطه إلى `UNIDOME`. تحقّق من `tabCustom Field` مباشرة إذا لاحظت اختفاء حقل من fixture رغم عدم حذفه فعلياً. |
| `custom_steel_qty_kg` | Float |
| `custom_concrete_qty_m3` | Float |
| `custom_slab_thickness_mm` | Float |
| `custom_actual_desgined_area_m2` | Data — **⚠️ موجود في القاعدة فقط، غير مُصدَّر إلى `custom_field.json` (اكتُشف 2026-07-24)**. اسم الحقل به خطأ إملائي فعلي ("desgined" لا "designed") — استُخدم كما هو، لا تُصحّحه دون تنسيق (سيكسر أي كود/تقرير يشير إليه). يُستخدم كـ "الكمية المستلمة" في Purchase Receipt عند اعتماد التصميم المبدئي (راجع Script 17 في 6.2). نوعه Data وليس Float — يُحوَّل بـ `frappe.utils.flt()` عند الاستخدام. |

> **⚠️ حقلان حُذفا خارج هذه الجلسة (اكتُشف 2026-07-24 أثناء `export-fixtures`):** `custom_final_design_file` و`custom_final_boq_file` (Attach — مرفق التصميم النهائي وBOQ النهائي) لم يعودا موجودين كـ Custom Field على الإطلاق. **الأعمدة نفسها ما زالت موجودة في جدول `tabOpportunity`** وتحتوي بيانات فعلية (فرصتان لـ design_file، فرصة واحدة لـ boq_file) — البيانات غير مفقودة لكنها غير ظاهرة/غير قابلة للتعديل حالياً لعدم وجود تعريف الحقل. **قرار مقصود من المستخدم (2026-07-24): تُركا محذوفين عمداً ولم يُعاد إنشاؤهما.** لا تُعد إنشاءهما دون طلب صريح.

**مجموعة التحكم:**

| fieldname | النوع |
|-----------|-------|
| `custom_unidome_control_section` | Section Break (Collapsible) |
| `custom_contract_signed` | Check |
| `custom_contract_signed_date` | Date (depends_on: custom_contract_signed) |
| `custom_contract_file` | Attach (depends_on: custom_contract_signed) |
| `custom_lost_reason` | Small Text |
| `custom_unidome_opportunity_state` | Data (Read Only) — **حقل workflow الفرصة** |

### على Project (module: UNIDOME)

| fieldname | النوع |
|-----------|-------|
| `custom_unidome_project_section` | Section Break (Collapsible) |
| `custom_opportunity` | Link → Opportunity |
| `custom_total_area_m2` | Float |
| `custom_floor_number` | Int |
| `custom_final_design_due_date` | Date (Read Only) |
| `custom_cost_reconciliation_status` | Select: Pending / Passed / Failed - Margin / Failed - Scope Change |
| `custom_execution_completed_date` | Date |
| `custom_vsm_review_required` | Check |
| `custom_project_stage` | Data (Read Only) — **حقل workflow المشروع** — يُنشأ عبر patch |

> **⚠️ حقل مكرر مكتشَف 2026-07-24:** يوجد أيضاً حقل باسم **`opportunity`** (بدون `custom_`) على Project — Link → Opportunity، بنفس التسمية "الفرصة المرتبطة"، **موجود في القاعدة فقط وليس في `custom_field.json`**. على الأرجح بقايا محاولة سابقة. الحقلان الآن يُبقيان متزامنين معاً بواسطة `_set_project_opportunity_links()` في `sales_order.py` (راجع 5.2) عند إنشاء Project من Sales Order — لا تحذف أياً منهما دون التحقق من عدم استخدامه في تقرير/Client Script آخر.

> `custom_project_stage` لا يوجد في `custom_field.json` — يُنشأ عبر `patches/add_project_stage_field.py` لأنه مرتبط بـ Workflow.

### على Sales Order (module: UNIDOME)

| fieldname | النوع |
|-----------|-------|
| `custom_opportunity` | Link → Opportunity |
| `custom_floor_count` | Int |
| `custom_project_created` | Check (Read Only) |

### على Purchase Receipt (module: UNIDOME)

| fieldname | النوع |
|-----------|-------|
| `custom_opportunity` | Link → Opportunity |
| `custom_boq_created` | Check (Read Only) |

### على Purchase Order Item (module: null — قديم)

| fieldname | النوع |
|-----------|-------|
| `custom_note` | Small Text |

---

## 5. Python Hooks — الملفات والأحداث

### 5.1 doc_events الكاملة (hooks.py)

```python
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
        "validate"     : "huge_app.custom.sales_order.sales_order.validate",
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

scheduler_events = {
    "daily": [
        "huge_app.custom.scheduled_tasks.run"
    ]
}
```

### 5.2 جدول الملفات والوظائف الكامل

| الملف | الحدث | الوظيفة |
|-------|-------|---------|
| `custom/lead/lead.py` | Lead on_update | Script 1: Lead محوّل → Opportunity جديدة في "Needs Analysis" |
| `custom/opportunity/opportunity.py` | Opportunity on_update | Outsourced Designer: إنشاء/إلغاء PO + Scripts 2,3,4,8,17,18 |
| `custom/sales_order/sales_order.py` | SO validate | Script 19: تعبئة `custom_opportunity` من الـ Quotation المصدر إن كان فارغاً |
| `custom/sales_order/sales_order.py` | SO before_submit | Script 5: التحقق من توقيع العقد ووجود Quotation مُسلَّم |
| `custom/sales_order/sales_order.py` | SO on_submit | Script 6: إنشاء Project + 13 مهمة + فاتورة Kickoff 30% |
| `custom/project/project.py` | Project after_insert | إنشاء Cost Center + Site Warehouse تلقائياً |
| `custom/project/project.py` | Project on_update | Scripts 7,9,10,14,20: SLA + تسوية التكلفة + MR (من BOQ الفرصة، ومن دخول Material Planning) + فاتورة التسليم |
| `custom/purchase_receipt/purchase_receipt.py` | PR on_submit | تحديث prelim_design_status في الفرصة |
| `custom/purchase_receipt/purchase_receipt.py` | PR on_update | إنشاء Project BOQ عند `review_status == "Approved"` (Final Design Review Flow — راجع 6.4) |
| `custom/material_request/material_request.py` | MR before_save | BOM Optimizer: اختيار أفضل BOM مقابل المخزون |
| `custom/work_order/work_order.py` | WO on_submit | Script 11: سلسلة WO (Shield → Unifix → Unidome → 4-Module → FG) |
| `custom/delivery_note/delivery_note.py` | DN on_submit | Script 13: Stock Entry (Material Issue) + إشعار العميل + Project = Shipped |
| `custom/fg_qc_inspection/fg_qc_inspection.py` | FGQ on_submit | Script 12: Accept→DN / Reject→NCR+WO جديد+إشعار |
| `custom/customer_satisfaction_survey/customer_satisfaction_survey.py` | CSS on_submit | Script 16: تقييم منخفض أو عنصر حرج → CAPA تلقائي |
| `custom/scheduled_tasks.py` | يومياً | Script 15: مشاريع D+30 → فاتورة 10% + استبيان + Snag Task |

### 5.3 قواعد بنية الكود

- **كل الكود داخل دوال** — لا يجوز وجود `doc` أو `frappe` على مستوى الـ module.
- **Guard لمنع الحلقات اللانهائية:** `if doc.flags.ignore_unidome_hooks: return` في أول كل دالة hook رئيسية.
- **عند إنشاء doc داخل hook:** ضع `new_doc.flags.ignore_unidome_hooks = True` قبل `insert()`.
- **بنية الدالة:** `def on_submit(doc, method=None):` — `method` اختياري دائماً.
- **Helper للـ logging:** `_log = lambda msg: frappe.logger("huge_app").info(msg)` — مُعرَّف في كل ملف.

---

## 6. Workflows

### 6.1 Outsourced Designer Workflow (قديم — مُعطَّل)
- **DocType:** Opportunity
- **workflow_state_field:** `workflow_state`
- **الحالة في ERPNext:** مُعطَّل — لا تُعيد تفعيله
- **الكود المقابل:** `custom/opportunity/opportunity.py` — دوال `_handle_workflow_approved` و `_handle_workflow_rejected`
- **ملاحظة:** حقل الربط بين PO والفرصة هو `opportunity` (بدون `custom_`)

---

### 6.2 UNIDOME Opportunity Workflow (فعّال)
- **DocType:** Opportunity
- **workflow_state_field:** `custom_unidome_opportunity_state`
- **الملف:** `fixtures/workflow.json`
- **الأدوار:** UNIDOME Sales User, UNIDOME Sales Manager, UNIDOME Operations User, UNIDOME Technical Manager

**الحالات الـ 13:**

| الحالة | الدور المسموح له بالتعديل |
|--------|--------------------------|
| Needs Analysis | UNIDOME Sales User |
| Qualification Review | UNIDOME Sales Manager |
| Qualified | UNIDOME Sales User |
| Preliminary Design Requested | UNIDOME Operations User |
| Preliminary Design Received | UNIDOME Technical Manager |
| Preliminary Design Review | UNIDOME Technical Manager |
| Costing and Saving Analysis | UNIDOME Technical Manager |
| Quotation Ready | UNIDOME Sales User |
| Quotation Sent | UNIDOME Sales User |
| Negotiation/Review | UNIDOME Sales Manager |
| Closed Won | UNIDOME Sales Manager |
| Closed Lost | UNIDOME Sales Manager |
| Design Revision Required | UNIDOME Operations User |

**الانتقالات الـ 16:**
```
Needs Analysis              →[Submit for Qualification]→      Qualification Review
Qualification Review        →[Approve]→                       Qualified
Qualification Review        →[Reject]→                        Needs Analysis
Qualified                   →[Request Preliminary Design]→    Preliminary Design Requested
Preliminary Design Requested→[Mark Received]→                 Preliminary Design Received
Preliminary Design Received →[Submit for Review]→             Preliminary Design Review
Preliminary Design Review   →[Approve Preliminary Design]→    Costing and Saving Analysis
Preliminary Design Review   →[Reject - Request Revision]→     Preliminary Design Requested
Preliminary Design Review   →[Request Design Revision]→       Design Revision Required
Design Revision Required    →[Re-request Design]→             Preliminary Design Requested
Costing and Saving Analysis →[Approve Costing]→               Quotation Ready
Quotation Ready             →[Send Quotation]→                Quotation Sent
Quotation Sent              →[Mark as Under Negotiation]→     Negotiation/Review
Negotiation/Review          →[Revise Pricing]→                Costing and Saving Analysis
Negotiation/Review          →[Mark Won]→                      Closed Won
Negotiation/Review          →[Mark Lost]→                     Closed Lost
```

**الأتمتة المرتبطة بتغيّر `custom_unidome_opportunity_state`:**

| الحالة الجديدة | الإجراء |
|----------------|---------|
| Preliminary Design Requested | **إنشاء وتسليم Purchase Order** للمصمم الخارجي (`custom_external_designer` + `custom_external_items`) + SLA 5 أيام عمل + إيميل لـ External Designer |
| Costing and Saving Analysis (قادماً تحديداً من Preliminary Design Review — أي بعد action "Approve Preliminary Design") | **إنشاء Purchase Receipt تلقائياً** (Script 17، أُضيف 2026-07-24) — يمثّل استلام التصميم المبدئي من المصمم الخارجي مقابل الـ Purchase Order الموجود؛ الكمية المستلمة = `custom_actual_desgined_area_m2` (**إلزامي التعبئة قبل تنفيذ الموافقة وإلا يُرفض الانتقال**) |
| Quotation Ready | إنشاء Quotation مسودة تلقائياً — **الأصناف حقيقية** (item_code/qty/rate من جدول `items` في الفرصة نفسها، مُصلَح 2026-07-24 — كانت صنفاً وهمياً ثابتاً برعر=0) |
| Closed Lost | إلزامية تعبئة `custom_lost_reason` |
| Costing and Saving Analysis | التحقق من اكتمال حقول BOQ النهائي |

**Script 18 (أُضيف 2026-07-24) — مزامنة سعر `custom_external_items` من Price List المورد:** عند كل حفظ للفرصة، إذا كان `custom_external_designer` مضبوطاً وله `default_price_list`، يُستبدَل سعر كل صف في `custom_external_items` **دائماً** (استبدال، وليس تعبئة عند الفراغ فقط) بالسعر من Item Price المطابق لذلك الصنف في تلك القائمة — مع تفضيل سعر خاص بالمورد نفسه، والرجوع لسعر عام إن لم يوجد. **ملاحظة تقنية:** لا يُستخدَم `erpnext.stock.get_item_details.get_item_price` مباشرة لأنه يُصفّي حسب UOM، وجدول `External Item Details` لا يملك حقل UOM إطلاقاً — الاستعلام مكتوب يدوياً (`_get_item_price_list_rate`) لتفادي هذا. يعمل قبل إنشاء الـ PO في نفس دورة `on_update` كي يستخدم الـ PO السعر الصحيح مباشرة.

> **إنشاء PO (مُصلَح 2026-07-13):** الدالة `_unidome_create_po_for_external_designer` في `opportunity.py` — تُنشأ عند الدخول الفعلي لحالة "Preliminary Design Requested" (وليس عند تكرارها). تتحقق من عدم وجود PO سابق غير ملغى لنفس الفرصة، وتُلزم بوجود `custom_external_designer` و `custom_external_items` وإلا `frappe.throw`. تضبط `warehouse` تلقائياً (`Stores - {company_abbr}`) لأن أصناف PO قد تكون Stock Items تتطلب مستودعاً. **آلية "Outsourced Designer" القديمة (`_handle_workflow_approved` تعتمد على حقل `workflow_state` المخفي) أصبحت كوداً ميتاً فعلياً** — الـ Workflow نفسه `is_active=0` ولا توجد أزرار في الواجهة تُغيّر `workflow_state` — لم تُحذف لكنها لن تُستدعى أبداً بالاستخدام العادي.

---

### 6.3 UNIDOME Project Workflow (فعّال — جديد)
- **DocType:** Project
- **workflow_state_field:** `custom_project_stage`
- **الملف:** `fixtures/project_workflow.json`
- **الأدوار:** Projects Manager, UNIDOME External Designer, UNIDOME Technical Manager, UNIDOME Operations Manager, UNIDOME Factory User, UNIDOME Finance User

**الحالات الـ 11:**

| الحالة | الدور المسموح له بالتعديل |
|--------|--------------------------|
| Project Initiated | Projects Manager |
| Final Design | UNIDOME External Designer |
| Design Review | UNIDOME Technical Manager |
| Final Design Approved | UNIDOME Technical Manager |
| Material Planning | Projects Manager |
| Manufacturing | UNIDOME Factory User |
| Site Execution | Projects Manager |
| Project Closure | Projects Manager |
| Final Cost Analysis | UNIDOME Finance User |
| Invoice & Collection | UNIDOME Finance User |
| Completed | UNIDOME Finance User |

**الانتقالات الـ 11:**
```
Project Initiated    →[Start Final Design]→        Final Design
Final Design         →[Submit for Design Review]→  Design Review
Design Review        →[Approve Final Design]→       Final Design Approved
Design Review        →[Reject - Request Revision]→  Final Design          ← حلقة رفض
Final Design Approved→[Start Material Planning]→   Material Planning
Material Planning    →[Approve Material Plan]→      Manufacturing
Manufacturing        →[Complete Manufacturing]→     Site Execution
Site Execution       →[Complete Site Execution]→    Project Closure
Project Closure      →[Close Project Technically]→  Final Cost Analysis
Final Cost Analysis  →[Approve Cost Analysis]→      Invoice & Collection
Invoice & Collection →[Confirm Payment]→            Completed
```

> **تحديث 2026-07-24:** أول أتمتة مرتبطة فعلياً بتغيّر `custom_project_stage` أُضيفت (Script 20): عند الدخول إلى حالة **Material Planning**، يُنشأ Material Request تلقائياً — الصنف = `custom_unidome_size` من الفرصة المرتبطة، الكمية = `custom_unidome_qty` مطروحاً منها المتوفر فعلياً في مستودع `Stores - {abbr}` (عبر Bin). لا يُنشئ MR إذا لم يوجد صنف/كمية، أو إذا كان الصنف غير موجود فعلياً في Item master، أو إذا وُجد MR سابق غير ملغى لنفس المشروع. باقي حالات هذا الـ workflow (Final Design, Design Review, Manufacturing, ...) لا تزال بدون منطق Python مرتبط — لم يُنفَّذ بعد.
>
> **⚠️ خلل مُصلَح في نفس الأتمتة (Script 10 القديم، كان مُعطَّلاً فعلياً منذ إنشائه):** كان يستخدم أصنافاً وهمية غير موجودة إطلاقاً (`Unidome Unit`, `Steel Rebar`) وكان يحاول ضبط/استعلام حقل `project` مباشرة على **Material Request نفسها** — هذا الحقل **غير موجود على الإطلاق** على الـ parent doctype، فقط على child table **`Material Request Item`**. أي استدعاء سابق لهذه الدالة كان يرمي `OperationalError: Unknown column 'project'` فور محاولة فحص التكرار. أُصلح ليضبط `project` على صف الصنف، ويتحقق من التكرار عبر `frappe.get_all(..., filters=[["Material Request Item", "project", "=", ...]])`.

### 6.4 Final Design Review Flow (فُعِّل 2026-07-13 — Purchase Receipt)

> **تمييز مهم عن Script 17 (راجع 6.2):** يوجد الآن مساران مختلفان ينشئان/يديران Purchase Receipt مرتبطاً بالفرصة عبر `custom_opportunity` — لا تخلط بينهما:
> - **هذا القسم (6.4):** PR **يدوي** يمر بـ workflow خاص بحقل `review_status`، يمثّل **التصميم النهائي** (بعد BOQ)، وينتهي بإنشاء Project BOQ عند اعتماده.
> - **Script 17 (6.2):** PR يُنشأ **تلقائياً بالكامل** (بدون أي تدخل يدوي أو workflow خاص به) عند اعتماد **التصميم المبدئي** (Preliminary Design Review → Costing and Saving Analysis)، ويُسلَّم (submit) مباشرة عبر الكود.
- **DocType:** Purchase Receipt
- **workflow_state_field:** `review_status` (Select، ليس `workflow_state` القياسي)
- **الأدوار:** Technical Manager, Design Auditor, Project Manager, External Designer (أدوار قديمة غير مسبوقة بـ UNIDOME — ليست ضمن الـ 10 أدوار في القسم 7)

**الحالات الـ 5:**

| الحالة | doc_status المطلوب | الدور المسموح له بالتعديل |
|--------|---------------------|---------------------------|
| Pending Review | 0 (Draft) | Technical Manager |
| Auditor Review | 0 (Draft) | Design Auditor |
| Pending Client Approval | 0 (Draft) | Project Manager |
| Approved | 1 (Submitted) | Technical Manager |
| Rejected — Revision | 0 (Draft) | External Designer |

**الانتقالات:**
```
Pending Review           →[Send to Auditor]→            Auditor Review
Auditor Review           →[Auditor Approves]→            Pending Client Approval
Auditor Review           →[Auditor Rejects]→             Rejected — Revision
Pending Client Approval  →[Client Approves]→             Approved   ← يُسلَّم PR تلقائياً (docstatus→1)
Pending Client Approval  →[Client Requests Change]→      Rejected — Revision
Rejected — Revision      →[Resubmit Revised Design]→     Pending Review
```

> **تحذير مهم — PR يجب أن يُنشأ كـ Draft (بدون submit) ليدخل الـ workflow.** استدعاء `pr.submit()` يدوياً قبل المرور بحالات المراجعة سيفشل بخطأ "Illegal Document Status" لأن حالتَي "Auditor Review" و"Pending Client Approval" تتطلبان docstatus=0. الـ submit الفعلي يحدث تلقائياً عند تنفيذ انتقال "Client Approves".

**كانت هذه الآلية كوداً معطَّلاً بالكامل (`is_active=0`) وبها 3 أخطاء صُحِّحت عند تفعيلها:**
1. `purchase_receipt.py on_update` كان يقرأ `doc.workflow_state` (حقل **غير موجود إطلاقاً** على Purchase Receipt) → كان يُسبب `AttributeError` عند **أي** حفظ لأي Purchase Receipt في النظام. الحقل الصحيح هو `review_status`.
2. حقل `review_status` (Select) كانت خياراته (`Pending Review/Approved/Rejected`) لا تغطي كل حالات الـ workflow (ناقصة: `Auditor Review`, `Pending Client Approval`) → أُضيفت كل الحالات الخمس لخيارات الحقل.
3. حقل `project` في Project BOQ كان `reqd=1` رغم أن BOQ يُنشأ في مرحلة سابقة لوجود Project أصلاً → أصبح اختيارياً (راجع القسم 3.1).
كما استُبدلت أسطر تضبط حقولاً غير موجودة على Project BOQ (company/customer/project_name/purchase_receipt/date/unidome_supplier/steel_supplier/concrete_supplier) بحقول حقيقية فقط (opportunity/project/total_slab_area_m2/status/notes).

**تم التحقق end-to-end عبر bench console:** PR (Draft) → Auditor Review → Pending Client Approval → Client Approves (submit تلقائي) → Project BOQ يُنشأ بنجاح.

---

### 6.5 Monkeypatches على ERPNext الأساسي (`huge_app/__init__.py`) — أُضيفت 2026-07-24

اكتُشفت خلال التشخيص أخطاء حقيقية في **erpnext نفسه** (وليس في huge_app) تُسبب تكرار سجلات Customer عند إنشاء Sales Order من Quotation مرتبط بـ Prospect. بما أنه لا يجوز تعديل كود core مباشرة (يُفقد عند تحديث erpnext)، طُبِّق الإصلاح كـ monkeypatch في `huge_app/__init__.py` — يُنفَّذ مرة واحدة تلقائياً عند تحميل التطبيق (عند بدء كل عملية Python)، وليس عبر doc_events:

1. **`erpnext.crm.doctype.prospect.prospect.make_customer`** — الدالة الأصلية **لا تضبط `Customer.prospect_name` إطلاقاً** عند تحويل Prospect إلى Customer (بعكس تدفق Lead المكافئ الذي يضبط `Customer.lead_name` بشكل صحيح عبر `field_map`). بدون هذا الحقل، دالة `Quotation._make_customer` في erpnext لا تستطيع أبداً إيجاد Customer موجود مسبقاً لنفس الـ Prospect، فتُنشئ نسخة جديدة **في كل مرة** يُضغط فيها "Create > Sales Order". الـ patch يضبط `customer.prospect_name = source_name` على الوثيقة قبل `insert()`.

2. **`erpnext.selling.doctype.quotation.quotation._make_customer`** — طبقة حماية إضافية (belt-and-suspenders): حتى لو كان حقل الربط (`prospect_name`/`lead_name`) فارغاً، أو تم حذف السجل المرتبط لاحقاً، **لا يُنشئ عميلاً جديداً أبداً** إذا وُجد أي Customer آخر بنفس `customer_name` تماماً — يُعيد استخدامه بدلاً من ذلك. **قرار مقصود (بناءً على طلب المستخدم):** المطابقة بالاسم حرفياً — إذا وُجدت فعلياً شركتان مختلفتان بنفس الاسم تماماً، ستُعامَلان كعميل واحد.

**آلية العمل الفنية:** كلا الـ patch يستبدل الدالة على مستوى الـ **module attribute** (`module.func_name = new_func`)، وليس عبر تعديل الملف المصدر لـ erpnext. هذا يعمل بشكل موثوق لأن الاستدعاءات الداخلية في erpnext (سواء عبر `from x import y` محلي داخل دالة، أو مرجع عام على مستوى الملف) تُحل الاسم من الـ module's `__dict__` وقت **التنفيذ** وليس وقت **التعريف** — فتلتقط النسخة المُصلَحة تلقائياً.

> **⚠️ ملاحظة تشغيلية حرجة:** بما أن هذا كود يُنفَّذ عند **تحميل التطبيق فقط**، أي تعديل عليه يتطلب **إعادة تشغيل كاملة (`kill -TERM`)** — راجع التحذير في القسم 1 عن عدم موثوقية `kill -HUP` هنا بسبب `--preload`. اكتُشف هذا فعلياً أثناء الجلسة: نفس الإصلاح بدا يعمل أحياناً ويفشل أحياناً أخرى حسب أي worker استقبل الطلب، إلى أن استُخدم `kill -TERM`.

> **تحقيق جانبي مهم للتشخيص المستقبلي:** لوحظ تكرار "اختفاء" عميل تم إصلاحه بشكل صحيح (`prospect_name` مضبوط) بين محاولات اختبار متتالية للمستخدم. التحقق عبر جدول `tabDeleted Document` أثبت أن السبب هو **حذف يدوي متكرر من حساب Administrator** أثناء اختبار المستخدم لنفس المشكلة (وليس خللاً في منطق الـ dedup نفسه). **عند تشخيص مشاكل تكرار مشابهة مستقبلاً، تحقق أولاً من `tabDeleted Document` قبل افتراض وجود خلل في الكود:**
> ```sql
> SELECT name, deleted_doctype, deleted_name, owner, creation
> FROM `tabDeleted Document`
> WHERE deleted_doctype='Customer' AND deleted_name LIKE '%...%'
> ORDER BY creation DESC;
> ```

---

## 7. الأدوار (Roles)

**الملف:** `fixtures/role.json` — 10 أدوار UNIDOME:

| الدور | الغرض |
|-------|--------|
| UNIDOME Sales User | مندوب المبيعات — يُدير الفرص والعروض |
| UNIDOME Sales Manager | مدير المبيعات — الاعتماد والمفاوضات |
| UNIDOME Operations User | مسؤول العمليات — استلام التصاميم |
| UNIDOME Operations Manager | مدير العمليات — إشراف وتصعيد SLA |
| UNIDOME Technical Manager | المدير التقني — مراجعة واعتماد التصاميم |
| UNIDOME External Designer | المصمم الخارجي — يستلم طلبات التصميم |
| UNIDOME Factory User | موظف المصنع — متابعة Work Orders |
| UNIDOME Site Engineer | مهندس الموقع — تقارير التدقيق |
| UNIDOME Finance User | المحاسب — الفواتير والمستحقات |
| UNIDOME Quality Inspector | مفتش الجودة — QC و CAPA |

---

## 8. Server Scripts في قاعدة البيانات

| الاسم | الحدث | DocType | الحالة | ملاحظة |
|-------|-------|---------|--------|--------|
| Unidome: BOM Optimizer API | API | — | **فعّال** | API endpoint — لا مقابل Python له |
| Unidome: MR Trigger BOM Optimizer | After Save | Material Request | **مُعطَّل** | يُغطّيه `material_request.py` |
| Unidome: Opportunity Cost Transfer on Close | After Save | Opportunity | **مُعطَّل** | مُعطَّل عمداً — **لا تُعيد تفعيله أبداً** |
| Unidome: PR Approved Creates BOQ | After Save | Purchase Receipt | **مُعطَّل** | يُغطّيه `purchase_receipt.py` (يعمل الآن فعلياً بعد تفعيل Final Design Review Flow — راجع 6.4) |
| Unidome: PR Submit Updates Opportunity | After Submit | Purchase Receipt | **مُعطَّل** | يُغطّيه `purchase_receipt.py` |
| Unidome: Project Auto CC and Warehouse | After Insert | Project | **مُعطَّل** | يُغطّيه `project.py` |
| Unidome: Sales Order Creates Project | After Submit | Sales Order | **مُعطَّل** | يُغطّيه `sales_order.py` |

> **قاعدة صارمة:** لا تُعيد تفعيل أي Server Script له مقابل في Python hooks.

---

## 9. Fixtures في hooks.py

```python
fixtures = [
    "Role",
    {"dt": "Workflow Action Master", "filters": [["workflow_action_name", "in", [
        "Submit for Qualification", "Request Preliminary Design", "Mark Received",
        "Submit for Review", "Approve Preliminary Design", "Reject - Request Revision",
        "Request Design Revision", "Re-request Design", "Approve Costing",
        "Send Quotation", "Mark as Under Negotiation", "Revise Pricing",
        "Mark Won", "Mark Lost",
        "Start Final Design", "Submit for Design Review", "Approve Final Design",
        "Start Material Planning", "Approve Material Plan", "Complete Manufacturing",
        "Complete Site Execution", "Close Project Technically",
        "Approve Cost Analysis", "Confirm Payment"
    ]]]},
    {
        "dt": "Custom Field",
        "filters": [["name", "in", [
            "Opportunity-custom_project_name",
            "Opportunity-custom_external_designer",
            "Opportunity-custom_external_designer_items",
            "Opportunity-custom_external_items",
            "Purchase Order Item-custom_note",
        ]]]
    },
    {
        "dt": "Custom Field",
        "filters": [["module", "=", "UNIDOME"]]
    },
    {
        "dt": "Workflow",
        "filters": [["name", "in", ["UNIDOME Opportunity Workflow", "UNIDOME Project Workflow"]]]
    },
    {"dt": "Workflow State"},
    {
        "dt": "Notification",
        "filters": [["name", "like", "UNIDOME WF Notify:%"]]
    },
]
```

> **ملاحظة fixtures — Frappe v15:**
> - `Workflow` → الـ JSON يجب أن يحتوي على `workflow_name` (مصدر autoname)
> - `Workflow State` → الـ JSON يجب أن يحتوي على `workflow_state_name`
> - `Workflow Action Master` → الـ JSON يجب أن يحتوي على `workflow_action_name`
> - `Project Template` → لا يُستخدم كـ fixture — يُنشأ عبر patch (يعتمد على Task records)
> - `Notification` (تنبيهات الـ workflow) → يُنشأ عبر patch (راجع القسم 11.1)، ثم يُصدَّر كـ fixture بفلتر `name like "UNIDOME WF Notify:%"`

> **⚠️ حقول مخصصة موجودة في القاعدة فقط، غير مُصدَّرة (اكتُشفت 2026-07-24):** `Opportunity.custom_actual_desgined_area_m2` و`Project.opportunity` (بدون `custom_`) — على الأرجح أُنشئا يدوياً عبر Customize Form في وقت ما ولم يُصدَّرا. **لا تفترض أن `custom_field.json` يحتوي كل الحقول الفعلية** — تحقّق دائماً من `tabCustom Field` مباشرة في القاعدة عند الشك. يجب تصديرهما لاحقاً عبر `bench export-fixtures --app huge_app` إذا أُريد نشرهما على بيئة جديدة.

---

## 9.1 تنبيهات الـ Workflow (System Notification + Email) — أُضيفت 2026-07-14

**الملف:** `patches/create_workflow_notifications.py` (مسجَّل في `patches.txt`) — يُنشئ سجلّ `Notification` واحداً لكل حالة من حالتَي الـ workflow الفعّالين × قناتين (System Notification + Email) = **48 سجلاً** (26 لـ Opportunity's 13 حالة، 22 لـ Project's 11 حالة).

**الآلية لكل سجل:**
- `document_type`: Opportunity أو Project
- `event`: "Value Change"، `value_changed`: `custom_unidome_opportunity_state` أو `custom_project_stage`
- `condition`: `doc.<field> == '<state>'` — يمنع التكرار عند إعادة الحفظ لأن Frappe يتحقق أن القيمة تغيّرت فعلاً (Value Change event)
- `recipients`: صف واحد بـ `receiver_by_role` = دور الـ `allow_edit` لتلك الحالة (نفس الأدوار الموثقة في القسمين 6.2 و6.3)
- التسمية: `UNIDOME WF Notify: <Opportunity|Project> - <State> (<Channel>)`

**لإعادة التوليد بعد تعديل حالات/أدوار الـ workflow:**
```bash
bench --site erp.huge.ps execute huge_app.patches.create_workflow_notifications.execute
bench --site erp.huge.ps export-fixtures
```
الدالة idempotent — تتخطى أي اسم موجود مسبقاً، فلا تُنشئ تكراراً. عند تغيير حالة موجودة يجب حذف سجلّها القديم يدوياً قبل إعادة التشغيل ليُعاد إنشاؤه بالقيم الجديدة.

**تنبيهات قديمة معطَّلة عمداً (كانت كوداً ميتاً، أُبقيت للتاريخ لا للحذف):**
`Unidome: Pending Qualification`, `Unidome: Design Requested`, `Unidome: Design Received` — كانت تقرأ `doc.workflow_state` (حقل الـ Outsourced Designer الميت، وليس `custom_unidome_opportunity_state`) بقيم حالات لا تطابق أصلاً الـ workflow الفعّال. عُطِّلت (`enabled=0`) في 2026-07-14 بدل حذفها.

---

## 10. Project Template — Unidome Project Template

يُنشأ تلقائياً عبر الـ patch script عند `bench migrate`.
**الملف:** `patches/create_unidome_project_template.py`
**الحالة:** مُنفَّذ ومُثبَّت في قاعدة البيانات ✓

### المهام الـ 13 (إجمالي المشروع ~66 يوم):

| # | المهمة | يبدأ (يوم) | المدة | Milestone |
|---|--------|-----------|-------|-----------|
| 1 | تأهيل الفرصة | 0 | 3 أيام | — |
| 2 | التصميم المبدئي | 3 | 7 أيام | — |
| 3 | المراجعة الفنية | 10 | 3 أيام | — |
| 4 | التسعير والتفاوض | 13 | 5 أيام | — |
| 5 | ★ توقيع العقد | 18 | 2 يوم | ✓ دفعة 30% |
| 6 | التصميم النهائي | 20 | 10 أيام | — |
| 7 | ★ اعتماد التصميم | 30 | 3 أيام | ✓ |
| 8 | تخطيط الموارد | 33 | 4 أيام | — |
| 9 | التصنيع | 37 | 14 يوم | — |
| 10 | فحص جودة المنتج النهائي | 51 | 2 يوم | — |
| 11 | ★ الشحن | 53 | 2 يوم | ✓ |
| 12 | التنفيذ الميداني | 55 | 7 أيام | — |
| 13 | ★ الإغلاق والتسليم | 62 | 2 يوم | ✓ استبيان D+30 |

### كيف يعمل الـ Patch:
1. ينشئ 13 Task بـ `status="Template"`, `is_template=1`, بدون project
2. ينشئ Project Template باسم `"Unidome Project Template"` ويربط التاسكات به
3. آمن للتكرار — يتخطى إذا Template موجود مسبقاً

### استخدام الـ Template:
- `sales_order.py` يُسمّي الثابت `TEMPLATE_NAME = "Unidome Project Template"`
- عند إنشاء Project من SO → `project.project_template = TEMPLATE_NAME`
- ERPNext يُنشئ نسخ من التاسكات تلقائياً مع تواريخ محسوبة من `expected_start_date`

---

## 11. UNIDOME — منطق الفواتير الميلستون

يُنشئ التطبيق 4 فواتير مسودة تلقائياً على مدار دورة حياة المشروع:

| الفاتورة | النسبة | المُشغِّل |
|---------|--------|-----------|
| Kickoff | 30% | SO on_submit (Script 6) |
| انطلاق المشروع | 30% | Project: cost_reconciliation_status = "Passed" (Script 9) |
| التسليم | 30% | Project: status = "Execution Completed" (Script 14) |
| الثبات (Retention) | 10% | Scheduled Job: D+30 من اكتمال التنفيذ (Script 15) |

**كل الفواتير:** مسودة (Draft) — لا تُرسَل تلقائياً. تستخدم أول بند من SO بسعر معدَّل.

---

## 12. UNIDOME — سلسلة Work Orders

```
Shield Assembly BOM → [on_submit Completed] → Unifix Assembly
Unifix Assembly     → [on_submit Completed] → Unidome Production
Unidome Production  → [on_submit Completed] → 4-Unidome Module
4-Unidome Module    → [on_submit Completed] → Stock Entry: Material Transfer → FG Warehouse
```

**شرط التشغيل:** `doc.status == "Completed"` + اسم `production_item` يطابق تسلسل WO_SEQUENCE في `work_order.py`.
**إذا لم يُوجد BOM:** تتوقف السلسلة وتُسجّل خطأ في Error Log.

---

## 13. حقول Project — Standard vs Custom

| الحقل | الموقف الصحيح |
|-------|--------------|
| `cost_center` | Standard Field — استخدمه مباشرة |
| `expected_cost` | Standard Field |
| `customer` | Standard Field |
| `sales_order` | Standard Field — ربط SO بالمشروع |
| `custom_opportunity` | Custom Field (UNIDOME) — ربط Opportunity |
| `custom_cost_reconciliation_status` | Custom Field (UNIDOME) — بوابة MR والفواتير |
| `custom_project_stage` | Custom Field (UNIDOME) — حقل workflow المشروع |

---

## 14. أوامر شائعة

```bash
# تطبيق migrations بعد إضافة DocTypes أو Custom Fields أو Patches
bench --site erp.huge.ps migrate

# تصدير fixtures
bench --site erp.huge.ps export-fixtures --app huge_app

# تنظيف cache
bench --site erp.huge.ps clear-cache

# تنفيذ patch يدوياً (للاختبار)
bench --site erp.huge.ps execute huge_app.patches.create_unidome_project_template.execute
bench --site erp.huge.ps execute huge_app.patches.add_project_stage_field.execute

# فحص syntax لجميع ملفات custom
python3 -m py_compile \
  apps/huge_app/huge_app/custom/lead/lead.py \
  apps/huge_app/huge_app/custom/opportunity/opportunity.py \
  apps/huge_app/huge_app/custom/sales_order/sales_order.py \
  apps/huge_app/huge_app/custom/project/project.py \
  apps/huge_app/huge_app/custom/work_order/work_order.py \
  apps/huge_app/huge_app/custom/delivery_note/delivery_note.py \
  apps/huge_app/huge_app/custom/fg_qc_inspection/fg_qc_inspection.py \
  apps/huge_app/huge_app/custom/customer_satisfaction_survey/customer_satisfaction_survey.py \
  apps/huge_app/huge_app/custom/scheduled_tasks.py \
  apps/huge_app/huge_app/custom/purchase_receipt/purchase_receipt.py \
  apps/huge_app/huge_app/custom/material_request/material_request.py \
  apps/huge_app/huge_app/hooks.py

# إعادة تحميل gunicorn بعد تعديل .py — استخدم TERM دائماً (HUP غير موثوق هنا، راجع القسم 1)
kill -TERM $(pgrep -f "gunicorn -b 127.0.0.1" | head -1)

# فحص وجود عناصر في قاعدة البيانات
bench --site erp.huge.ps execute "frappe.db.sql" \
  --args '["SELECT name FROM tabWorkflow WHERE document_type=\"Project\""]'
bench --site erp.huge.ps execute "frappe.db.exists" \
  --args '["Project Template", "Unidome Project Template"]'

# الاتصال بقاعدة البيانات
python3 -c "
import json, subprocess
cfg = json.load(open('sites/erp.huge.ps/site_config.json'))
subprocess.run(['mysql', '-u', 'db_huge', f\"-p{cfg['db_password']}\", cfg['db_name']])
"

# فحص سجل الأخطاء
tail -f sites/erp.huge.ps/logs/frappe.log
tail -f logs/web.error.log
```

---

## 15. قواعد التطوير

1. **اقرأ الكود الفعلي أولاً** قبل افتراض أسماء الحقول أو بنية البيانات.
2. **لا تستخدم `bench restart`** — يحتاج sudo غير متاح. استخدم `kill -TERM` (راجع القاعدة 21 — `kill -HUP` غير موثوق هنا).
3. **لا تُعيد تفعيل أي Server Script** مُعطَّل — خاصةً "Unidome: Opportunity Cost Transfer on Close".
4. **guard الحلقات:** `if doc.flags.ignore_unidome_hooks: return` أول شيء في كل hook. عند إنشاء doc جديد: `new_doc.flags.ignore_unidome_hooks = True` قبل `insert()`.
5. **Outsourced Designer workflow:** يقرأ `doc.workflow_state` — الربط بين PO والفرصة عبر `opportunity` (بدون `custom_`).
6. **UNIDOME Opportunity workflow:** يقرأ `doc.custom_unidome_opportunity_state`. **UNIDOME Project workflow:** يقرأ `doc.custom_project_stage`. لا تخلط بين الحقلين.
7. **بعد تعديل أي `.py`** → `kill -TERM` لإعادة التحميل (راجع القاعدة 21).
8. **DocTypes في `doctype/`:** لا تحذف مجلد أي DocType وإلا سيُحذف من DB عند `migrate`.
9. **ملفات `custom/`** لا تحتاج `__init__.py` — Python 3.3+ namespace packages.
10. **لا تكتب كوداً على مستوى الـ module** — كل المنطق داخل دوال hook.
11. **إضافة hook جديد:** (أ) دالة في `.py`، (ب) تسجيل في `hooks.py → doc_events`.
12. **لا تُنشئ Custom Field لحقل موجود افتراضياً** — تحقق بـ `frappe.get_meta` أولاً.
13. **Business days في الأردن:** يوم الجمعة = weekday 4، يوم السبت = weekday 5 — كلاهما عطلة. راجع دالة `_add_business_days()` في `opportunity.py` و `project.py`.
14. **فواتير الميلستون:** تستخدم `so.items[0]` كبند قالب بسعر معدَّل — لا تُعدِّل qty أو so_detail لتجنّب تعارض التحقق من الكميات المفوترة.
15. **`frappe.log_error` في Frappe v15:** الوسيط الأول هو العنوان (title، حد أقصى 140 حرف)، الثاني هو الرسالة. للرسائل المعلوماتية استخدم `frappe.logger("huge_app").info(msg)` — أو اختصاراً `_log(msg)`.
16. **Fixtures بـ autoname مُركَّب:** doctypes مثل Workflow وWorkflow State وWorkflow Action Master تطلب حقل اسمها الصريح داخل الـ JSON إضافةً إلى `name` (`workflow_name`, `workflow_state_name`, `workflow_action_name`).
17. **Project Template:** لا يُستخدم كـ fixture — يجب إنشاء Task records أولاً ثم ربطها بالـ Template. استخدم دائماً patch script لهذا الغرض.
18. **`frappe.get_users_with_role` غير موجود في Frappe v15** — استخدم دائماً: `from frappe.utils.user import get_users_with_role` ثم استدعِها مباشرةً بدون `frappe.`.
19. **لا تستخدم `doc.some_field` (dot access) لحقل قد لا يكون موجوداً على الـ DocType** — يرمي `AttributeError` فوراً ويكسر الحفظ بالكامل (هذا ما حدث مع `doc.workflow_state` على Purchase Receipt — راجع 6.4). استخدم دائماً `doc.get("some_field")` عند عدم التأكد 100% من وجود الحقل في meta الحالي.
20. **PO للمصمم الخارجي (UNIDOME):** يُنشأ الآن عند الدخول الفعلي لحالة "Preliminary Design Requested" ضمن UNIDOME Opportunity Workflow (`_unidome_create_po_for_external_designer` في `opportunity.py`) — وليس عبر workflow "Outsourced Designer" القديم المعطَّل (القاعدة 5 أعلاه ما زالت صحيحة تاريخياً لكنها كود ميت فعلياً).
21. **بعد أي تعديل `.py`، استخدم `kill -TERM` وليس `kill -HUP`:** الـ gunicorn هنا يعمل بـ `--preload`، مما يجعل `kill -HUP` غير موثوق لتحميل كود جديد (راجع القسم 1) — لوحظ فعلياً سلوك غير متسق بين الطلبات بعد HUP وحدها.
22. **اختبر أي منطق جديد على بيانات حقيقية قبل النشر، وليس فقط `py_compile`:** استخدم `bench execute` (أفضل من `bench console` عبر stdin — الأخير له مشاكل parsing مع الحلقات/الدوال متعددة الأسطر) لتشغيل الدالة الجديدة مباشرة على سجل حقيقي، مع `frappe.db.rollback()` في النهاية لتفادي أي أثر جانبي. هذا كشف أخطاء حقيقية أكثر من مرة (مثال: فلترة UOM في `get_item_price` كانت تُفشل كل مطابقة صامتاً، وحقل `project` غير الموجود على Material Request).
23. **تحقّق من الحقول الفعلية على child table وليس فقط على الـ parent doctype قبل الاستعلام:** بعض الحقول (مثل `project` على Material Request) موجودة فقط على الـ child table (`Material Request Item`) وليس على المستند الرئيسي — استعلام `frappe.db.get_value` مباشر عليها كـ parent يرمي `Unknown column` فوراً.
24. **لا تفترض اكتمال `custom_field.json`:** بعض الحقول المخصصة تُنشأ يدوياً عبر Customize Form وتبقى في القاعدة فقط دون تصدير (أمثلة: `custom_actual_desgined_area_m2` على Opportunity، `opportunity` على Project — راجع القسم 9). تحقّق من `tabCustom Field` في القاعدة عند الشك بدل الاعتماد على الملف فقط.
25. **عند تشخيص "تكرار" أو "اختفاء" بيانات يبدو أنه يعاود الظهور رغم إصلاح الكود:** تحقّق من `tabDeleted Document` قبل افتراض وجود خلل في المنطق — قد يكون المستخدم نفسه يحذف السجلات يدوياً أثناء الاختبار (راجع القسم 6.5).

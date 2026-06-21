# CLAUDE.md — huge_app

دليل مرجعي شامل للتطبيق. يُقرأ هذا الملف تلقائياً في بداية كل جلسة.
**آخر تحديث:** 2026-06-19 — يشمل: إصلاح `frappe.log_error`، Project Template، إصلاح Fixtures.

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

```bash
# Graceful reload (يكفي لتحميل تغييرات Python في معظم الحالات)
kill -HUP $(pgrep -f "gunicorn -b 127.0.0.1" | head -1)

# Full restart (إذا لم تُفِد HUP — بدون sudo)
kill -TERM $(pgrep -f "gunicorn -b 127.0.0.1" | head -1)
# supervisor يعيد تشغيله تلقائياً (autorestart=true)
sleep 7
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://127.0.0.1:8000 -H "Host: erp.huge.ps"
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
│   │   └── create_unidome_project_template.py  ← ينشئ Template + 13 Task
│   ├── fixtures/
│   │   ├── custom_field.json               ← 43 حقل مخصص (5 قديمة + 38 UNIDOME)
│   │   ├── role.json                       ← 10 أدوار UNIDOME
│   │   ├── workflow.json                   ← UNIDOME Opportunity Workflow
│   │   └── workflow_state.json             ← 13 حالة workflow
│   ├── custom/
│   │   ├── lead/
│   │   │   └── lead.py                     ← Script 1: Lead محوّل → Opportunity
│   │   ├── opportunity/
│   │   │   └── opportunity.py              ← Outsourced Designer PO + Scripts 2,3,4,8
│   │   ├── sales_order/
│   │   │   └── sales_order.py              ← Scripts 5,6: التحقق + إنشاء Project + فاتورة
│   │   ├── project/
│   │   │   └── project.py                  ← CC+Warehouse + Scripts 7,9,10,14
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
| project | Link | Project |
| opportunity | Link | Opportunity |
| floor_number | Int | |
| revision | Int | |
| status | Select | Draft / Pending Client Approval / Pending Auditor Review / Approved / Rejected |
| company_items | Table | Project BOQ Company Item |
| client_items | Table | Project BOQ Client Item |
| total_slab_area_m2 | Float | |
| total_unidome_units | Int | |
| design_file | Attach | |
| notes | Text Editor | |

### 3.2 Project BOQ Company Item / Client Item (Child Tables)
شركة: item_code, uom, qty, notes. عميل: description, uom, qty, notes.

### 3.3 Engineering Solutions Settings (Single)
إعدادات الحسابات والمراكز المالية للتطبيق.

### 3.4 External Item Details (Child Table)
مرتبطة بـ Opportunity عبر `custom_external_items`: item_code, qty, rate, description.

---

### 3.5 UNIDOME: Site Inspection Report *(جديد)*
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

### 3.6 UNIDOME: FG QC Inspection *(جديد)*
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

### 3.7 UNIDOME: Customer Satisfaction Survey *(جديد)*
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

### 3.8 UNIDOME: CAPA Record *(جديد)*
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
| `custom_final_design_file` | Attach |
| `custom_final_boq_file` | Attach |
| `custom_unidome_qty` | Float |
| `custom_unidome_size` | Data |
| `custom_steel_qty_kg` | Float |
| `custom_concrete_qty_m3` | Float |
| `custom_slab_thickness_mm` | Float |

**مجموعة التحكم:**

| fieldname | النوع |
|-----------|-------|
| `custom_unidome_control_section` | Section Break (Collapsible) |
| `custom_contract_signed` | Check |
| `custom_contract_signed_date` | Date (depends_on: custom_contract_signed) |
| `custom_contract_file` | Attach (depends_on: custom_contract_signed) |
| `custom_lost_reason` | Small Text |
| `custom_unidome_opportunity_state` | Data (Read Only) — **حقل الـ Workflow** |

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
| `custom/opportunity/opportunity.py` | Opportunity on_update | Outsourced Designer: إنشاء/إلغاء PO + Scripts 2,3,4,8 |
| `custom/sales_order/sales_order.py` | SO before_submit | Script 5: التحقق من توقيع العقد ووجود Quotation مُسلَّم |
| `custom/sales_order/sales_order.py` | SO on_submit | Script 6: إنشاء Project + 12 مهمة + فاتورة Kickoff 30% |
| `custom/project/project.py` | Project after_insert | إنشاء Cost Center + Site Warehouse تلقائياً |
| `custom/project/project.py` | Project on_update | Scripts 7,9,10,14: SLA + تسوية التكلفة + MR + فاتورة التسليم |
| `custom/purchase_receipt/purchase_receipt.py` | PR on_submit | تحديث prelim_design_status في الفرصة |
| `custom/purchase_receipt/purchase_receipt.py` | PR on_update | إنشاء Project BOQ عند Approved |
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

---

## 6. Workflows

### 6.1 Outsourced Designer Workflow (قديم — مُعطَّل)
- **DocType:** Opportunity
- **workflow_state_field:** `workflow_state`
- **الحالة في ERPNext:** يجب تعطيله يدوياً من واجهة ERPNext (Workflow → is_active = 0)
- **الكود المقابل:** `custom/opportunity/opportunity.py` — دوال `_handle_workflow_approved` و `_handle_workflow_rejected`
- **ملاحظة:** حقل الربط بين PO والفرصة هو `opportunity` (بدون `custom_`)

### 6.2 UNIDOME Opportunity Workflow *(جديد — فعّال)*
- **DocType:** Opportunity
- **workflow_state_field:** `custom_unidome_opportunity_state`
- **الملف:** `fixtures/workflow.json`
- **الأدوار المستخدمة:** UNIDOME Sales User, UNIDOME Sales Manager, UNIDOME Operations User, UNIDOME Technical Manager

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
Needs Analysis →[Submit for Qualification]→ Qualification Review
Qualification Review →[Approve]→ Qualified
Qualification Review →[Reject]→ Needs Analysis
Qualified →[Request Preliminary Design]→ Preliminary Design Requested
Preliminary Design Requested →[Mark Received]→ Preliminary Design Received
Preliminary Design Received →[Submit for Review]→ Preliminary Design Review
Preliminary Design Review →[Approve Preliminary Design]→ Costing and Saving Analysis
Preliminary Design Review →[Reject - Request Revision]→ Preliminary Design Requested
Preliminary Design Review →[Request Design Revision]→ Design Revision Required
Design Revision Required →[Re-request Design]→ Preliminary Design Requested
Costing and Saving Analysis →[Approve Costing]→ Quotation Ready
Quotation Ready →[Send Quotation]→ Quotation Sent
Quotation Sent →[Mark as Under Negotiation]→ Negotiation/Review
Negotiation/Review →[Revise Pricing]→ Costing and Saving Analysis
Negotiation/Review →[Mark Won]→ Closed Won
Negotiation/Review →[Mark Lost]→ Closed Lost
```

**الأتمتة المرتبطة بتغيّر `custom_unidome_opportunity_state`:**

| الحالة الجديدة | السكريبت | الإجراء |
|----------------|----------|---------|
| Preliminary Design Requested | Script 2 | SLA 5 أيام عمل + إيميل لـ External Designer |
| Quotation Ready | Script 3 | إنشاء Quotation مسودة تلقائياً |
| Closed Lost | Script 4 | إلزامية تعبئة `custom_lost_reason` |
| Costing and Saving Analysis | Script 8 | التحقق من اكتمال حقول BOQ النهائي |

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
| Unidome: Opportunity Cost Transfer on Close | After Save | Opportunity | **مُعطَّل** | مُعطَّل عمداً — لا تُعيد تفعيله |
| Unidome: PR Approved Creates BOQ | After Save | Purchase Receipt | **مُعطَّل** | يُغطّيه `purchase_receipt.py` |
| Unidome: PR Submit Updates Opportunity | After Submit | Purchase Receipt | **مُعطَّل** | يُغطّيه `purchase_receipt.py` |
| Unidome: Project Auto CC and Warehouse | After Insert | Project | **مُعطَّل** | يُغطّيه `project.py` |
| Unidome: Sales Order Creates Project | After Submit | Sales Order | **مُعطَّل** | يُغطّيه `sales_order.py` |

> **قاعدة صارمة:** لا تُعيد تفعيل أي Server Script له مقابل في Python hooks.

---

## 9. Fixtures في hooks.py

```python
fixtures = [
    "Role",
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
        "filters": [["name", "=", "UNIDOME Opportunity Workflow"]]
    },
    {"dt": "Workflow State"},
]
```

> **ملاحظة fixtures:** Frappe v15 يطلب في بعض Doctypes حقلاً إضافياً مطابقاً لـ `autoname`:
> - `Workflow` → يجب أن يحتوي الـ JSON على `workflow_name` (مصدر autoname)
> - `Workflow State` → يجب أن يحتوي على `workflow_state_name`
> - `Project Template` → لا يُستخدم كـ fixture (يُنشأ عبر patch بسبب اعتماده على Task records)

---

## 10. Project Template — Unidome Project Template

يُنشأ تلقائياً عبر الـ patch script عند `bench migrate`.
**الملف:** `patches/create_unidome_project_template.py`
**قائمة الـ patches:** `patches.txt`

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
- ERPNext يُنشئ نسخ من التاسكات تلقائياً (`copy_from_template`) مع تواريخ محسوبة من `expected_start_date`

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

# إعادة تحميل gunicorn بعد تعديل .py
kill -HUP $(pgrep -f "gunicorn -b 127.0.0.1" | head -1)

# الاتصال بقاعدة البيانات
python3 -c "
import json, subprocess
cfg = json.load(open('sites/erp.huge.ps/site_config.json'))
subprocess.run(['mysql', '-u', 'db_huge', f\"-p{cfg['db_password']}\", cfg['db_name']])
"

# فحص سجل الأخطاء
tail -f sites/erp.huge.ps/logs/frappe.log
tail -f logs/web.error.log

# تعطيل workflow قديم (مرة واحدة فقط بعد النشر)
bench --site erp.huge.ps execute frappe.db.set_value \
  --args '["Workflow", "Outsourced Designer", "is_active", 0]'
bench --site erp.huge.ps clear-cache
```

---

## 15. قواعد التطوير

1. **اقرأ الكود الفعلي أولاً** قبل افتراض أسماء الحقول أو بنية البيانات.
2. **لا تستخدم `bench restart`** — يحتاج sudo غير متاح. استخدم `kill -HUP` أو `kill -TERM`.
3. **لا تُعيد تفعيل أي Server Script** مُعطَّل — خاصةً "Unidome: Opportunity Cost Transfer on Close".
4. **guard الحلقات:** `if doc.flags.ignore_unidome_hooks: return` أول شيء في كل hook. عند إنشاء doc جديد: `new_doc.flags.ignore_unidome_hooks = True` قبل `insert()`.
5. **Outsourced Designer workflow:** يقرأ `doc.workflow_state` — الربط بين PO والفرصة عبر `opportunity` (بدون `custom_`).
6. **UNIDOME workflow:** يقرأ `doc.custom_unidome_opportunity_state` — لا تخلط بين الحقلين.
7. **بعد تعديل أي `.py`** → `kill -HUP` لإعادة التحميل.
8. **DocTypes في `doctype/`:** لا تحذف مجلد أي DocType وإلا سيُحذف من DB عند `migrate`.
9. **ملفات `custom/`** لا تحتاج `__init__.py` — Python 3.3+ namespace packages.
10. **لا تكتب كوداً على مستوى الـ module** — كل المنطق داخل دوال hook.
11. **إضافة hook جديد:** (أ) دالة في `.py`، (ب) تسجيل في `hooks.py → doc_events`.
12. **لا تُنشئ Custom Field لحقل موجود افتراضياً** — تحقق بـ `frappe.get_meta` أولاً.
13. **Business days في الأردن:** يوم الجمعة = weekday 4، يوم السبت = weekday 5 — كلاهما عطلة. راجع دالة `_add_business_days()` في `opportunity.py` و `project.py`.
14. **فواتير الميلستون:** تستخدم `so.items[0]` كبند قالب بسعر معدَّل — لا تُعدِّل qty أو so_detail لتجنّب تعارض التحقق من الكميات المفوترة.
15. **`frappe.log_error` في Frappe v15:** الوسيط الأول هو العنوان (title، حد أقصى 140 حرف)، الثاني هو الرسالة. للرسائل المعلوماتية استخدم `frappe.logger("huge_app").info(msg)` بدلاً من log_error.
16. **Fixtures بـ autoname مُركَّب:** doctypes مثل Workflow وWorkflow State تطلب حقل اسمها الصريح (`workflow_name`, `workflow_state_name`) داخل الـ JSON إضافةً إلى `name`.
17. **Project Template:** لا يُستخدم كـ fixture — يجب إنشاء Task records أولاً ثم ربطها بالـ Template. استخدم دائماً patch script لهذا الغرض.

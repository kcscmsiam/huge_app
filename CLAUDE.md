# CLAUDE.md — huge_app

دليل مرجعي شامل للتطبيق. يُقرأ هذا الملف تلقائياً في بداية كل جلسة.

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
# لا يوجد sudo — استخدم kill -TERM على master gunicorn
# supervisor يعيد تشغيله تلقائياً (autorestart=true)
kill -TERM $(pgrep -f "gunicorn -b 127.0.0.1:8000" | head -1)
sleep 7
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://127.0.0.1:8000 -H "Host: erp.huge.ps"
```

> **تحذير:** `kill -HUP` (graceful reload) لا يُعيد تحميل كود Python مع `--preload` — يجب `kill -TERM` لإعادة تحميل التغييرات في `.py`.

---

## 2. هيكل التطبيق

```
apps/huge_app/
├── CLAUDE.md                          ← هذا الملف
├── huge_app/
│   ├── hooks.py                       ← نقطة التسجيل الرئيسية
│   ├── fixtures/
│   │   └── custom_field.json          ← الحقول المخصصة المُصدَّرة
│   ├── custom/
│   │   ├── opportunity/
│   │   │   └── opportunity.py         ← منطق workflow المخصص
│   │   ├── material_request/
│   │   │   └── material_request.py    ← BOM optimizer (before_save)
│   │   ├── project/
│   │   │   └── project.py             ← إنشاء CC + Warehouse (after_insert)
│   │   ├── purchase_receipt/
│   │   │   └── purchase_receipt.py    ← تحديث Opportunity + إنشاء BOQ
│   │   └── sales_order/
│   │       └── sales_order.py         ← إنشاء Project (on_submit)
│   ├── public/
│   │   └── js/opportunity.js          ← ملاحظة فقط (لا منطق فعلي)
│   └── huge_app/
│       └── doctype/
│           ├── project_boq/           ← DocType مخصص
│           ├── project_boq_client_item/
│           ├── project_boq_company_item/
│           ├── engineering_solutions_settings/
│           └── external_item_details/ ← Child Table للفرص
```

---

## 3. DocTypes المخصصة

### 3.1 Project BOQ
DocType رئيسي لعروض الكميات للمشاريع.

| الحقل | النوع | الخيارات |
|-------|-------|----------|
| project | Link | Project |
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

### 3.2 Project BOQ Company Item (Child Table)
| الحقل | النوع |
|-------|-------|
| item_code | Link → Item |
| uom | Link → UOM |
| qty | Float |
| notes | Small Text |

### 3.3 Project BOQ Client Item (Child Table)
| الحقل | النوع |
|-------|-------|
| description | Data |
| uom | Data |
| qty | Float |
| notes | Small Text |

### 3.4 Engineering Solutions Settings
DocType للإعدادات العامة للتطبيق (Single).

| الحقل | النوع | الغرض |
|-------|-------|--------|
| deferred_bid_cost_account | Link → Account | حساب تكاليف العطاء المؤجل |
| project_design_cost_account | Link → Account | حساب تكاليف التصميم |
| project_manufacturing_account | Link → Account | حساب التصنيع |
| subcon_cost_account | Link → Account | حساب المقاولين الفرعيين |
| lost_bid_expense_account | Link → Account | حساب العطاءات الخاسرة |
| design_dept_cost_center | Link → Cost Center | |
| projects_parent_cost_center | Link → Cost Center | |
| projects_parent_warehouse | Link → Warehouse | |
| default_subcontractor | Link → Supplier | |
| default_designer_supplier | Link → Supplier | |

### 3.5 External Item Details (Child Table)
Child Table مرتبطة بـ Opportunity عبر حقل `custom_external_items`.

| الحقل | النوع |
|-------|-------|
| item_code | Link → Item |
| qty | Float |
| rate | Currency |
| description | Text Editor |

---

## 4. الحقول المخصصة (Custom Fields)

مُعرَّفة في `fixtures/custom_field.json` ومُسجَّلة في `hooks.py`.

### على Opportunity

| اسم الحقل | النوع | تفاصيل |
|-----------|-------|--------|
| `custom_project_name` | Data | يظهر بعد `opportunity_owner` |
| `custom_external_designer` | Link → Supplier | يظهر بعد `total` |
| `custom_external_designer_items` | Section Break | يظهر بعد `custom_external_designer`، مشروط: `depends_on: custom_external_designer` |
| `custom_external_items` | Table → External Item Details | يظهر داخل Section Break أعلاه |

### على Purchase Order Item

| اسم الحقل | النوع | تفاصيل |
|-----------|-------|--------|
| `custom_note` | Small Text | ملاحظة على بند أمر الشراء |

### تحديث الـ fixtures بعد أي تعديل على الحقول:
```bash
bench --site erp.huge.ps export-fixtures --app huge_app
```

---

## 5. Python Hooks — الملفات والأحداث

جميع المنطق الآن في ملفات Python مُسجَّلة عبر `hooks.py`. **لا يوجد Server Scripts فعّالة مكررة.**

### 5.1 ملف `hooks.py` — doc_events الحالية

```python
doc_events = {
    "Opportunity": {
        "on_update": "huge_app.custom.opportunity.opportunity.on_update",
    },
    "Purchase Receipt": {
        "on_submit": "huge_app.custom.purchase_receipt.purchase_receipt.on_submit",
        "on_update": "huge_app.custom.purchase_receipt.purchase_receipt.on_update",
    },
    "Project": {
        "after_insert": "huge_app.custom.project.project.after_insert",
    },
    "Sales Order": {
        "on_submit": "huge_app.custom.sales_order.sales_order.on_submit",
    },
    "Material Request": {
        "before_save": "huge_app.custom.material_request.material_request.before_save",
    },
}
```

### 5.2 جدول الملفات والوظائف

| الملف | الدالة | الحدث | الوظيفة |
|-------|--------|-------|---------|
| `custom/opportunity/opportunity.py` | `on_update` | Opportunity on_update | إنشاء/إلغاء PO عند تغيّر workflow |
| `custom/material_request/material_request.py` | `before_save` | Material Request before_save | اختيار أفضل BOM لكل بند في MR نوع Manufacture |
| `custom/project/project.py` | `after_insert` | Project after_insert | إنشاء Cost Center + Site Warehouse تلقائياً |
| `custom/purchase_receipt/purchase_receipt.py` | `on_submit` | Purchase Receipt on_submit | تحديث `prelim_design_status` في الفرصة المرتبطة إلى "Received" |
| `custom/purchase_receipt/purchase_receipt.py` | `on_update` | Purchase Receipt on_update | إنشاء Project BOQ عند وصول PR لحالة "Approved" |
| `custom/sales_order/sales_order.py` | `on_submit` | Sales Order on_submit | إنشاء Project (وطوابق إضافية) وربطه بالـ SO |

### 5.3 قواعد بنية الكود — مهمة جداً

- **كل الكود داخل دوال** — لا يجوز وجود `doc` أو `frappe` على مستوى الـ module خارج الدوال.
- **كل ملف يحتوي `import frappe`** في أول سطر.
- بنية الدالة الصحيحة: `def on_submit(doc, method=None):` أو `def before_save(doc, method=None):` إلخ.
- الكود على مستوى الـ module يُنفَّذ عند **استيراد** الملف → يسبب `NameError: name 'doc' is not defined`.

---

## 6. منطق الـ Workflow (opportunity.py)

**الملف:** `huge_app/custom/opportunity/opportunity.py`
**Hook:** `doc_events → Opportunity → on_update`

### Workflow المُطبَّق: "Outsourced Designer"
- **workflow_state_field:** `workflow_state` (ليس `sales_stage`)
- يُطبَّق على DocType: **Opportunity**

### المسار: Approve من "Preliminary Design Requested"

```
Preliminary Design Requested  →[Approve]→  Preliminary Design Received
```

عند هذا الانتقال تلقائياً:
1. يتحقق من وجود `custom_external_designer` (Supplier)
2. يتحقق من وجود بنود في `custom_external_items`
3. يبحث عن PO موجود مرتبط بنفس الفرصة (حقل `opportunity`)
4. إن لم يوجد، يُنشئ Purchase Order جديد بالبنود من `custom_external_items`
5. يُسلّم (submit) الـ PO تلقائياً

### المسار: Reject من "Preliminary Design Check"

```
Preliminary Design Check  →[Reject]→  Preliminary Design Requested
```

عند هذا الانتقال تلقائياً:
- يجد الـ PO المرتبط بالفرصة (docstatus=1)
- يُلغي (cancel) الـ PO

### نقاط جوهرية — لا تغيّرها

- الكود يقرأ `doc.workflow_state` و `prev_doc.workflow_state` — **ليس** `sales_stage`
- حقل الربط في Purchase Order هو `opportunity` — **ليس** `custom_opportunity`
- الجزء الخاص بـ "Cost Transfer" في الملف (الدوال: `get_abbr`, `get_accounts`, `get_linked_purchase_receipts`, `create_purchase_invoice`) موجود كـ helper functions فقط — **لا يوجد كود تنفيذي على مستوى الـ module** — الـ Server Script المقابل له مُعطَّل عمداً

---

## 7. Server Scripts في قاعدة البيانات

| الاسم | الحدث | DocType | الحالة | ملاحظة |
|-------|-------|---------|--------|--------|
| Unidome: BOM Optimizer API | API | — | **فعّال** | API endpoint — لا مقابل Python له |
| Unidome: MR Trigger BOM Optimizer | After Save | Material Request | **مُعطَّل** | يُغطّيه `material_request.py` |
| Unidome: Opportunity Cost Transfer on Close | After Save | Opportunity | **مُعطَّل** | مُعطَّل عمداً — لا تُعيد تفعيله |
| Unidome: PR Approved Creates BOQ | After Save | Purchase Receipt | **مُعطَّل** | يُغطّيه `purchase_receipt.py` |
| Unidome: PR Submit Updates Opportunity | After Submit | Purchase Receipt | **مُعطَّل** | يُغطّيه `purchase_receipt.py` |
| Unidome: Project Auto CC and Warehouse | After Insert | Project | **مُعطَّل** | يُغطّيه `project.py` |
| Unidome: Sales Order Creates Project | After Submit | Sales Order | **مُعطَّل** | يُغطّيه `sales_order.py` |

> **قاعدة صارمة:** لا تُعيد تفعيل أي Server Script له مقابل في Python hooks — سيتسبب في تنفيذ مضاعف وأخطاء.

---

## 8. fixtures في hooks.py

```python
fixtures = [
    {"dt": "Custom Field", "filters": [
        ["name", "in", [
            "Opportunity-custom_project_name",
            "Opportunity-custom_external_designer",
            "Opportunity-custom_external_designer_items",
            "Opportunity-custom_external_items",
            "Purchase Order Item-custom_note",
        ]]
    ]}
]
```

---

## 9. أوامر شائعة

```bash
# تطبيق migrations
bench --site erp.huge.ps migrate

# تصدير fixtures
bench --site erp.huge.ps export-fixtures --app huge_app

# تنظيف cache
bench --site erp.huge.ps clear-cache

# فحص syntax لجميع ملفات custom
python3 -m py_compile apps/huge_app/huge_app/custom/opportunity/opportunity.py
python3 -m py_compile apps/huge_app/huge_app/custom/material_request/material_request.py
python3 -m py_compile apps/huge_app/huge_app/custom/project/project.py
python3 -m py_compile apps/huge_app/huge_app/custom/purchase_receipt/purchase_receipt.py
python3 -m py_compile apps/huge_app/huge_app/custom/sales_order/sales_order.py

# إعادة تشغيل gunicorn بعد أي تعديل .py
kill -TERM $(pgrep -f "gunicorn -b 127.0.0.1:8000" | head -1)
sleep 7
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://127.0.0.1:8000 -H "Host: erp.huge.ps"

# الاتصال بقاعدة البيانات
python3 -c "
import json, subprocess
cfg = json.load(open('sites/erp.huge.ps/site_config.json'))
subprocess.run(['mysql', '-u', 'db_huge', f\"-p{cfg['db_password']}\", cfg['db_name']])
"

# فحص حالة Server Scripts
python3 << 'EOF'
import json, subprocess
cfg = json.load(open('sites/erp.huge.ps/site_config.json'))
r = subprocess.run(['mysql', '-u', 'db_huge', f"-p{cfg['db_password']}", cfg['db_name'], '-e',
    'SELECT name, disabled FROM `tabServer Script` ORDER BY name;'],
    capture_output=True, text=True)
print(r.stdout)
EOF

# فحص سجل الأخطاء
tail -f sites/erp.huge.ps/logs/frappe.log
tail -f logs/web.error.log
```

---

## 10. حقول Project — Standard vs Custom

قبل إضافة أي Custom Field تحقق أن ERPNext لا يملكه افتراضياً:
```python
meta = frappe.get_meta("Project")
print([f.fieldname for f in meta.fields if "cost" in f.fieldname])
```

| الحقل | النوع | الموقف الصحيح |
|-------|-------|--------------|
| `cost_center` | **Standard Field** في Project | استخدمه مباشرة — لا تُنشئ Custom Field |
| `expected_cost` | Standard Field في Project | استخدمه مباشرة |
| `customer` | Standard Field في Project | استخدمه مباشرة |

**`project.py` يكتب `cost_center`** (الحقل الافتراضي) — لا يوجد `custom_project_cost_center` على Project.

---

## 11. قواعد التطوير

1. **اقرأ الكود الفعلي أولاً** قبل افتراض أسماء الحقول أو بنية البيانات.
2. **لا تستخدم `bench restart`** — يحتاج sudo غير متاح. استخدم `kill -TERM` على master gunicorn.
3. **لا تُعيد تفعيل أي Server Script** مُعطَّل — خاصةً "Unidome: Opportunity Cost Transfer on Close" والخمسة المعطَّلة التي لها مقابل في Python hooks.
4. **الـ workflow يُحدّث `workflow_state`** فقط — أي كود يتحقق من تغيّر حالة الـ workflow يجب أن يقرأ هذا الحقل وليس `sales_stage`.
5. **الربط بين PO والفرصة** عبر حقل `opportunity` في `tabPurchase Order` (وليس `custom_opportunity`).
6. **بعد تعديل أي `.py`** يجب إعادة تشغيل gunicorn بـ `kill -TERM` حتى يُحمّل الكود الجديد (سبب: `--preload`).
7. **DocTypes الأربعة** (Project BOQ, Project BOQ Client Item, Project BOQ Company Item, Engineering Solutions Settings) موجودة في كود التطبيق — لا تحذفها من `doctype/` وإلا ستُحذف من DB عند `migrate`.
8. **ملفات `custom/`** لا تحتاج `__init__.py` — Python 3.3+ namespace packages تعمل.
9. **لا تكتب كوداً على مستوى الـ module** في ملفات `custom/` — كل المنطق يجب أن يكون داخل دوال hook واضحة (`def before_save(doc, method=None)` إلخ).
10. **إضافة hook جديد** يتطلب خطوتين: (أ) إضافة الدالة في ملف `.py`، (ب) تسجيلها في `hooks.py` ← `doc_events`.
11. **لا تُنشئ Custom Field لحقل موجود افتراضياً** في ERPNext — تحقق دائماً بـ `frappe.get_meta` قبل الإضافة.

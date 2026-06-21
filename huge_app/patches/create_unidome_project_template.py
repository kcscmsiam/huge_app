"""
Create the Unidome Project Template with 13 Task records.

Run once via: bench --site erp.huge.ps migrate
Safe to re-run — skips if template already exists.
"""

import frappe

TEMPLATE_NAME = "Unidome Project Template"

TASKS = [
    {
        "subject"      : "تأهيل الفرصة",
        "description"  : "مراجعة بيانات العميل وتقييم مدى ملاءمة نظام UNIDOME لاحتياجاتهم",
        "start"        : 0,
        "duration"     : 3,
        "task_weight"  : 1.0,
        "is_milestone" : 0,
    },
    {
        "subject"      : "التصميم المبدئي",
        "description"  : "إعداد التصميم المبدئي وتحديد مساحة البلاطة والاحتياجات الأولية (SLA: 5 أيام عمل)",
        "start"        : 3,
        "duration"     : 7,
        "task_weight"  : 2.0,
        "is_milestone" : 0,
    },
    {
        "subject"      : "المراجعة الفنية",
        "description"  : "مراجعة التصميم المبدئي من قبل الفريق الفني والتحقق من مطابقته للمواصفات",
        "start"        : 10,
        "duration"     : 3,
        "task_weight"  : 1.0,
        "is_milestone" : 0,
    },
    {
        "subject"      : "التسعير والتفاوض",
        "description"  : "إعداد BOQ وتفاوض الشروط مع العميل حتى الوصول لاتفاق",
        "start"        : 13,
        "duration"     : 5,
        "task_weight"  : 1.0,
        "is_milestone" : 0,
    },
    {
        "subject"      : "توقيع العقد",
        "description"  : "توقيع العقد النهائي وتسجيل Sales Order — تُدفع دفعة المقدمة 30%",
        "start"        : 18,
        "duration"     : 2,
        "task_weight"  : 1.0,
        "is_milestone" : 1,
    },
    {
        "subject"      : "التصميم النهائي",
        "description"  : "إعداد خرائط التنفيذ التفصيلية وتفاصيل وحدات UNIDOME (SLA: 7 أيام عمل)",
        "start"        : 20,
        "duration"     : 10,
        "task_weight"  : 3.0,
        "is_milestone" : 0,
    },
    {
        "subject"      : "اعتماد التصميم",
        "description"  : "مراجعة واعتماد التصميم النهائي من قبل العميل والفريق الفني",
        "start"        : 30,
        "duration"     : 3,
        "task_weight"  : 1.0,
        "is_milestone" : 1,
    },
    {
        "subject"      : "تخطيط الموارد",
        "description"  : "طلب المواد (Material Request) وجدولة التصنيع وتجهيز المصنع",
        "start"        : 33,
        "duration"     : 4,
        "task_weight"  : 1.0,
        "is_milestone" : 0,
    },
    {
        "subject"      : "التصنيع",
        "description"  : "تصنيع وحدات UNIDOME: Shield → Unifix → Unidome Production → 4-Unidome Module",
        "start"        : 37,
        "duration"     : 14,
        "task_weight"  : 4.0,
        "is_milestone" : 0,
    },
    {
        "subject"      : "فحص جودة المنتج النهائي",
        "description"  : "فحص FG QC Inspection واعتماد الوحدات قبل الشحن",
        "start"        : 51,
        "duration"     : 2,
        "task_weight"  : 1.0,
        "is_milestone" : 0,
    },
    {
        "subject"      : "الشحن",
        "description"  : "شحن الوحدات إلى الموقع وإصدار Delivery Note",
        "start"        : 53,
        "duration"     : 2,
        "task_weight"  : 1.0,
        "is_milestone" : 1,
    },
    {
        "subject"      : "التنفيذ الميداني",
        "description"  : "تركيب وتنفيذ نظام البلاطة UNIDOME في الموقع",
        "start"        : 55,
        "duration"     : 7,
        "task_weight"  : 3.0,
        "is_milestone" : 0,
    },
    {
        "subject"      : "الإغلاق والتسليم",
        "description"  : "إغلاق المشروع وتسليمه للعميل — يُطلق استبيان رضا العملاء (D+30)",
        "start"        : 62,
        "duration"     : 2,
        "task_weight"  : 1.0,
        "is_milestone" : 1,
    },
]


def execute():
    if frappe.db.exists("Project Template", TEMPLATE_NAME):
        frappe.logger("huge_app").info(
            f"[patch] Project Template '{TEMPLATE_NAME}' already exists — skipping."
        )
        return

    task_names = _create_template_tasks()
    _create_project_template(task_names)
    frappe.db.commit()
    frappe.logger("huge_app").info(
        f"[patch] '{TEMPLATE_NAME}' created with {len(task_names)} tasks."
    )


def _create_template_tasks():
    created = []
    for t in TASKS:
        existing = frappe.db.get_value(
            "Task",
            {"subject": t["subject"], "is_template": 1, "project": ["is", "not set"]},
            "name"
        )
        if existing:
            created.append(existing)
            continue

        task = frappe.new_doc("Task")
        task.subject      = t["subject"]
        task.description  = t["description"]
        task.status       = "Template"
        task.is_template  = 1
        task.start        = t["start"]
        task.duration     = t["duration"]
        task.task_weight  = t["task_weight"]
        task.is_milestone = t["is_milestone"]
        task.insert(ignore_permissions=True)
        created.append(task.name)

    return created


def _create_project_template(task_names):
    tmpl = frappe.new_doc("Project Template")
    tmpl.name = TEMPLATE_NAME

    for task_name in task_names:
        tmpl.append("tasks", {"task": task_name})

    tmpl.insert(ignore_permissions=True)

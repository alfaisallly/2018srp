from app.models import Permission

PERMISSION_LABELS: dict[Permission, dict[str, str]] = {
    Permission.VIEW: {"label": "عرض البيانات", "group": "قراءة", "description": "عرض لوحة التحكم والأصول"},
    Permission.VIEW_REPORTS: {"label": "عرض التقارير", "group": "قراءة", "description": "تحميل وعرض التقارير"},
    Permission.MANAGE_DEVICES: {"label": "تعديل الشبكة", "group": "تعديل", "description": "إضافة/فحص/حذف أجهزة الشبكة"},
    Permission.MANAGE_SERVERS: {"label": "تعديل السيرفرات", "group": "تعديل", "description": "إضافة/فحص/حذف السيرفرات"},
    Permission.MANAGE_STORAGE: {"label": "تعديل التخزين", "group": "تعديل", "description": "إضافة/فحص/حذف أنظمة التخزين"},
    Permission.MANAGE_DATACENTERS: {"label": "تعديل مراكز البيانات", "group": "تعديل", "description": "إدارة مراكز البيانات والرفوف"},
    Permission.MANAGE_NETWORK_MAPS: {"label": "تعديل خرائط الشبكة", "group": "تعديل", "description": "إنشاء وتعديل خرائط التوبولوجيا"},
    Permission.MANAGE_ALERTS: {"label": "إدارة التنبيهات", "group": "تعديل", "description": "حل وتعديل التنبيهات"},
    Permission.MANAGE_USERS: {"label": "إدارة المستخدمين", "group": "إدارة", "description": "إنشاء وتعديل المستخدمين والصلاحيات"},
    Permission.MANAGE_IPAM: {"label": "إدارة عناوين IP", "group": "تعديل", "description": "إدارة البادئات والتخصيصات IPAM"},
    Permission.MANAGE_INTEGRATIONS: {"label": "إدارة التكاملات", "group": "تعديل", "description": "ربط PRTG وVMware والأنظمة الخارجية"},
}

ROLE_TEMPLATES: dict[str, dict] = {
    "admin": {
        "label": "مدير النظام — كامل الصلاحيات",
        "permissions": list(Permission),
    },
    "editor": {
        "label": "قراءة وتعديل",
        "permissions": [
            Permission.VIEW,
            Permission.VIEW_REPORTS,
            Permission.MANAGE_DEVICES,
            Permission.MANAGE_SERVERS,
            Permission.MANAGE_STORAGE,
            Permission.MANAGE_DATACENTERS,
            Permission.MANAGE_NETWORK_MAPS,
            Permission.MANAGE_ALERTS,
            Permission.MANAGE_IPAM,
            Permission.MANAGE_INTEGRATIONS,
        ],
    },
    "operator": {
        "label": "مشغّل — قراءة وتعديل الأصول",
        "permissions": [
            Permission.VIEW,
            Permission.VIEW_REPORTS,
            Permission.MANAGE_DEVICES,
            Permission.MANAGE_SERVERS,
            Permission.MANAGE_STORAGE,
            Permission.MANAGE_ALERTS,
            Permission.MANAGE_NETWORK_MAPS,
            Permission.MANAGE_IPAM,
            Permission.MANAGE_INTEGRATIONS,
        ],
    },
    "viewer": {
        "label": "قراءة فقط",
        "permissions": [Permission.VIEW, Permission.VIEW_REPORTS],
    },
    "custom": {
        "label": "مخصص — اختيار يدوي",
        "permissions": [],
    },
}


def resolve_permissions(role: str, custom: list[str] | None = None) -> list[str]:
    if role == "custom" and custom:
        return _validate_permissions(custom)
    template = ROLE_TEMPLATES.get(role)
    if template:
        return [p.value for p in template["permissions"]]
    return [Permission.VIEW.value]


def _validate_permissions(perms: list[str]) -> list[str]:
    valid = {p.value for p in Permission}
    return [p for p in perms if p in valid]


def permissions_from_user(user) -> set[Permission]:
    if user.permissions:
        return {Permission(p) for p in user.permissions if p in {x.value for x in Permission}}
    template = ROLE_TEMPLATES.get(user.role)
    if template and template["permissions"]:
        return set(template["permissions"])
    from app.models import ROLE_PERMISSIONS

    return ROLE_PERMISSIONS.get(user.role, {Permission.VIEW})

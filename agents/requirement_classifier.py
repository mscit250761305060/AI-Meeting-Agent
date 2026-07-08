import re


CATEGORY_RULES = {

    "Authentication": [
        "login",
        "logout",
        "signup",
        "register",
        "otp",
        "password",
        "authentication",
        "forgot password"
    ],

    "Employee": [
        "employee",
        "staff",
        "worker"
    ],

    "Department": [
        "department",
        "division"
    ],

    "Leave": [
        "leave",
        "holiday",
        "vacation"
    ],

    "Attendance": [
        "attendance",
        "check in",
        "check out",
        "punch"
    ],

    "Payroll": [
        "salary",
        "payroll",
        "payment",
        "bonus"
    ],

    "Dashboard": [
        "dashboard",
        "report",
        "analytics",
        "graph"
    ],

    "User Management": [
        "role",
        "permission",
        "admin",
        "manager",
        "user"
    ]
}


def classify_requirement(text):

    lower = text.lower()

    for category, keywords in CATEGORY_RULES.items():

        for keyword in keywords:

            if re.search(r"\b" + re.escape(keyword) + r"\b", lower):
                return category

    return "General"
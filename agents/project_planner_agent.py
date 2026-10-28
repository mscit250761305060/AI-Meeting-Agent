import re

def plan_project(requirements):
    title = (requirements.get("project_name") or requirements.get("project_title") or "").lower()
    
    slug = re.sub(r"[^\w\s-]", "", title)
    slug = re.sub(r"[-\s]+", "_", slug).strip("_") or "custom_app"

    return {
        "project_type": "crud_app",
        "template": slug,
        "entity": requirements.get("entity_name") or "Item"
    }
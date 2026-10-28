"""
app/services/generator/requirement_parser.py

Provider-independent requirement parser that converts transcripts or structured inputs
into a validated ProjectSpecification without calling any AI provider.
"""

import re
from typing import Dict, Any, List, Union
from app.services.generator.specification import (
    ProjectSpecification,
    FieldSpec,
    PageSpec,
    ApiEndpointSpec
)


DOMAIN_TEMPLATES = {
    "task": {
        "project_name": "Task Management System",
        "industry": "Productivity & Operations",
        "purpose": "Organize, track, and collaborate on team tasks and project milestones.",
        "entity_name": "Task",
        "entity_plural": "tasks",
        "fields": [
            FieldSpec(name="title", type="string", label="Task Title", required=True),
            FieldSpec(name="description", type="text", label="Description", required=False),
            FieldSpec(name="status", type="string", label="Status", required=True, default="Pending", options=["Pending", "In Progress", "Completed", "Blocked"]),
            FieldSpec(name="priority", type="string", label="Priority", required=True, default="Medium", options=["Low", "Medium", "High", "Critical"]),
            FieldSpec(name="due_date", type="string", label="Due Date", required=False)
        ],
        "pages": [
            PageSpec(title="Dashboard", slug="dashboard_page", type="dashboard", description="Overview metrics, pending tasks, and completion rate."),
            PageSpec(title="Task List", slug="task_list_page", type="list", description="Searchable, filterable list of all project tasks."),
            PageSpec(title="New Task", slug="task_form_page", type="form", description="Create or update project tasks.")
        ],
        "features": [
            "Create and assign new tasks",
            "Update task status and priority",
            "Real-time task search and filtering",
            "Task completion analytics",
            "Delete completed or cancelled tasks"
        ]
    },
    "ecommerce": {
        "project_name": "E-Commerce Product Management",
        "industry": "Retail & E-Commerce",
        "purpose": "Manage catalog products, inventory levels, and category pricing.",
        "entity_name": "Product",
        "entity_plural": "products",
        "fields": [
            FieldSpec(name="name", type="string", label="Product Name", required=True),
            FieldSpec(name="category", type="string", label="Category", required=True, default="General", options=["Electronics", "Clothing", "Home & Kitchen", "Books", "General"]),
            FieldSpec(name="price", type="float", label="Price ($)", required=True, default=0.0),
            FieldSpec(name="stock", type="integer", label="Stock Quantity", required=True, default=10),
            FieldSpec(name="description", type="text", label="Product Description", required=False)
        ],
        "pages": [
            PageSpec(title="Dashboard", slug="dashboard_page", type="dashboard", description="Sales velocity, stock levels, and category breakdown."),
            PageSpec(title="Product Catalog", slug="product_list_page", type="list", description="Browse and search inventory products."),
            PageSpec(title="Add Product", slug="product_form_page", type="form", description="Add new inventory items to catalog.")
        ],
        "features": [
            "Catalog product creation and management",
            "Stock quantity and inventory tracking",
            "Category filtering and product search",
            "Product price and detail updates",
            "Inventory deletion and retirement"
        ]
    },
    "clinic": {
        "project_name": "Clinic Patient Management",
        "industry": "Healthcare",
        "purpose": "Maintain patient records, visits, diagnoses, and medical status.",
        "entity_name": "Patient",
        "entity_plural": "patients",
        "fields": [
            FieldSpec(name="name", type="string", label="Patient Full Name", required=True),
            FieldSpec(name="age", type="integer", label="Age", required=True, default=30),
            FieldSpec(name="gender", type="string", label="Gender", required=True, default="Other", options=["Male", "Female", "Other"]),
            FieldSpec(name="contact", type="string", label="Contact Phone", required=True),
            FieldSpec(name="diagnosis", type="string", label="Primary Diagnosis / Notes", required=False),
            FieldSpec(name="status", type="string", label="Status", required=True, default="Active", options=["Active", "Admitted", "Discharged", "Follow-up"])
        ],
        "pages": [
            PageSpec(title="Dashboard", slug="dashboard_page", type="dashboard", description="Patient intake metrics and active treatment status."),
            PageSpec(title="Patient Directory", slug="patient_list_page", type="list", description="Searchable patient records."),
            PageSpec(title="Register Patient", slug="patient_form_page", type="form", description="Patient intake and registration form.")
        ],
        "features": [
            "Patient intake and registration",
            "Diagnosis tracking and status updates",
            "Patient directory search and filter",
            "Patient discharge and record archiving"
        ]
    },
    "crm": {
        "project_name": "Customer Relationship Management (CRM)",
        "industry": "Sales & Marketing",
        "purpose": "Track sales leads, customer contacts, company deals, and conversion pipelines.",
        "entity_name": "Customer",
        "entity_plural": "customers",
        "fields": [
            FieldSpec(name="name", type="string", label="Customer Name", required=True),
            FieldSpec(name="email", type="string", label="Email Address", required=True),
            FieldSpec(name="phone", type="string", label="Phone Number", required=False),
            FieldSpec(name="company", type="string", label="Company Name", required=False),
            FieldSpec(name="status", type="string", label="Lead Stage", required=True, default="Lead", options=["Lead", "Contacted", "Proposal", "Won", "Lost"])
        ],
        "pages": [
            PageSpec(title="Dashboard", slug="dashboard_page", type="dashboard", description="Lead conversion funnel and client metrics."),
            PageSpec(title="Customer Directory", slug="customer_list_page", type="list", description="Active accounts and leads."),
            PageSpec(title="Add Customer", slug="customer_form_page", type="form", description="Record new prospective client.")
        ],
        "features": [
            "Lead intake and contact management",
            "Stage conversion pipeline tracking",
            "Customer communication logs",
            "Search and segment leads by company"
        ]
    },
    "booking": {
        "project_name": "Hotel Reservation & Booking System",
        "industry": "Hospitality",
        "purpose": "Manage guest reservations, room types, check-in dates, and booking status.",
        "entity_name": "Booking",
        "entity_plural": "bookings",
        "fields": [
            FieldSpec(name="guest_name", type="string", label="Guest Name", required=True),
            FieldSpec(name="room_type", type="string", label="Room Type", required=True, default="Standard", options=["Standard", "Deluxe", "Suite", "Executive"]),
            FieldSpec(name="check_in", type="string", label="Check-In Date", required=True),
            FieldSpec(name="check_out", type="string", label="Check-Out Date", required=True),
            FieldSpec(name="status", type="string", label="Reservation Status", required=True, default="Confirmed", options=["Confirmed", "Checked In", "Checked Out", "Cancelled"])
        ],
        "pages": [
            PageSpec(title="Dashboard", slug="dashboard_page", type="dashboard", description="Occupancy rate, upcoming check-ins, and departures."),
            PageSpec(title="Reservations", slug="booking_list_page", type="list", description="View and manage guest bookings."),
            PageSpec(title="New Reservation", slug="booking_form_page", type="form", description="Create a new guest booking.")
        ],
        "features": [
            "Guest reservation creation",
            "Occupancy and check-in tracking",
            "Room type selection and date validation",
            "Cancellation and modification handling"
        ]
    },
    "employee": {
        "project_name": "Employee Management System",
        "industry": "Human Resources",
        "purpose": "Manage organization workforce, departmental assignments, and staff profiles.",
        "entity_name": "Employee",
        "entity_plural": "employees",
        "fields": [
            FieldSpec(name="name", type="string", label="Full Name", required=True),
            FieldSpec(name="email", type="string", label="Work Email", required=True),
            FieldSpec(name="department", type="string", label="Department", required=True, default="Engineering", options=["Engineering", "Product", "Sales", "HR", "Finance", "Operations"]),
            FieldSpec(name="role", type="string", label="Job Title", required=True, default="Associate"),
            FieldSpec(name="salary", type="float", label="Annual Salary ($)", required=False, default=60000.0)
        ],
        "pages": [
            PageSpec(title="Dashboard", slug="dashboard_page", type="dashboard", description="Headcount metrics, department distribution, and staff summary."),
            PageSpec(title="Employee Directory", slug="employee_list_page", type="list", description="Browse and search staff members."),
            PageSpec(title="Add Employee", slug="employee_form_page", type="form", description="Staff onboarding and profile creation form.")
        ],
        "features": [
            "Employee onboarding and profile creation",
            "Departmental assignment and role updates",
            "Search and filter staff directory",
            "Salary tracking and workforce analytics"
        ]
    },
    "generic": {
        "project_name": "Custom Resource Management",
        "industry": "General Business",
        "purpose": "Track and manage custom business resources, statuses, and records.",
        "entity_name": "Item",
        "entity_plural": "items",
        "fields": [
            FieldSpec(name="name", type="string", label="Item Name", required=True),
            FieldSpec(name="category", type="string", label="Category", required=True, default="General"),
            FieldSpec(name="status", type="string", label="Status", required=True, default="Active", options=["Active", "Pending", "Archived"]),
            FieldSpec(name="description", type="text", label="Description", required=False)
        ],
        "pages": [
            PageSpec(title="Dashboard", slug="dashboard_page", type="dashboard", description="Operational metrics and item status overview."),
            PageSpec(title="Item List", slug="item_list_page", type="list", description="Searchable directory of records."),
            PageSpec(title="Add Item", slug="item_form_page", type="form", description="Create new item record.")
        ],
        "features": [
            "Create new records",
            "Search and filter records",
            "Update record properties",
            "Delete or archive records"
        ]
    }
}


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[-\s]+", "_", text).strip("_")


def parse_requirements(input_data: Union[str, Dict[str, Any]]) -> ProjectSpecification:
    """
    Parses either structured requirements dictionary or raw meeting transcript text into
    a fully validated ProjectSpecification using deterministic domain heuristics.
    """
    if isinstance(input_data, dict):
        return _parse_structured_input(input_data)
    elif isinstance(input_data, str):
        return _parse_transcript_input(input_data)
    else:
        raise ValueError("Unsupported input format for requirement parsing.")


def _parse_structured_input(data: Dict[str, Any]) -> ProjectSpecification:
    project_name = data.get("project_name") or data.get("project_title") or "Dynamic Application"
    slug = slugify(project_name)

    entity_name = data.get("entity_name")
    entity_plural = data.get("entity_plural")

    # Match domain if entity not explicitly passed
    matched_domain = "generic"
    lower_name = project_name.lower()
    for dom_key in DOMAIN_TEMPLATES:
        if dom_key in lower_name:
            matched_domain = dom_key
            break

    template = DOMAIN_TEMPLATES[matched_domain]

    if not entity_name:
        entity_name = template["entity_name"]
    if not entity_plural:
        entity_plural = template["entity_plural"]

    # Parse fields
    fields = []
    raw_fields = data.get("fields", [])
    if raw_fields:
        for f in raw_fields:
            if isinstance(f, dict):
                fields.append(FieldSpec(**f))
            elif isinstance(f, str):
                fields.append(FieldSpec(name=slugify(f), label=f.title(), type="string"))
    else:
        fields = template["fields"]

    # Parse pages
    pages = []
    raw_pages = data.get("pages", [])
    if raw_pages:
        for p in raw_pages:
            if isinstance(p, dict):
                pages.append(PageSpec(**p))
            elif isinstance(p, str):
                p_slug = slugify(p)
                p_type = "generic"
                if "dashboard" in p_slug:
                    p_type = "dashboard"
                elif "list" in p_slug or "table" in p_slug:
                    p_type = "list"
                elif "form" in p_slug or "create" in p_slug or "add" in p_slug:
                    p_type = "form"
                elif "login" in p_slug:
                    p_type = "login"
                pages.append(PageSpec(title=p.title(), slug=p_slug, type=p_type))
    else:
        pages = template["pages"]

    features = data.get("features") or template["features"]
    user_roles = data.get("user_roles") or ["Admin", "Manager", "User"]
    purpose = data.get("purpose") or data.get("description") or template["purpose"]
    industry = data.get("industry") or template["industry"]

    api_endpoints = _build_default_api_endpoints(entity_plural, entity_name)

    unsupported = []
    raw_text = str(data).lower()
    if "payment" in raw_text or "stripe" in raw_text:
        unsupported.append("Third-party payment gateways (Stripe/PayPal) require active external API provider configuration.")
    if "ai chatbot" in raw_text or "llm" in raw_text:
        unsupported.append("Arbitrary LLM reasoning and conversational bots are deferred until AI provider selection.")

    return ProjectSpecification(
        project_name=project_name,
        project_slug=slug,
        purpose=purpose,
        industry=industry,
        entity_name=entity_name,
        entity_plural=entity_plural,
        fields=fields,
        pages=pages,
        features=features,
        user_roles=user_roles,
        backend_framework="FastAPI",
        database_type="SQLite",
        api_endpoints=api_endpoints,
        unsupported_requirements=unsupported,
        generation_notes=[
            "Generated via deterministic provider-independent architecture.",
            "No AI model hallucination or synthetic external calls performed."
        ],
        metadata={"source": "structured_input"}
    )


def _parse_transcript_input(transcript: str) -> ProjectSpecification:
    text = transcript.lower()

    # Detect domain keywords
    domain_key = "generic"
    if any(k in text for k in ["task", "todo", "kanban", "project management", "sprint"]):
        domain_key = "task"
    elif any(k in text for k in ["product", "e-commerce", "ecommerce", "store", "shop", "catalog", "cart"]):
        domain_key = "ecommerce"
    elif any(k in text for k in ["patient", "clinic", "hospital", "doctor", "medical", "health"]):
        domain_key = "clinic"
    elif any(k in text for k in ["customer", "crm", "lead", "client", "sales", "prospect"]):
        domain_key = "crm"
    elif any(k in text for k in ["booking", "hotel", "reservation", "room", "guest"]):
        domain_key = "booking"
    elif any(k in text for k in ["employee", "staff", "workforce", "hr", "payroll"]):
        domain_key = "employee"

    template = DOMAIN_TEMPLATES[domain_key]

    # Extract custom title if mentioned
    project_name = template["project_name"]
    title_match = re.search(r"(?:build|create|make|developing|want a|need a)\s+([a-z0-9\s]{3,35}?)(?:system|app|application|platform|portal)", text)
    if title_match:
        extracted = title_match.group(1).strip().title() + " " + "System"
        if len(extracted) > 8 and "New" not in extracted:
            project_name = extracted

    slug = slugify(project_name)

    # Detect explicit pages in transcript
    pages = list(template["pages"])
    if "login page" in text and not any(p.slug == "login_page" for p in pages):
        pages.append(PageSpec(title="Login", slug="login_page", type="login", description="User authentication and sign-in."))
    if "settings page" in text and not any(p.slug == "settings_page" for p in pages):
        pages.append(PageSpec(title="Settings", slug="settings_page", type="settings", description="System preferences and settings."))

    # Extract user roles mentioned
    user_roles = ["Admin", "User"]
    if "manager" in text and "Manager" not in user_roles:
        user_roles.append("Manager")
    if "doctor" in text and "Doctor" not in user_roles:
        user_roles.append("Doctor")

    unsupported = []
    if "payment" in text or "stripe" in text or "credit card" in text:
        unsupported.append("Payment processing integration requires live third-party gateway keys.")
    if "ai recommendation" in text or "smart ai" in text:
        unsupported.append("Machine learning recommendation engine deferred until AI provider integration.")

    api_endpoints = _build_default_api_endpoints(template["entity_plural"], template["entity_name"])

    return ProjectSpecification(
        project_name=project_name,
        project_slug=slug,
        purpose=template["purpose"],
        industry=template["industry"],
        entity_name=template["entity_name"],
        entity_plural=template["entity_plural"],
        fields=template["fields"],
        pages=pages,
        features=template["features"],
        user_roles=user_roles,
        backend_framework="FastAPI",
        database_type="SQLite",
        api_endpoints=api_endpoints,
        unsupported_requirements=unsupported,
        generation_notes=[
            f"Deterministic domain analysis identified category: {template['industry']}.",
            "All boilerplate and data contracts synthesized rule-based."
        ],
        metadata={"source": "transcript_analysis", "detected_domain": domain_key}
    )


def _build_default_api_endpoints(plural: str, singular: str) -> List[ApiEndpointSpec]:
    return [
        ApiEndpointSpec(method="GET", path=f"/api/{plural}", description=f"List all {plural}"),
        ApiEndpointSpec(method="GET", path=f"/api/{plural}/{{id}}", description=f"Retrieve single {singular} by ID"),
        ApiEndpointSpec(method="POST", path=f"/api/{plural}", description=f"Create a new {singular}"),
        ApiEndpointSpec(method="PUT", path=f"/api/{plural}/{{id}}", description=f"Update existing {singular} record"),
        ApiEndpointSpec(method="DELETE", path=f"/api/{plural}/{{id}}", description=f"Delete a {singular} record"),
        ApiEndpointSpec(method="GET", path="/api/stats", description="Aggregate metrics for dashboard widgets"),
    ]

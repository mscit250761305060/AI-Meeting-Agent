import json
from pathlib import Path
import concurrent.futures
from utilities.llm_utils import generate_content_with_retry
from types import SimpleNamespace
from config import get_model
import re

def check_tsx_syntax(code: str):
    """Basic Agentic Loop Validator for TSX"""
    if not code: return False, "Code is empty"
    if "export default" not in code and "export function" not in code and "export const" not in code:
        return False, "Missing export statement"
    return True, "Valid"

def _build_page_map(pages):
    page_map = []
    for page in pages:
        page_name = page.lower().strip()
        base_name = re.sub(r'[^a-z0-9]+', '_', page_name).strip('_')
        # Convert snake_case to PascalCase for React component names
        pascal_name = ''.join(word.capitalize() for word in base_name.split('_'))
        module_name = pascal_name + ".tsx"
        
        route = f"/{base_name.replace('_', '-')}"
        if any(kw in route for kw in ["home", "landing", "index"]):
            route = "/"
        elif "login" in route:
            route = "/login"
        elif "register" in route or "signup" in route:
            route = "/register"
        elif "forgot" in route:
            route = "/forgot-password"
        elif "reset" in route:
            route = "/reset-password"
            
        roles = []
        if "admin" in route: roles.append("Admin")
        elif "restaurant" in route or "menu" in route or "owner" in route: roles.append("Restaurant Owner")
        elif "customer" in route or "cart" in route or "checkout" in route or "track" in route or "favorite" in route: roles.append("Customer")
        
        showInSidebar = not any(k in route for k in ['login', 'register', 'auth', 'forgot', 'reset', 'signup', 'signin'])
        
        page_map.append({
            "label": page,
            "filename": module_name,
            "componentName": pascal_name,
            "path": route,
            "roles": roles,
            "showInSidebar": showInSidebar
        })
    return page_map

def _generate_tsx_component(comp, requirements):
    design_system = requirements.get("ui_ux_design", {})
    ds_ctx = f"GLOBAL UI/UX DESIGN SYSTEM:\n{json.dumps(design_system, indent=2)}\n" if design_system else ""
    
    prompt = f"""
    You are an elite Senior Frontend Engineer. Generate a highly reusable, visually stunning React TSX Component: '{comp.get('name')}'
    Description: {comp.get('description')}
    Project Requirements: {json.dumps({k: v for k, v in requirements.items() if k not in ['backend_schema', 'ui_ux_design']})}

    {ds_ctx}

    RULES:
    1. Export a default or named React functional component using TypeScript.
    2. USE TAILWIND CSS: Use the classes defined in the GLOBAL DESIGN SYSTEM. Apply modern UI principles (glassmorphism, soft shadows, rounded corners).
    3. UI QUALITY & ANIMATION: Use `lucide-react` for icons. Add subtle micro-animations (e.g. `transition-all duration-300 hover:scale-105 active:scale-95`).
    4. ROBUSTNESS: Ensure components gracefully handle missing props or loading states.
    5. COMPREHENSIVE FORMS: If generating a registration or signup form, you MUST include fields for Full Name, Email Address, Password, and Confirm Password at minimum.
    6. PRODUCTION & UI/UX REQUIREMENTS: Create a modern, premium, professional UI with excellent UX (looks like a high-quality SaaS product). Use consistent design (typography, spacing, colors). No placeholder content. No dummy functionality. Every feature must work end-to-end.
    
    Output ONLY the raw TSX code wrapped in ```tsx ... ``` markdown.
    """
    
    for attempt in range(3):
        response = generate_content_with_retry(
            model_name=get_model("page_generator"),
            contents=prompt,
            config=SimpleNamespace(temperature=0.1, max_output_tokens=4096)
        )
        code = response.text.strip()
        code = code.strip()
        if code.startswith("```tsx"): code = code[6:].strip()
        elif code.startswith("```typescript"): code = code[13:].strip()
        if code.startswith("```"): code = code[3:].strip()
        if code.endswith("```"): code = code[:-3].strip()
        
        valid, err = check_tsx_syntax(code)
        if valid:
            from server.ws_manager import manager
            try: manager.broadcast_sync({"action": "log", "message": f"✅ Component '{comp.get('name')}' generated."})
            except: pass
            return code
            
        prompt += f"\n\nERROR: {err}. Please fix the syntax error."
    
    return code

def _generate_tsx_page(entry, page_map, requirements):
    backend_schema = requirements.get("backend_schema", "")
    schema_ctx = f"Backend Schemas:\n{backend_schema}\n" if backend_schema else ""
    
    components = requirements.get("blueprint", {}).get("frontend_components", [])
    components_ctx = f"Available Components in '../components/':\n" + "\n".join([f"- {c['name']}.tsx" for c in components])
    
    available_routes = ", ".join([p['path'] for p in page_map])

    design_system = requirements.get("ui_ux_design", {})
    ds_ctx = f"GLOBAL UI/UX DESIGN SYSTEM (Use these classes):\n{json.dumps(design_system, indent=2)}\n" if design_system else ""
    
    prompt = f"""
    You are an elite React/Next.js Principal Engineer building a stunning, premium web application.
    Generate the COMPLETE React TSX Component for the '{entry["label"]}' page.
    Component Name must be: {entry['componentName']}
    
    Project Requirements:
    {json.dumps({k: v for k, v in requirements.items() if k not in ['backend_schema', 'blueprint', 'ui_ux_design']}, indent=4)}
    
    {schema_ctx}
    {components_ctx}
    {ds_ctx}
    
    If you use any components, import them. e.g. `import {{ Card }} from '../components/Card';`
    
    RULES:
    1. Export default the component (`export default function {entry['componentName']}() {{ ... }}`).
    2. DO NOT GENERATE A GLOBAL SIDEBAR, TOPBAR, OR LAYOUT WRAPPER! Your component will be rendered inside a `<main>` container of a global layout. Just generate the content of the page.
    3. USE REACT HOOKS (`useState`, `useEffect`) for state and API calls. Track `isLoading` and `error` states for ALL API requests.
    4. Use `import {{ api }} from '../api';` to make backend requests (`await api.get('/api/endpoint')`). IMPORTANT: `api.ts` directly returns the JSON payload (not an axios object). Do NOT use `response.data` or `const {{ data }} =`, use `response` directly!
    5. Use `react-router-dom` hooks like `useNavigate` for navigation.
    6. USE TAILWIND CSS: Make it look like a 2026 SaaS startup (lucide-react icons, glassmorphism, subtle gradients, rounded-2xl, soft shadow-xl).
    7. ACTUAL CHARTS REQUIRED: NEVER use placeholders for charts. ALWAYS implement real interactive charts using `recharts` (e.g. `LineChart`, `BarChart`, `ResponsiveContainer`).
    8. LOADING STATES: Never show "$undefined". When `isLoading` is true, render a beautiful Tailwind Skeleton loader (use classes like `animate-pulse bg-gray-200 rounded-lg`).
    9. ERROR HANDLING: Wrap API calls in try/catch. If API fails, set state with realistic MOCK DATA so the UI never crashes. Show toast notifications.
    10. CROSS-LINKING: Login pages MUST contain a visible "Sign Up" link to `/register`. Register pages MUST contain a "Log In" link to `/login`.
    11. AVAILABLE ROUTES: You can only navigate to the following paths: {available_routes}.
    12. FULLY WORKING CRUD: If there are actions like 'Add', 'Create', 'New', or 'Edit', YOU MUST IMPLEMENT A FULLY WORKING MODAL (Popup). Do not leave them as dummy buttons. Use a boolean state (e.g. `isModalOpen`) to show/hide a fixed overlay modal.
    13. FORM STATE: Inside the modal, render a proper form with inputs for the required data. Use `useState` to track the form data (e.g. `formData`, `setFormData`).
    14. API SUBMISSION: When the modal form is submitted, call the appropriate backend API (e.g. `await api.post('/api/endpoint', formData)`). On success, close the modal and re-fetch the data list so the UI updates instantly!
    15. REGISTRATION FORMS: If generating a Register or Sign Up page/component, the form MUST include comprehensive fields such as Full Name, Email Address, Password, and Confirm Password (and Role if applicable). Do NOT just use email and password.
    16. POST-AUTH NAVIGATION: In Login, Register, Sign In, or Sign Up pages, when the form is submitted successfully, you MUST save the returned auth token (e.g. `localStorage.setItem('auth_token', '...')`) and immediately redirect the user to the dashboard using `navigate('/dashboard')`.
    17. PRODUCTION & UI/UX REQUIREMENTS: Create a modern, premium, professional UI with excellent UX (looks like a high-quality SaaS product). Use consistent design (typography, spacing, colors). No placeholder content. No dummy functionality. Every feature must work end-to-end.
    
    Output ONLY the raw TSX code wrapped in ```tsx ... ``` markdown.
    """

    for attempt in range(3):
        response = generate_content_with_retry(
            model_name=get_model("page_generator"),
            contents=prompt,
            config=SimpleNamespace(temperature=0.1, max_output_tokens=8192)
        )
        code = response.text.strip()
        code = code.strip()
        if code.startswith("```tsx"): code = code[6:].strip()
        if code.startswith("```typescript"): code = code[13:].strip()
        if code.startswith("```"): code = code[3:].strip()
        if code.endswith("```"): code = code[:-3].strip()
        
        valid, err = check_tsx_syntax(code)
        if valid:
            from server.ws_manager import manager
            try: manager.broadcast_sync({"action": "log", "message": f"✅ Page '{entry['label']}' generated."})
            except: pass
            return code
            
        prompt += f"\n\nERROR: {err}. Please fix the syntax error."
        
    return code


def generate_pages(requirements, project_path):
    project_path = Path(project_path)
    frontend_path = project_path / "frontend"
    src_path = frontend_path / "src"
    pages_path = src_path / "pages"
    pages_path.mkdir(exist_ok=True, parents=True)
    components_path = src_path / "components"
    components_path.mkdir(exist_ok=True, parents=True)
    
    # 1. Generate Components
    components = requirements.get("blueprint", {}).get("frontend_components", [])
    if components:
        print("Generating React Components...")
        import time
        def _worker_comp(comp):
            try:
                code = _generate_tsx_component(comp, requirements)
                if code:
                    (components_path / f"{comp['name']}.tsx").write_text(code, encoding="utf-8")
            except Exception as e:
                print(f"Error generating component {comp['name']}: {e}")
            time.sleep(4)
            
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            list(executor.map(_worker_comp, components))

    # 2. Generate Pages
    pages = requirements.get("pages", [])
    
    # Enforce Phase 6 UI/UX Requirements
    auth_pages = ["Login", "Register", "Forgot Password", "Reset Password"]
    for ap in reversed(auth_pages):
        if not any(ap.lower() in str(p).lower() for p in pages):
            pages.insert(0, ap)
            
            
    requirements["pages"] = pages

    page_map = _build_page_map(pages)

    import time
    def _worker(entry):
        try:
            print(f"Generating React Page: {entry['filename']}...")
            code = _generate_tsx_page(entry, page_map, requirements)
            if code:
                (pages_path / entry['filename']).write_text(code, encoding="utf-8")
        except Exception as e:
            print(f"Error generating {entry['filename']}: {e}")
        time.sleep(4) 

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        list(executor.map(_worker, page_map))

    # 3. Generate App.tsx (Router)
    print("Generating App.tsx to initialize React Router...")
    
    imports = []
    public_routes_jsx = []
    protected_routes_jsx = []
    sidebar_links = []
    
    # Determine the first non-public route to use as the post-login redirect
    dashboard_path = next((p['path'] for p in page_map if not any(kw in p['path'].lower() for kw in ['login', 'register', 'forgot', 'reset'])), '/')
    
    for p in page_map:
        imports.append(f"import {p['componentName']} from './pages/{p['componentName']}';")
        
        is_public = any(kw in p['path'].lower() for kw in ['login', 'register', 'forgot', 'reset'])
        
        if is_public:
            public_routes_jsx.append(f"        <Route path=\"{p['path']}\" element={{<PublicGuard><{p['componentName']} /></PublicGuard>}} />")
        else:
            protected_routes_jsx.append(f"        <Route path=\"{p['path']}\" element={{<Layout><AuthGuard allowedRoles={{{json.dumps(p['roles'])}}}><{p['componentName']} /></AuthGuard></Layout>}} />")
            
        if p['showInSidebar'] and not is_public:
            sidebar_links.append(f"            <Link to=\"{p['path']}\" className=\"px-4 py-3 text-sm font-medium text-slate-700 hover:text-brand hover:bg-slate-100 rounded-xl transition-all flex items-center gap-3\"><div className=\"w-2 h-2 rounded-full bg-brand/50\"></div>{p['label']}</Link>")
    
    default_path = page_map[0]['path'] if page_map else '/'
    app_tsx = f"""import React from 'react';
import {{ BrowserRouter as Router, Routes, Route, Link, useNavigate, Navigate }} from 'react-router-dom';
{chr(10).join(imports)}

function PublicGuard({{ children }}: {{ children: React.ReactNode }}) {{
  const token = localStorage.getItem('auth_token');
  if (token) return <Navigate to="{dashboard_path}" replace />;
  return <main className="min-h-screen bg-slate-50 flex flex-col">{{children}}</main>;
}}

function AuthGuard({{ children, allowedRoles }}: {{ children: React.ReactNode, allowedRoles?: string[] }}) {{
  const token = localStorage.getItem('auth_token');
  const userRole = localStorage.getItem('user_role');
  
  if (!token) return <Navigate to="/login" replace />;
  if (allowedRoles && allowedRoles.length > 0 && !allowedRoles.includes(userRole || '')) {{
      return <div className="p-8 text-center text-red-500 font-bold">Unauthorized Access</div>;
  }}
  return <>{{children}}</>;
}}

function Layout({{ children }}: {{ children: React.ReactNode }}) {{
  const navigate = useNavigate();
  
  const handleLogout = () => {{
    localStorage.clear();
    navigate('/login');
  }};

  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden font-sans selection:bg-brand/20">
      <aside className="w-[280px] bg-white border-r border-slate-200 hidden md:flex flex-col shadow-sm z-10">
        <div className="h-16 flex items-center px-6 border-b border-slate-100">
          <div className="font-bold text-xl text-slate-900 tracking-tight flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-brand flex items-center justify-center text-white font-black text-sm">AI</div>
            Workspace
          </div>
        </div>
        <nav className="flex-1 p-4 flex flex-col gap-1.5 overflow-y-auto">
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 px-2 mt-2">Menu</div>
{chr(10).join(sidebar_links)}
        </nav>
        <div className="p-4 border-t border-slate-100 bg-slate-50/50">
          <button onClick={{handleLogout}} className="w-full flex items-center gap-3 px-4 py-3 text-sm font-medium text-red-600 hover:bg-red-50 rounded-xl transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" x2="9" y1="12" y2="12"></line></svg>
            Sign Out
          </button>
        </div>
      </aside>
      <div className="flex-1 flex flex-col h-full overflow-hidden relative">
        <header className="h-16 bg-white/80 backdrop-blur-md border-b border-slate-200 flex items-center justify-between px-8 sticky top-0 z-20">
           <div className="text-sm text-slate-500 font-medium">Dashboard Overview</div>
           <div className="flex items-center gap-4">
              <div className="w-8 h-8 rounded-full bg-slate-200 border-2 border-white shadow-sm"></div>
           </div>
        </header>
        <main className="flex-1 overflow-y-auto p-8 bg-slate-50/50">
          <div className="max-w-7xl mx-auto">
            {{children}}
          </div>
        </main>
      </div>
    </div>
  );
}}

export default function App() {{
  return (
    <Router>
        <Routes>
{chr(10).join(public_routes_jsx)}
{chr(10).join(protected_routes_jsx)}
          {{/* Default fallback if root wasn't explicitly generated */}}
          <Route path="/" element={{
            localStorage.getItem('auth_token') ? 
            <div className="p-8 text-center text-slate-600 mt-20">
              <h2 className="text-3xl font-bold text-slate-800 mb-4">Authentication Successful!</h2>
              <p className="mb-6">You have securely logged into the system.</p>
              <button 
                onClick={{() => {{ localStorage.clear(); window.location.href = '/login'; }}}}
                className="px-6 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl transition-all shadow-md font-medium"
              >
                Sign Out
              </button>
            </div>
            : <Navigate to="{default_path}" replace />
          }} />
          <Route path="*" element={{<div className="p-8 text-center text-gray-500 text-xl">404 Not Found</div>}} />
        </Routes>
    </Router>
  );
}}
"""
    (src_path / "App.tsx").write_text(app_tsx, encoding="utf-8")

    return {"status": "react_pages_generated"}

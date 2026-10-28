from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)

def generate_frontend(requirements, project_path):
    project_path = Path(project_path).resolve()
    frontend_path = project_path / "frontend"
    frontend_path.mkdir(exist_ok=True, parents=True)
    
    src_path = frontend_path / "src"
    src_path.mkdir(exist_ok=True)
    pages_path = src_path / "pages"
    pages_path.mkdir(exist_ok=True)
    components_path = src_path / "components"
    components_path.mkdir(exist_ok=True)

    project_name = requirements.get("project_name") or requirements.get("project_title") or "AI App"
    clean_project_name = project_name.lower().replace(" ", "-")

    # 1. package.json
    package_json = {
        "name": clean_project_name,
        "private": True,
        "version": "0.0.0",
        "type": "module",
        "scripts": {
            "dev": "vite",
            "build": "tsc && vite build",
            "preview": "vite preview"
        },
        "dependencies": {
            "react": "^18.2.0",
            "react-dom": "^18.2.0",
            "react-router-dom": "^6.22.3",
            "lucide-react": "^0.359.0",
            "react-hot-toast": "^2.4.1",
            "recharts": "^2.12.7",
            "zustand": "^4.5.2",
            "clsx": "^2.1.0",
            "tailwind-merge": "^2.2.2"
        },
        "devDependencies": {
            "@types/react": "^18.2.66",
            "@types/react-dom": "^18.2.22",
            "@vitejs/plugin-react": "^4.2.1",
            "autoprefixer": "^10.4.19",
            "postcss": "^8.4.38",
            "tailwindcss": "^3.4.3",
            "typescript": "^5.2.2",
            "vite": "^5.2.0"
        }
    }
    (frontend_path / "package.json").write_text(json.dumps(package_json, indent=2), encoding="utf-8")

    # 2. Vite Config
    vite_config = """import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true
      }
    }
  }
})
"""
    (frontend_path / "vite.config.ts").write_text(vite_config, encoding="utf-8")

    # 3. TS Configs
    tsconfig = """{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": false,
    "noUnusedLocals": false,
    "noUnusedParameters": false,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
"""
    (frontend_path / "tsconfig.json").write_text(tsconfig, encoding="utf-8")
    
    tsconfig_node = """{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true,
    "strict": false
  },
  "include": ["vite.config.ts"]
}
"""
    (frontend_path / "tsconfig.node.json").write_text(tsconfig_node, encoding="utf-8")

    # 4. Tailwind & PostCSS
    tailwind_config = """/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: '#0ea5e9',
        brandHover: '#0284c7'
      },
      animation: {
        'fade-in': 'fadeIn 0.5s ease-out',
        'slide-up': 'slideUp 0.4s ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        }
      }
    },
  },
  plugins: [],
}
"""
    (frontend_path / "tailwind.config.js").write_text(tailwind_config, encoding="utf-8")
    
    postcss_config = """export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
"""
    (frontend_path / "postcss.config.js").write_text(postcss_config, encoding="utf-8")

    # 5. index.html
    index_html = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/vite.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{project_name}</title>
  </head>
  <body class="bg-gray-50 text-gray-900 font-sans antialiased">
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
"""
    (frontend_path / "index.html").write_text(index_html, encoding="utf-8")

    # 6. src/index.css
    index_css = """@tailwind base;
@tailwind components;
@tailwind utilities;

@layer utilities {
  .glass-panel {
    @apply bg-white/70 backdrop-blur-md border border-white/30 shadow-xl rounded-2xl;
  }
  .premium-input {
    @apply w-full px-4 py-3 bg-white/50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-brand focus:border-transparent outline-none transition-all;
  }
  .premium-button {
    @apply w-full bg-brand hover:bg-brandHover text-white font-medium py-3 px-4 rounded-xl transition-all shadow-md hover:shadow-lg active:scale-95 disabled:opacity-70;
  }
  
  /* Skeleton Loader Animation */
  .skeleton {
    @apply animate-pulse bg-gray-200 rounded-md;
  }
  .skeleton-text {
    @apply h-4 bg-gray-200 rounded-md w-3/4 mb-2;
  }
  .skeleton-title {
    @apply h-6 bg-gray-200 rounded-md w-1/2 mb-4;
  }
}
"""
    (src_path / "index.css").write_text(index_css, encoding="utf-8")

    # 7. src/api.ts
    api_ts = """import toast from 'react-hot-toast';

export const api = {
    async request(endpoint: string, options: RequestInit = {}) {
        const token = localStorage.getItem('auth_token');
        const headers: Record<string, string> = {
            'Content-Type': 'application/json',
            ...(options.headers as Record<string, string>)
        };
        if (token) headers['Authorization'] = `Bearer ${token}`;

        try {
            const response = await fetch(endpoint, { ...options, headers });
            
            if (response.status === 401) {
                localStorage.removeItem('auth_token');
                window.location.href = '/login';
                return null;
            }
            
            const data = await response.json().catch(() => null);
            if (!response.ok) {
                const errMsg = data?.detail || data?.message || 'API Error';
                toast.error(errMsg);
                throw new Error(errMsg);
            }
            return data;
        } catch (err) {
            console.error('API Request Failed:', err);
            throw err;
        }
    },
    get(endpoint: string) { return this.request(endpoint, { method: 'GET' }); },
    post(endpoint: string, body: any) { return this.request(endpoint, { method: 'POST', body: JSON.stringify(body) }); },
    put(endpoint: string, body: any) { return this.request(endpoint, { method: 'PUT', body: JSON.stringify(body) }); },
    delete(endpoint: string) { return this.request(endpoint, { method: 'DELETE' }); }
};
"""
    (src_path / "api.ts").write_text(api_ts, encoding="utf-8")

    # 8. src/main.tsx
    main_tsx = """import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'
import { Toaster } from 'react-hot-toast'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
    <Toaster position="top-right" />
  </React.StrictMode>,
)
"""
    (src_path / "main.tsx").write_text(main_tsx, encoding="utf-8")

    # 9. src/App.tsx (will be overwritten by page_generator_agent, but give it a shell)
    app_tsx = """import { BrowserRouter } from 'react-router-dom';
export default function App() {
  return <BrowserRouter><div>Loading...</div></BrowserRouter>;
}
"""
    (src_path / "App.tsx").write_text(app_tsx, encoding="utf-8")

    print("React+Vite SPA UI Scaffold initialized successfully.")
    return {"status": "frontend_initialized"}

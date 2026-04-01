# Export routes for CodeForge AI - PWA and Desktop exports
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response
from motor.motor_asyncio import AsyncIOMotorClient
import os

export_router = APIRouter()

# Database connection
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "codeforge")
client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]


@export_router.get("/app/{project_id}")
async def serve_pwa_app(project_id: str):
    """Serve the generated app as an installable PWA"""
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    
    if not project:
        raise HTTPException(status_code=404, detail="Projet non trouvé")
    
    generated_code = project.get("generated_code", {})
    files = generated_code.get("files", [])
    app_name = project.get('name', 'Application')[:30]
    
    # Extract content from generated files
    css_content = ""
    jsx_content = ""
    
    for file in files:
        path = file.get('path', '')
        content = file.get('content', '')
        
        if path.endswith('.css'):
            css_content += content + "\n"
        elif path.endswith('.jsx') or (path.endswith('.js') and 'sw' not in path.lower()):
            jsx_content += content + "\n"
    
    # Create complete PWA HTML
    html = f'''<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="theme-color" content="#050505">
    <meta name="apple-mobile-web-app-title" content="{app_name}">
    <link rel="manifest" href="/api/pwa/manifest/{project_id}">
    <link rel="apple-touch-icon" href="/api/pwa/icon/{project_id}">
    <title>{app_name}</title>
    
    <!-- React & Babel for JSX -->
    <script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
    <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
    
    <!-- TailwindCSS -->
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {{
            theme: {{
                extend: {{
                    colors: {{
                        'cyber': '#E4FF00',
                        'neon': '#00FF66',
                        'dark': '#050505',
                        'darker': '#0F0F13'
                    }}
                }}
            }}
        }}
    </script>
    
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        html, body {{ 
            height: 100%; 
            height: -webkit-fill-available;
            overflow-x: hidden;
        }}
        body {{ 
            font-family: system-ui, -apple-system, BlinkMacSystemFont, sans-serif; 
            background: #050505; 
            color: #ffffff;
            min-height: 100vh;
            min-height: -webkit-fill-available;
        }}
        #root {{ min-height: 100vh; }}
        
        /* Custom scrollbar */
        ::-webkit-scrollbar {{ width: 8px; }}
        ::-webkit-scrollbar-track {{ background: #0F0F13; }}
        ::-webkit-scrollbar-thumb {{ background: #E4FF00; border-radius: 4px; }}
        
        /* Generated CSS */
        {css_content}
    </style>
</head>
<body class="bg-dark text-white">
    <div id="root"></div>
    
    <script type="text/babel">
        {jsx_content}
    </script>
    
    <script>
        // Register Service Worker
        if ('serviceWorker' in navigator) {{
            navigator.serviceWorker.register('/api/pwa/sw/{project_id}')
                .then(reg => console.log('✅ PWA Ready'))
                .catch(err => console.log('SW Error:', err));
        }}
        
        // Install prompt handling
        let installPrompt;
        window.addEventListener('beforeinstallprompt', (e) => {{
            e.preventDefault();
            installPrompt = e;
            showInstallButton();
        }});
        
        function showInstallButton() {{
            if (document.getElementById('pwa-install-btn')) return;
            
            const btn = document.createElement('button');
            btn.id = 'pwa-install-btn';
            btn.innerHTML = '📲 Installer';
            btn.style.cssText = `
                position: fixed;
                bottom: 20px;
                right: 20px;
                background: linear-gradient(135deg, #E4FF00 0%, #00FF66 100%);
                color: #050505;
                border: none;
                padding: 15px 30px;
                border-radius: 50px;
                font-weight: bold;
                font-size: 16px;
                cursor: pointer;
                z-index: 99999;
                box-shadow: 0 4px 20px rgba(228, 255, 0, 0.4);
                transition: transform 0.2s;
            `;
            btn.onmouseover = () => btn.style.transform = 'scale(1.05)';
            btn.onmouseout = () => btn.style.transform = 'scale(1)';
            btn.onclick = installApp;
            document.body.appendChild(btn);
        }}
        
        async function installApp() {{
            if (!installPrompt) return;
            installPrompt.prompt();
            const result = await installPrompt.userChoice;
            if (result.outcome === 'accepted') {{
                document.getElementById('pwa-install-btn')?.remove();
            }}
            installPrompt = null;
        }}
        
        // Check if already installed
        if (window.matchMedia('(display-mode: standalone)').matches) {{
            console.log('Running as installed PWA');
        }}
    </script>
</body>
</html>'''
    
    return HTMLResponse(content=html)


@export_router.get("/manifest/{project_id}")
async def get_manifest(project_id: str):
    """Serve PWA manifest"""
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    
    if not project:
        raise HTTPException(status_code=404, detail="Projet non trouvé")
    
    app_name = project.get('name', 'App')[:30]
    description = project.get('description', 'Application générée par CodeForge AI')[:200]
    
    manifest = {
        "name": app_name,
        "short_name": app_name[:12],
        "description": description,
        "start_url": f"/api/pwa/app/{project_id}",
        "scope": f"/api/pwa/",
        "display": "standalone",
        "background_color": "#050505",
        "theme_color": "#E4FF00",
        "orientation": "portrait-primary",
        "categories": ["utilities", "productivity"],
        "icons": [
            {
                "src": f"/api/pwa/icon/{project_id}?size=192",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any"
            },
            {
                "src": f"/api/pwa/icon/{project_id}?size=512",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable"
            }
        ],
        "screenshots": [],
        "prefer_related_applications": False
    }
    
    return JSONResponse(
        content=manifest,
        headers={"Content-Type": "application/manifest+json"}
    )


@export_router.get("/sw/{project_id}")
async def get_service_worker(project_id: str):
    """Serve Service Worker for offline support"""
    sw = f'''
const CACHE_NAME = 'codeforge-app-{project_id}-v1';
const OFFLINE_URL = '/api/pwa/app/{project_id}';

const ASSETS_TO_CACHE = [
    OFFLINE_URL,
    'https://unpkg.com/react@18/umd/react.production.min.js',
    'https://unpkg.com/react-dom@18/umd/react-dom.production.min.js',
    'https://unpkg.com/@babel/standalone/babel.min.js',
    'https://cdn.tailwindcss.com'
];

// Install
self.addEventListener('install', event => {{
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(ASSETS_TO_CACHE))
            .then(() => self.skipWaiting())
    );
}});

// Activate
self.addEventListener('activate', event => {{
    event.waitUntil(
        caches.keys().then(keys => {{
            return Promise.all(
                keys.filter(key => key !== CACHE_NAME)
                    .map(key => caches.delete(key))
            );
        }}).then(() => self.clients.claim())
    );
}});

// Fetch
self.addEventListener('fetch', event => {{
    event.respondWith(
        caches.match(event.request)
            .then(cached => {{
                if (cached) return cached;
                
                return fetch(event.request)
                    .then(response => {{
                        if (!response || response.status !== 200) return response;
                        
                        const clone = response.clone();
                        caches.open(CACHE_NAME)
                            .then(cache => cache.put(event.request, clone));
                        
                        return response;
                    }})
                    .catch(() => caches.match(OFFLINE_URL));
            }})
    );
}});
'''
    return Response(content=sw, media_type="application/javascript")


@export_router.get("/icon/{project_id}")
async def get_app_icon(project_id: str, size: int = 512):
    """Generate app icon as SVG"""
    # Simple colorful icon
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}">
    <defs>
        <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" style="stop-color:#E4FF00"/>
            <stop offset="100%" style="stop-color:#00FF66"/>
        </linearGradient>
    </defs>
    <rect width="{size}" height="{size}" rx="{size//5}" fill="url(#bg)"/>
    <text x="{size//2}" y="{size*0.65}" font-size="{size//2}" text-anchor="middle" fill="#050505">📱</text>
</svg>'''
    
    return Response(content=svg, media_type="image/svg+xml")


@export_router.get("/install/{project_id}")
async def get_install_page(project_id: str):
    """Installation page with QR code and instructions"""
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    
    if not project:
        raise HTTPException(status_code=404, detail="Projet non trouvé")
    
    app_name = project.get('name', 'Application')[:30]
    app_url = f"https://deepseek-forge.preview.emergentagent.com/api/pwa/app/{project_id}"
    
    html = f'''<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Installer {app_name}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body {{ font-family: system-ui, sans-serif; }}
    </style>
</head>
<body class="min-h-screen bg-[#050505] text-white flex items-center justify-center p-6">
    <div class="max-w-lg w-full bg-[#0F0F13] rounded-2xl p-8 text-center border border-white/10">
        <!-- App Icon -->
        <div class="w-24 h-24 bg-gradient-to-br from-[#E4FF00] to-[#00FF66] rounded-3xl mx-auto mb-6 flex items-center justify-center text-5xl shadow-lg shadow-[#E4FF00]/20">
            📱
        </div>
        
        <h1 class="text-3xl font-bold mb-2 text-[#E4FF00]">{app_name}</h1>
        <p class="text-gray-400 mb-8">Application générée par CodeForge AI</p>
        
        <!-- QR Code -->
        <div class="bg-white p-4 rounded-xl inline-block mb-6">
            <img src="https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={app_url}" 
                 alt="QR Code" class="w-48 h-48">
        </div>
        
        <p class="text-sm text-gray-400 mb-6">Scannez avec votre téléphone</p>
        
        <!-- Install Button -->
        <a href="{app_url}" 
           class="inline-block w-full py-4 px-8 bg-gradient-to-r from-[#E4FF00] to-[#00FF66] text-[#050505] font-bold text-lg rounded-xl hover:opacity-90 transition-opacity mb-4">
            🚀 Ouvrir l'application
        </a>
        
        <!-- Instructions -->
        <div class="mt-8 text-left bg-[#050505] rounded-xl p-6 border border-white/10">
            <h3 class="font-bold text-[#00FF66] mb-4">📲 Comment installer :</h3>
            <ol class="space-y-3 text-sm text-gray-300">
                <li class="flex gap-3">
                    <span class="text-[#E4FF00] font-bold">1.</span>
                    <span>Ouvrez le lien sur votre téléphone (Chrome recommandé)</span>
                </li>
                <li class="flex gap-3">
                    <span class="text-[#E4FF00] font-bold">2.</span>
                    <span>Cliquez sur le bouton <strong class="text-[#E4FF00]">"📲 Installer"</strong> qui apparaît</span>
                </li>
                <li class="flex gap-3">
                    <span class="text-[#E4FF00] font-bold">3.</span>
                    <span>L'app s'installe sur votre écran d'accueil !</span>
                </li>
            </ol>
        </div>
        
        <p class="mt-6 text-xs text-gray-500">
            💡 Fonctionne sur Android, iOS, Windows, Mac et Linux
        </p>
    </div>
</body>
</html>'''
    
    return HTMLResponse(content=html)

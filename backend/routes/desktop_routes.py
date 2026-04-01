# Desktop Export Routes - Generate real EXE files
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient
import os
import json
import subprocess
import shutil
import uuid
import asyncio
from datetime import datetime, timezone

desktop_router = APIRouter()

# Database connection
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "codeforge")
client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

# Build directory
BUILD_DIR = "/app/builds/desktop"
OUTPUT_DIR = "/app/builds/output"


async def build_electron_app(project_id: str, app_name: str, files: list):
    """Build Electron app in background"""
    build_path = f"{BUILD_DIR}/{project_id}"
    
    try:
        # Clean previous build
        if os.path.exists(build_path):
            shutil.rmtree(build_path)
        
        os.makedirs(build_path, exist_ok=True)
        os.makedirs(f"{build_path}/src", exist_ok=True)
        
        # Write source files
        for file in files:
            file_path = f"{build_path}/src/{file['path']}"
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(file['content'])
        
        # Create main.js for Electron
        main_js = f'''const {{ app, BrowserWindow, Menu }} = require('electron');
const path = require('path');

let mainWindow;

function createWindow() {{
    mainWindow = new BrowserWindow({{
        width: 1200,
        height: 800,
        minWidth: 800,
        minHeight: 600,
        webPreferences: {{
            nodeIntegration: false,
            contextIsolation: true
        }},
        title: '{app_name}',
        backgroundColor: '#050505',
        show: false,
        autoHideMenuBar: true
    }});
    
    Menu.setApplicationMenu(null);
    mainWindow.loadFile('src/index.html');
    mainWindow.once('ready-to-show', () => mainWindow.show());
    mainWindow.on('closed', () => {{ mainWindow = null; }});
}}

app.whenReady().then(createWindow);
app.on('window-all-closed', () => app.quit());
app.on('activate', () => {{ if (BrowserWindow.getAllWindows().length === 0) createWindow(); }});
'''
        with open(f"{build_path}/main.js", 'w') as f:
            f.write(main_js)
        
        # Create package.json
        safe_name = ''.join(c if c.isalnum() else '' for c in app_name.lower())[:20] or 'app'
        package_json = {
            "name": safe_name,
            "version": "1.0.0",
            "description": f"{app_name} - Desktop",
            "main": "main.js",
            "scripts": {
                "start": "electron .",
                "build": "electron-builder --win --x64"
            },
            "build": {
                "appId": f"com.codeforge.{safe_name}",
                "productName": app_name,
                "directories": {"output": "dist"},
                "win": {
                    "target": [{"target": "portable", "arch": ["x64"]}]
                },
                "portable": {"artifactName": f"{safe_name}.exe"}
            },
            "devDependencies": {
                "electron": "^28.0.0",
                "electron-builder": "^24.0.0"
            }
        }
        
        with open(f"{build_path}/package.json", 'w') as f:
            json.dump(package_json, f, indent=2)
        
        # Install dependencies
        process = await asyncio.create_subprocess_exec(
            'npm', 'install',
            cwd=build_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()
        
        # Build EXE
        process = await asyncio.create_subprocess_exec(
            'npm', 'run', 'build',
            cwd=build_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()
        
        # Find the generated EXE
        dist_path = f"{build_path}/dist"
        exe_file = None
        
        if os.path.exists(dist_path):
            for file in os.listdir(dist_path):
                if file.endswith('.exe'):
                    exe_file = f"{dist_path}/{file}"
                    break
        
        if exe_file and os.path.exists(exe_file):
            output_file = f"{OUTPUT_DIR}/{project_id}.exe"
            shutil.copy(exe_file, output_file)
            
            await db.builds.update_one(
                {"project_id": project_id},
                {"$set": {
                    "status": "completed",
                    "exe_path": output_file,
                    "completed_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            return output_file
        else:
            await db.builds.update_one(
                {"project_id": project_id},
                {"$set": {"status": "failed", "error": "EXE not generated"}}
            )
            return None
            
    except Exception as e:
        await db.builds.update_one(
            {"project_id": project_id},
            {"$set": {"status": "failed", "error": str(e)}}
        )
        return None


@desktop_router.get("/install/{project_id}")
async def get_desktop_install_page(project_id: str):
    """Desktop installation page with download link"""
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    
    if not project:
        raise HTTPException(status_code=404, detail="Projet non trouve")
    
    app_name = project.get('name', 'Application')[:30]
    
    # Check if build exists
    build = await db.builds.find_one({"project_id": project_id, "type": "desktop"}, {"_id": 0})
    
    build_status = "none"
    exe_ready = False
    
    if build:
        build_status = build.get("status", "none")
        if build_status == "completed" and os.path.exists(build.get("exe_path", "")):
            exe_ready = True
    
    # Build the HTML based on status
    download_section = ""
    if exe_ready:
        download_section = f'''
            <div class="bg-[#00FF66]/10 border border-[#00FF66]/30 rounded-xl p-4 mb-6">
                <p class="text-[#00FF66] font-bold">Votre application est prete !</p>
            </div>
            <a href="/api/desktop/download/{project_id}" 
               class="inline-block w-full py-4 px-8 bg-gradient-to-r from-[#E4FF00] to-[#00FF66] text-[#050505] font-bold text-lg rounded-xl hover:opacity-90 transition-opacity mb-4">
                Telecharger EXE
            </a>
        '''
    elif build_status == "building":
        download_section = '''
            <div class="bg-[#E4FF00]/10 border border-[#E4FF00]/30 rounded-xl p-6 mb-6">
                <div class="w-12 h-12 border-4 border-[#E4FF00] border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
                <p class="text-[#E4FF00] font-bold">Generation en cours...</p>
                <p class="text-gray-400 text-sm mt-2">Cela peut prendre 1-2 minutes</p>
            </div>
            <script>setTimeout(() => location.reload(), 10000);</script>
        '''
    else:
        download_section = f'''
            <button onclick="startBuild()" id="build-btn"
                    class="inline-block w-full py-4 px-8 bg-gradient-to-r from-[#E4FF00] to-[#00FF66] text-[#050505] font-bold text-lg rounded-xl hover:opacity-90 transition-opacity mb-4 cursor-pointer">
                Generer EXE
            </button>
        '''
    
    html = f'''<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Telecharger {app_name}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body {{ font-family: system-ui, sans-serif; }}
        @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
        .animate-spin {{ animation: spin 1s linear infinite; }}
    </style>
</head>
<body class="min-h-screen bg-[#050505] text-white flex items-center justify-center p-6">
    <div class="max-w-lg w-full bg-[#0F0F13] rounded-2xl p-8 text-center border border-white/10">
        <div class="w-24 h-24 bg-gradient-to-br from-[#E4FF00] to-[#00FF66] rounded-3xl mx-auto mb-6 flex items-center justify-center text-5xl shadow-lg shadow-[#E4FF00]/20">
            <svg class="w-12 h-12" fill="#050505" viewBox="0 0 24 24"><path d="M4 4h16v16H4V4zm2 2v12h12V6H6z"/><path d="M8 8h8v2H8V8zm0 4h8v2H8v-2z"/></svg>
        </div>
        
        <h1 class="text-3xl font-bold mb-2 text-[#E4FF00]">{app_name}</h1>
        <p class="text-gray-400 mb-6">Application Desktop pour Windows</p>
        
        <div id="status-container">
            {download_section}
        </div>
        
        <div class="mt-6 text-left bg-[#050505] rounded-xl p-6 border border-white/10">
            <h3 class="font-bold text-[#00FF66] mb-4">Instructions :</h3>
            <ol class="space-y-3 text-sm text-gray-300">
                <li class="flex gap-3">
                    <span class="text-[#E4FF00] font-bold">1.</span>
                    <span>Cliquez sur "Generer EXE"</span>
                </li>
                <li class="flex gap-3">
                    <span class="text-[#E4FF00] font-bold">2.</span>
                    <span>Attendez la generation (~1-2 min)</span>
                </li>
                <li class="flex gap-3">
                    <span class="text-[#E4FF00] font-bold">3.</span>
                    <span>Telechargez et lancez le fichier .exe</span>
                </li>
            </ol>
        </div>
        
        <p class="mt-6 text-xs text-gray-500">Compatible Windows 10/11 (64-bit)</p>
    </div>
    
    <script>
        async function startBuild() {{
            const btn = document.getElementById('build-btn');
            btn.disabled = true;
            btn.innerHTML = 'Demarrage...';
            
            try {{
                const response = await fetch('/api/desktop/build/{project_id}', {{ method: 'POST' }});
                if (response.ok) {{
                    location.reload();
                }} else {{
                    alert('Erreur lors du demarrage');
                    btn.disabled = false;
                    btn.innerHTML = 'Generer EXE';
                }}
            }} catch (e) {{
                alert('Erreur: ' + e.message);
                btn.disabled = false;
                btn.innerHTML = 'Generer EXE';
            }}
        }}
    </script>
</body>
</html>'''
    
    return HTMLResponse(content=html)


@desktop_router.post("/build/{project_id}")
async def start_desktop_build(project_id: str, background_tasks: BackgroundTasks):
    """Start building EXE in background"""
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    
    if not project:
        raise HTTPException(status_code=404, detail="Projet non trouve")
    
    existing = await db.builds.find_one({"project_id": project_id, "type": "desktop"})
    if existing and existing.get("status") == "building":
        return JSONResponse({"status": "already_building"})
    
    await db.builds.update_one(
        {"project_id": project_id, "type": "desktop"},
        {"$set": {
            "project_id": project_id,
            "type": "desktop",
            "status": "building",
            "started_at": datetime.now(timezone.utc).isoformat()
        }},
        upsert=True
    )
    
    app_name = project.get('name', 'App')[:30]
    files = project.get('generated_code', {}).get('files', [])
    
    background_tasks.add_task(build_electron_app, project_id, app_name, files)
    
    return JSONResponse({"status": "building"})


@desktop_router.get("/download/{project_id}")
async def download_exe(project_id: str):
    """Download the generated EXE file"""
    build = await db.builds.find_one({"project_id": project_id, "type": "desktop"}, {"_id": 0})
    
    if not build or build.get("status") != "completed":
        raise HTTPException(status_code=404, detail="EXE non disponible")
    
    exe_path = build.get("exe_path")
    
    if not exe_path or not os.path.exists(exe_path):
        raise HTTPException(status_code=404, detail="Fichier EXE non trouve")
    
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    app_name = project.get('name', 'Application')[:20] if project else 'Application'
    safe_name = ''.join(c if c.isalnum() else '_' for c in app_name)
    
    return FileResponse(
        path=exe_path,
        filename=f"{safe_name}.exe",
        media_type="application/octet-stream"
    )


@desktop_router.get("/status/{project_id}")
async def get_build_status(project_id: str):
    """Get build status"""
    build = await db.builds.find_one({"project_id": project_id, "type": "desktop"}, {"_id": 0})
    
    if not build:
        return JSONResponse({"status": "none"})
    
    return JSONResponse({
        "status": build.get("status"),
        "error": build.get("error")
    })

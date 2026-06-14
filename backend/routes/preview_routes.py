"""iter122 — Routes /preview/* extraites de server.py (3 endpoints + ~500 lignes de HTML demo).

  - GET /preview/{preview_id}            : preview d'un projet stocké dans db.previews
  - GET /preview/project/{project_id}    : preview combiné d'un projet (CSS+HTML+JS)
  - GET /preview/demo/{preview_type}     : pages demo statiques (web/app/pdf/etc.)

Helpers injectés : db.
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse


def build_preview_router(db):
    router = APIRouter()

    @router.get("/preview/{preview_id}")
    async def get_preview(preview_id: str):
        """Get preview HTML for generated content"""
        preview = await db.previews.find_one({"preview_id": preview_id}, {"_id": 0})
    
        if not preview:
            return HTMLResponse("<h1>Prévisualisation non trouvée</h1>", status_code=404)
    
        # Return HTML preview
        html_content = preview.get("html_content", "")
    
        if not html_content:
            # Generate preview from files
            files = preview.get("files", [])
            html_parts = ["<!DOCTYPE html><html><head><meta charset='utf-8'><title>Prévisualisation</title>"]
        
            # Add CSS
            for file in files:
                if file["path"].endswith(".css"):
                    html_parts.append(f"<style>{file['content']}</style>")
        
            html_parts.append("</head><body>")
        
            # Add HTML
            for file in files:
                if file["path"].endswith(".html"):
                    html_parts.append(file["content"])
        
            # Add JS
            for file in files:
                if file["path"].endswith(".js"):
                    html_parts.append(f"<script>{file['content']}</script>")
        
            html_parts.append("</body></html>")
            html_content = "\n".join(html_parts)
    
        return HTMLResponse(content=html_content)

    @router.get("/preview/project/{project_id}")
    async def get_project_preview(project_id: str):
        """Get preview for a specific project"""
        project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    
        if not project:
            return HTMLResponse("<h1>Projet non trouvé</h1>", status_code=404)
    
        generated_code = project.get("generated_code") or {}
        files = (generated_code.get("files") if isinstance(generated_code, dict) else None) or []
    
        # Generate combined HTML preview
        html_parts = ["""<!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Prévisualisation - """ + project.get("name", "Projet") + """</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: system-ui, sans-serif; background: #050505; color: #fff; }
        </style>"""]
    
        # Add CSS files
        for file in files:
            if file["path"].endswith(".css"):
                html_parts.append(f"<style>{file['content']}</style>")
    
        html_parts.append("</head><body>")
    
        # Add HTML content
        for file in files:
            if file["path"].endswith(".html"):
                # Extract body content if full HTML
                content = file["content"]
                if "<body>" in content:
                    start = content.find("<body>") + 6
                    end = content.find("</body>")
                    content = content[start:end] if end > start else content
                html_parts.append(content)
    
        # Add JS files
        for file in files:
            if file["path"].endswith(".js"):
                html_parts.append(f"<script>{file['content']}</script>")
    
        html_parts.append("</body></html>")
    
        return HTMLResponse(content="\n".join(html_parts))

    @router.get("/preview/demo/{preview_type}")
    async def get_demo_preview(preview_type: str):
        """Get demo preview pages for different formats (Web, PDF, DOCX, App)"""
    
        previews = {
            "web": """<!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Prévisualisation Web - CodeForge AI</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
                font-family: system-ui, -apple-system, sans-serif; 
                background: linear-gradient(135deg, #050505 0%, #0F0F13 100%); 
                color: #ffffff; 
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .container { max-width: 800px; padding: 3rem; text-align: center; }
            .icon { font-size: 5rem; margin-bottom: 2rem; }
            h1 { color: #E4FF00; font-size: 3rem; margin-bottom: 1rem; }
            p { color: #A1A1AA; font-size: 1.2rem; line-height: 1.8; margin-bottom: 2rem; }
            .badge { 
                display: inline-block; 
                background: #00FF66; 
                color: #050505; 
                padding: 0.5rem 1.5rem; 
                border-radius: 2rem; 
                font-weight: bold;
                margin: 0.5rem;
            }
            .features { 
                display: grid; 
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
                gap: 1.5rem; 
                margin-top: 3rem;
                text-align: left;
            }
            .feature { 
                background: rgba(255,255,255,0.05); 
                padding: 1.5rem; 
                border-radius: 0.5rem; 
                border: 1px solid rgba(255,255,255,0.1);
            }
            .feature h3 { color: #E4FF00; margin-bottom: 0.5rem; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="icon">🌐</div>
            <h1>Prévisualisation Web</h1>
            <p>Ceci est une démonstration de prévisualisation pour les applications web générées par CodeForge AI.</p>
            <span class="badge">HTML5</span>
            <span class="badge">CSS3</span>
            <span class="badge">JavaScript</span>
            <div class="features">
                <div class="feature">
                    <h3>Responsive</h3>
                    <p>S'adapte à tous les écrans</p>
                </div>
                <div class="feature">
                    <h3>Moderne</h3>
                    <p>Technologies récentes</p>
                </div>
                <div class="feature">
                    <h3>Rapide</h3>
                    <p>Performance optimisée</p>
                </div>
            </div>
        </div>
    </body>
    </html>""",

            "app": """<!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Prévisualisation Application - CodeForge AI</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
                font-family: system-ui, sans-serif; 
                background: #050505; 
                color: #fff;
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .phone-frame {
                width: 375px;
                height: 667px;
                background: #0F0F13;
                border-radius: 40px;
                padding: 20px;
                border: 3px solid #333;
                box-shadow: 0 25px 50px rgba(0,0,0,0.5);
            }
            .phone-screen {
                background: linear-gradient(180deg, #1a1a2e 0%, #0F0F13 100%);
                height: 100%;
                border-radius: 25px;
                overflow: hidden;
            }
            .status-bar {
                height: 44px;
                background: rgba(0,0,0,0.3);
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 0 20px;
                font-size: 12px;
            }
            .app-content {
                padding: 20px;
                text-align: center;
            }
            .app-icon {
                width: 80px;
                height: 80px;
                background: #E4FF00;
                border-radius: 20px;
                margin: 30px auto;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 2.5rem;
            }
            h2 { color: #E4FF00; margin-bottom: 10px; }
            p { color: #A1A1AA; font-size: 14px; }
            .btn {
                background: #E4FF00;
                color: #050505;
                border: none;
                padding: 15px 40px;
                border-radius: 25px;
                font-weight: bold;
                margin-top: 30px;
                cursor: pointer;
            }
        </style>
    </head>
    <body>
        <div class="phone-frame">
            <div class="phone-screen">
                <div class="status-bar">
                    <span>9:41</span>
                    <span>📶 🔋</span>
                </div>
                <div class="app-content">
                    <div class="app-icon">📱</div>
                    <h2>Mon Application</h2>
                    <p>Application mobile générée par CodeForge AI</p>
                    <button class="btn">Démarrer</button>
                </div>
            </div>
        </div>
    </body>
    </html>""",

            "pdf": """<!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Prévisualisation PDF - CodeForge AI</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
                font-family: 'Times New Roman', serif; 
                background: #404040; 
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 2rem;
            }
            .pdf-page {
                width: 595px;
                min-height: 842px;
                background: white;
                color: #000;
                padding: 60px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.5);
            }
            .header {
                border-bottom: 2px solid #E4FF00;
                padding-bottom: 20px;
                margin-bottom: 30px;
            }
            .logo { 
                font-size: 24px; 
                font-weight: bold; 
                color: #050505;
                display: flex;
                align-items: center;
                gap: 10px;
            }
            .logo span { background: #E4FF00; padding: 5px 15px; }
            h1 { font-size: 28px; margin: 30px 0 20px; color: #1a1a1a; }
            p { line-height: 1.8; margin-bottom: 15px; color: #333; }
            .section { margin: 30px 0; }
            .highlight { background: #FFFFD0; padding: 15px; border-left: 4px solid #E4FF00; }
            .footer { 
                margin-top: 50px; 
                padding-top: 20px; 
                border-top: 1px solid #ddd;
                font-size: 12px;
                color: #666;
                text-align: center;
            }
        </style>
    </head>
    <body>
        <div class="pdf-page">
            <div class="header">
                <div class="logo">
                    <span>CodeForge</span> AI
                </div>
            </div>
            <h1>Document de Prévisualisation</h1>
            <p>Ce document représente un aperçu de la génération PDF par CodeForge AI. Les documents générés peuvent inclure du texte formaté, des images et des tableaux.</p>
        
            <div class="section">
                <h2>Caractéristiques</h2>
                <ul style="margin-left: 20px; line-height: 2;">
                    <li>Génération automatique de contenu</li>
                    <li>Mise en page professionnelle</li>
                    <li>Export haute qualité</li>
                    <li>Compatible tous appareils</li>
                </ul>
            </div>
        
            <div class="highlight">
                <strong>Note:</strong> Les PDFs générés sont entièrement personnalisables et peuvent être modifiés selon vos besoins.
            </div>
        
            <div class="footer">
                Généré par CodeForge AI - Création Sans Limites
            </div>
        </div>
    </body>
    </html>""",

            "docx": """<!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Prévisualisation DOCX - CodeForge AI</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
                font-family: 'Calibri', 'Arial', sans-serif; 
                background: #2b579a; 
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 2rem;
            }
            .word-container {
                background: #f3f3f3;
                padding: 20px;
                border-radius: 5px;
            }
            .toolbar {
                background: #2b579a;
                color: white;
                padding: 10px 20px;
                border-radius: 5px 5px 0 0;
                font-size: 14px;
                display: flex;
                gap: 20px;
            }
            .doc-page {
                width: 612px;
                min-height: 792px;
                background: white;
                color: #000;
                padding: 72px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            }
            h1 { font-size: 26px; color: #2b579a; margin-bottom: 20px; }
            h2 { font-size: 18px; color: #2b579a; margin: 25px 0 15px; }
            p { line-height: 1.6; margin-bottom: 12px; }
            .table {
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }
            .table th, .table td {
                border: 1px solid #ddd;
                padding: 10px;
                text-align: left;
            }
            .table th { background: #2b579a; color: white; }
            .footer { 
                margin-top: 40px; 
                font-size: 11px; 
                color: #666;
                border-top: 1px solid #ddd;
                padding-top: 10px;
            }
        </style>
    </head>
    <body>
        <div class="word-container">
            <div class="toolbar">
                <span>📄 Document1.docx</span>
                <span>Fichier</span>
                <span>Édition</span>
                <span>Affichage</span>
            </div>
            <div class="doc-page">
                <h1>Document Word - Prévisualisation</h1>
                <p>Ce document représente un aperçu de la génération de fichiers DOCX par CodeForge AI. Les documents peuvent être édités dans Microsoft Word ou LibreOffice.</p>
            
                <h2>Fonctionnalités supportées</h2>
                <p>Les documents générés supportent de nombreuses fonctionnalités :</p>
            
                <table class="table">
                    <tr>
                        <th>Fonctionnalité</th>
                        <th>Support</th>
                    </tr>
                    <tr>
                        <td>Texte formaté</td>
                        <td>✅ Complet</td>
                    </tr>
                    <tr>
                        <td>Tableaux</td>
                        <td>✅ Complet</td>
                    </tr>
                    <tr>
                        <td>Images</td>
                        <td>✅ Complet</td>
                    </tr>
                    <tr>
                        <td>En-têtes/Pieds de page</td>
                        <td>✅ Complet</td>
                    </tr>
                </table>
            
                <div class="footer">
                    Page 1 sur 1 | Généré par CodeForge AI
                </div>
            </div>
        </div>
    </body>
    </html>""",

            "image": """<!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Prévisualisation Image - CodeForge AI</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
                font-family: system-ui, sans-serif; 
                background: #1a1a1a; 
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .image-preview {
                background: #0F0F13;
                padding: 20px;
                border-radius: 10px;
                text-align: center;
            }
            .image-frame {
                width: 600px;
                height: 400px;
                background: linear-gradient(135deg, #E4FF00 0%, #00FF66 50%, #00D4FF 100%);
                border-radius: 5px;
                display: flex;
                align-items: center;
                justify-content: center;
                color: #050505;
                font-size: 24px;
                font-weight: bold;
            }
            .info {
                margin-top: 15px;
                color: #A1A1AA;
                font-size: 14px;
            }
        </style>
    </head>
    <body>
        <div class="image-preview">
            <div class="image-frame">
                🖼️ Image Générée par IA
            </div>
            <div class="info">
                Format: PNG | Résolution: 1920x1080 | Taille: ~2.4 MB
            </div>
        </div>
    </body>
    </html>"""
        }
    
        content = previews.get(preview_type, previews["web"])
        return HTMLResponse(content=content)
    return router

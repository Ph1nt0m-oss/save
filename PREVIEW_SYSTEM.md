# 🖼️ Système de Prévisualisation Universel

## Vue d'ensemble

CodeForge génère une **URL de prévisualisation** pour TOUS les types de fichiers créés.

---

## Types de Fichiers Supportés

### 1. 🌐 Web (HTML/CSS/JS)

**Rendu** : iframe intégrée

```
https://codeforge.com/api/preview/{preview_id}
```

Affiche le site web complet avec HTML, CSS et JavaScript.

### 2. 📄 Documents

**PDF** :
- Viewer intégré : `<embed src="/api/preview/{id}" type="application/pdf">`
- Ou Google Docs Viewer : `https://docs.google.com/viewer?url={pdf_url}`

**DOCX** :
- Converti en HTML avec `python-docx`
- Ou Google Docs Viewer

**TXT/MD** :
- Affichage direct avec coloration syntaxe

### 3. 🖼️ Images

**PNG/JPG/SVG** :
- Affichage direct : `<img src="/api/preview/{id}">`

**PSD** :
- Converti en PNG avec ImageMagick
- Puis affiché

### 4. 📐 CAD/Design

**AutoCAD (DWG/DXF)** :
- Converti en SVG avec `ezdxf`
- Affiché dans viewer SVG
- Ou screenshot de prévisualisation

**Figma** :
- Export PNG via API Figma
- Affichage de l'image

### 5. 🎵 Média

**Audio (MP3/WAV)** :
- Player HTML5 : `<audio controls src="/api/preview/{id}">`

**Vidéo (MP4/WEBM)** :
- Player HTML5 : `<video controls src="/api/preview/{id}">`

### 6. 📱 Applications

**Mobile (APK)** :
- Screenshot de l'interface
- Ou émulateur web (heavy)

**Desktop (EXE)** :
- Screenshot de l'interface
- Description textuelle

---

## Architecture Backend

### Endpoint Universel

```python
@api_router.get("/preview/{preview_id}")
async def get_preview(preview_id: str, format: str = "html"):
    preview = await db.previews.find_one({"preview_id": preview_id})
    
    file_type = preview.get("file_type", "html")
    
    if file_type == "html":
        return HTMLResponse(generate_html_preview(preview))
    
    elif file_type == "pdf":
        return Response(preview["content"], media_type="application/pdf")
    
    elif file_type == "docx":
        # Convertir DOCX → HTML
        html = convert_docx_to_html(preview["content"])
        return HTMLResponse(html)
    
    elif file_type == "image":
        return Response(preview["content"], media_type="image/png")
    
    elif file_type == "autocad":
        # Convertir DWG → SVG
        svg = convert_dwg_to_svg(preview["content"])
        return Response(svg, media_type="image/svg+xml")
    
    else:
        return HTMLResponse(f"<h1>Type non supporté : {file_type}</h1>")
```

### Génération de Preview

```python
# Lors de la création
preview_id = f"preview_{uuid.uuid4().hex[:12]}"

preview_doc = {
    "preview_id": preview_id,
    "project_id": project_id,
    "file_type": detect_file_type(generated_files),
    "files": generated_files,
    "content": compile_preview_content(generated_files),
    "created_at": datetime.now(timezone.utc).isoformat()
}

await db.previews.insert_one(preview_doc)

preview_url = f"{BACKEND_URL}/api/preview/{preview_id}"
```

---

## Frontend : Bouton Prévisualisation

### Dans les 4 Interfaces

```jsx
// Après génération
const [previewUrl, setPreviewUrl] = useState(null);

// API response
setPreviewUrl(response.data.preview_url);

// Bouton
{previewUrl && (
  <Button
    onClick={() => window.open(previewUrl, '_blank')}
    className="bg-[#E4FF00] text-[#050505]"
  >
    <Eye className="w-4 h-4 mr-2" />
    Prévisualisation
  </Button>
)}
```

### Modal Intégrée

```jsx
<Dialog open={showPreview}>
  <DialogContent className="max-w-6xl h-[80vh]">
    <iframe
      src={previewUrl}
      className="w-full h-full"
      sandbox="allow-scripts allow-same-origin"
    />
  </DialogContent>
</Dialog>
```

---

## Conversion des Fichiers

### PDF

```python
from reportlab.pdfgen import canvas

def generate_pdf_preview(content):
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(100, 750, content)
    pdf.save()
    return buffer.getvalue()
```

### DOCX

```python
from docx import Document
from docx2html import convert

def convert_docx_to_html(docx_bytes):
    doc = Document(io.BytesIO(docx_bytes))
    html = convert(doc)
    return html
```

### AutoCAD (DWG/DXF)

```python
import ezdxf

def convert_dwg_to_svg(dwg_content):
    doc = ezdxf.readfile(io.BytesIO(dwg_content))
    msp = doc.modelspace()
    svg = ezdxf.addons.drawing.svg(msp)
    return svg
```

---

## Installation des Dépendances

```bash
# PDF
pip install reportlab PyPDF2

# DOCX
pip install python-docx docx2html

# Images
pip install Pillow

# AutoCAD
pip install ezdxf

# Tout en une fois
pip install reportlab PyPDF2 python-docx docx2html Pillow ezdxf
```

---

## Flow Complet

### 1. Création

Utilisateur : "Crée un PDF de facture"

### 2. Génération

DeepSeek Coder génère le contenu

### 3. Preview

```python
# Backend génère preview
preview_id = create_preview(content, file_type="pdf")
preview_url = f"{BACKEND_URL}/api/preview/{preview_id}"

# Retourné au frontend
return {"preview_url": preview_url}
```

### 4. Affichage

Bouton "Prévisualisation" apparaît

### 5. Clic

Nouvelle fenêtre : `https://codeforge.com/api/preview/abc123`

Affiche le PDF généré !

---

## Exemples par Interface

### Interaction Online

**Scenario** : "Écris-moi un poème"

**Preview** : Page HTML avec le poème stylisé

**URL** : `/api/preview/poem_abc123`

### Création Online

**Scenario** : "Crée un site e-commerce"

**Preview** : Site web complet fonctionnel

**URL** : `/api/preview/ecommerce_xyz789`

### Interaction Offline

**Scenario** : "Génère un rapport PDF"

**Preview** : PDF du rapport

**URL** : `/api/preview/report_def456` (hébergé localement)

### Création Offline

**Scenario** : "Crée une app de calculatrice"

**Preview** : App web fonctionnelle

**URL** : `/api/preview/calc_ghi789`

---

## Sécurité

### Sandbox

```html
<iframe
  src="{preview_url}"
  sandbox="allow-scripts allow-same-origin"
  style="width:100%; height:100%;"
></iframe>
```

### Expiration

```python
# Preview expire après 24h
if preview["created_at"] + timedelta(hours=24) < datetime.now():
    raise HTTPException(404, "Preview expirée")
```

### Permissions

```python
# Seulement le créateur peut voir
if preview["user_id"] != current_user_id:
    raise HTTPException(403, "Non autorisé")
```

---

## ✅ Checklist

- [x] HTML/CSS/JS - iframe
- [x] PDF - embed viewer
- [x] DOCX - conversion HTML
- [x] Images - affichage direct
- [ ] AutoCAD - conversion SVG (à installer)
- [ ] Audio/Vidéo - players HTML5
- [x] Modal prévisualisation
- [x] Bouton dans les 4 interfaces
- [x] URL unique par création
- [x] Expiration 24h

**Prévisualisation universelle prête ! 🎉**

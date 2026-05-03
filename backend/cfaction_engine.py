"""
cfaction_engine — fonctions PURES pour :
- Analyser des pièces jointes (PDF/DOCX/XLSX/PPTX/SQLite/Image)
- Construire des fichiers téléchargeables (DOCX/PDF/XLSX/PPTX/plain)
- Exécuter du code Python en sandbox sécurisé

Ce module ne dépend PAS de MongoDB ni de FastAPI. Les fonctions retournent
des `bytes` (ou des dicts plats) et peuvent être testées/réutilisées partout.
La persistance en DB reste dans server.py (_persist_generated / _store_generated).
"""
from __future__ import annotations

import asyncio
import base64
import io
import logging
import os
import shutil
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------- filename
def sanitize_filename(name: str, ext: str = "") -> str:
    """Nettoie un nom de fichier en conservant l'extension si présente."""
    stem = name or "file"
    extpart = ""
    if "." in stem:
        stem, _dot, extpart = stem.rpartition(".")
        extpart = f".{extpart}"
    base = "".join(c if (c.isalnum() or c in ("-", "_", " ")) else "_" for c in stem).strip()
    base = base.replace(" ", "_")[:80] or "file"
    return f"{base}{extpart}{ext}"


# ----------------------------------------------------------------- analyzers
def analyze_pdf(data: bytes) -> str:
    """Extrait le texte d'un PDF (max 40 pages, 30k caractères)."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        parts = []
        for i, page in enumerate(reader.pages[:40]):
            try:
                t = page.extract_text() or ""
            except Exception:
                t = ""
            if t.strip():
                parts.append(f"[Page {i + 1}]\n{t.strip()}")
        return "\n\n".join(parts)[:30000]
    except Exception as e:
        logger.warning(f"PDF analyze failed: {e}")
        return ""


def analyze_docx(data: bytes) -> str:
    """Extrait le texte d'un DOCX."""
    try:
        from docx import Document
        doc = Document(io.BytesIO(data))
        parts = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n".join(parts)[:30000]
    except Exception as e:
        logger.warning(f"DOCX analyze failed: {e}")
        return ""


def analyze_xlsx(data: bytes) -> str:
    """Extrait le contenu d'un XLSX (6 feuilles × 200 lignes max)."""
    try:
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(data), data_only=True, read_only=True)
        parts = []
        for sheet in wb.sheetnames[:6]:
            ws = wb[sheet]
            rows = []
            for row in ws.iter_rows(max_row=200, values_only=True):
                rows.append("\t".join(["" if v is None else str(v) for v in row]))
            parts.append(f"=== Feuille « {sheet} » ===\n" + "\n".join(rows))
        return "\n\n".join(parts)[:30000]
    except Exception as e:
        logger.warning(f"XLSX analyze failed: {e}")
        return ""


def analyze_pptx(data: bytes) -> str:
    """Extrait le texte d'un PPTX (max 60 slides)."""
    try:
        from pptx import Presentation
        prs = Presentation(io.BytesIO(data))
        parts = []
        for i, slide in enumerate(prs.slides):
            if i >= 60:
                break
            texts = []
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    texts.append(shape.text.strip())
            if texts:
                parts.append(f"[Slide {i + 1}]\n" + "\n".join(texts))
        return "\n\n".join(parts)[:30000]
    except Exception as e:
        logger.warning(f"PPTX analyze failed: {e}")
        return ""


def analyze_sqlite(data: bytes) -> str:
    """Liste tables + 10 premières lignes de chaque table d'un SQLite."""
    try:
        import sqlite3
        import tempfile as _tf
        with _tf.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        try:
            con = sqlite3.connect(tmp_path)
            cur = con.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in cur.fetchall()]
            parts = [f"Tables : {', '.join(tables)}"]
            for table in tables[:8]:
                try:
                    cur.execute(f"PRAGMA table_info('{table}')")
                    cols = [r[1] for r in cur.fetchall()]
                    parts.append(f"\n=== {table} ({', '.join(cols)}) ===")
                    cur.execute(f"SELECT * FROM '{table}' LIMIT 10")
                    rows = cur.fetchall()
                    for r in rows:
                        parts.append(str(r))
                except Exception:
                    pass
            con.close()
            return "\n".join(parts)[:30000]
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"SQLite analyze failed: {e}")
        return ""


# ----------------------------------------------------------------- builders (bytes)
def build_docx_bytes(title: str, sections: List[Dict[str, Any]]) -> bytes:
    from docx import Document
    doc = Document()
    doc.add_heading(title or "Document", 0)
    for sec in sections or []:
        h = (sec.get("heading") or "").strip()
        c = (sec.get("content") or "").strip()
        if h:
            doc.add_heading(h, 1)
        if c:
            for para in c.split("\n\n"):
                doc.add_paragraph(para)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def build_pdf_bytes(title: str, sections: List[Dict[str, Any]]) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.units import cm
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title=title or "Document")
    styles = getSampleStyleSheet()
    flow = [Paragraph(title or "Document", styles["Title"]), Spacer(1, 0.6 * cm)]
    for sec in sections or []:
        h = (sec.get("heading") or "").strip()
        c = (sec.get("content") or "").strip()
        if h:
            flow.append(Paragraph(h, styles["Heading1"]))
            flow.append(Spacer(1, 0.2 * cm))
        if c:
            for para in c.split("\n\n"):
                flow.append(Paragraph(para.replace("\n", "<br/>"), styles["BodyText"]))
                flow.append(Spacer(1, 0.2 * cm))
    doc.build(flow)
    return buf.getvalue()


def build_xlsx_bytes(sheets: List[Dict[str, Any]]) -> bytes:
    """sheets = [{"name","headers","rows","formulas"}]"""
    import xlsxwriter
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    header_fmt = wb.add_format({"bold": True, "bg_color": "#E4FF00", "border": 1})
    for idx, sh in enumerate(sheets or [{"name": "Feuille1", "rows": []}]):
        ws = wb.add_worksheet(sh.get("name") or f"Feuille{idx + 1}")
        row_offset = 0
        headers = sh.get("headers") or []
        if headers:
            for c, h in enumerate(headers):
                ws.write(0, c, h, header_fmt)
            row_offset = 1
        for r_i, row in enumerate(sh.get("rows") or []):
            for c_i, val in enumerate(row):
                ws.write(row_offset + r_i, c_i, val)
        for cell, formula in (sh.get("formulas") or {}).items():
            try:
                ws.write_formula(cell, formula)
            except Exception:
                pass
        if headers:
            ws.autofilter(0, 0, row_offset + len(sh.get("rows") or []) - 1, len(headers) - 1)
    wb.close()
    return buf.getvalue()


def build_pptx_bytes(title: str, slides: List[Dict[str, Any]]) -> bytes:
    from pptx import Presentation
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = title or "Présentation"
    for s in slides or []:
        layout = prs.slide_layouts[1]
        sl = prs.slides.add_slide(layout)
        sl.shapes.title.text = s.get("title") or ""
        body = sl.placeholders[1]
        tf = body.text_frame
        content = s.get("content") or ""
        lines = content.split("\n")
        tf.text = lines[0] if lines else ""
        for extra in lines[1:]:
            p = tf.add_paragraph()
            p.text = extra
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


# ----------------------------------------------------------------- Python sandbox
_SANDBOX_PREAMBLE = (
    "import sys, os\n"
    "os.environ.pop('EMERGENT_LLM_KEY', None)\n"
    "os.environ.pop('RESEND_API_KEY', None)\n"
    "os.environ.pop('MONGO_URL', None)\n"
    "os.environ.pop('DB_NAME', None)\n"
    "os.environ.pop('OLLAMA_BASE_URL', None)\n"
    "sys.setrecursionlimit(1000)\n"
    "# Auto-dump matplotlib figures to ./_figs_/ on plt.show() OR at the end.\n"
    "try:\n"
    "    import matplotlib\n"
    "    matplotlib.use('Agg')\n"
    "    import matplotlib.pyplot as _plt\n"
    "    import atexit as _atexit\n"
    "    os.makedirs('_figs_', exist_ok=True)\n"
    "    _fig_counter = [0]\n"
    "    def _dump_all_figs():\n"
    "        for fnum in _plt.get_fignums():\n"
    "            fig = _plt.figure(fnum)\n"
    "            try:\n"
    "                fig.savefig(f'_figs_/fig_{_fig_counter[0]:03d}.png', bbox_inches='tight', dpi=110)\n"
    "                _fig_counter[0] += 1\n"
    "            except Exception:\n"
    "                pass\n"
    "        _plt.close('all')\n"
    "    _orig_show = _plt.show\n"
    "    def _patched_show(*a, **kw):\n"
    "        _dump_all_figs()\n"
    "    _plt.show = _patched_show\n"
    "    _atexit.register(_dump_all_figs)\n"
    "except Exception:\n"
    "    pass\n"
)


def _empty_result(err: str = "") -> Dict[str, Any]:
    return {"stdout": "", "stderr": err, "exit_code": -1, "timed_out": False, "duration_ms": 0, "images": []}


async def run_python_sandbox(code: str, timeout_sec: int = 10) -> Dict[str, Any]:
    """Exécute du code Python dans un sous-processus avec timeout dur.

    Retourne { stdout, stderr, exit_code, timed_out, duration_ms, images[] }.
    Les figures matplotlib et les PNG/JPG au cwd sont automatiquement capturés en base64.
    """
    code = (code or "").strip()
    if not code:
        return _empty_result("Aucun code fourni.")

    tmp_dir = tempfile.mkdtemp(prefix="cfsandbox_")
    script_path = os.path.join(tmp_dir, "user_script.py")
    try:
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(_SANDBOX_PREAMBLE + "\n# --- user code ---\n" + code)

        start = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=tmp_dir,
                env={
                    "PATH": os.environ.get("PATH", "/usr/bin:/usr/local/bin"),
                    "HOME": tmp_dir,
                    "LC_ALL": "C.UTF-8",
                    "LANG": "C.UTF-8",
                    "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
                    "MPLBACKEND": "Agg",
                },
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout_sec)
                timed_out = False
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                except Exception:
                    pass
                try:
                    stdout_b, stderr_b = await proc.communicate()
                except Exception:
                    stdout_b, stderr_b = b"", b""
                timed_out = True
            duration_ms = int((time.monotonic() - start) * 1000)
            stdout = (stdout_b or b"").decode("utf-8", errors="replace")[:8000]
            stderr = (stderr_b or b"").decode("utf-8", errors="replace")[:4000]

            # Collect generated images
            images: List[Dict[str, str]] = []
            try:
                figs_dir = os.path.join(tmp_dir, "_figs_")
                if os.path.isdir(figs_dir):
                    for fn in sorted(os.listdir(figs_dir))[:6]:
                        fp = os.path.join(figs_dir, fn)
                        if os.path.isfile(fp) and os.path.getsize(fp) < 4_000_000:
                            with open(fp, "rb") as imf:
                                images.append({
                                    "filename": fn,
                                    "mime_type": "image/png",
                                    "data_base64": base64.b64encode(imf.read()).decode("ascii"),
                                })
                for fn in os.listdir(tmp_dir):
                    if len(images) >= 6:
                        break
                    if fn.lower().endswith((".png", ".jpg", ".jpeg")) and fn != "user_script.py":
                        fp = os.path.join(tmp_dir, fn)
                        if os.path.isfile(fp) and os.path.getsize(fp) < 4_000_000:
                            mt = "image/jpeg" if fn.lower().endswith((".jpg", ".jpeg")) else "image/png"
                            with open(fp, "rb") as imf:
                                images.append({
                                    "filename": fn,
                                    "mime_type": mt,
                                    "data_base64": base64.b64encode(imf.read()).decode("ascii"),
                                })
            except Exception as _imx:
                logger.warning(f"sandbox image collect failed: {_imx}")

            return {
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": proc.returncode if proc.returncode is not None else -1,
                "timed_out": timed_out,
                "duration_ms": duration_ms,
                "images": images,
            }
        except Exception as e:
            return _empty_result(f"Sandbox error: {e}")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

"""
🌐 FastAPI Web Server — Landing sahifalarni serve qiladi
Bot bilan birga ishlaydi (bot.py dan import qilinadi)
"""

import json
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# ─── Yo'llar ────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
MEDIA_DIR = BASE_DIR / "media"
TEMPLATES_DIR = BASE_DIR / "templates"
PAGES_FILE = DATA_DIR / "pages.json"

# Papkalar yaratish
DATA_DIR.mkdir(exist_ok=True)
MEDIA_DIR.mkdir(exist_ok=True)

# ─── FastAPI ─────────────────────────────────────────────────
app = FastAPI(title="QR Code Landing Pages")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Statik fayllar (media)
app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")


# ─── Yordamchi funksiyalar ──────────────────────────────────
def load_pages() -> dict:
    """pages.json dan barcha sahifalarni yuklash"""
    if not PAGES_FILE.exists():
        return {}
    try:
        with open(PAGES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def save_pages(pages: dict):
    """Sahifalarni pages.json ga saqlash"""
    with open(PAGES_FILE, "w", encoding="utf-8") as f:
        json.dump(pages, f, ensure_ascii=False, indent=2)


# ─── Landing sahifa ─────────────────────────────────────────
@app.get("/page/{page_id}", response_class=HTMLResponse)
async def landing_page(request: Request, page_id: str):
    """Sahifani ko'rsatish"""
    pages = load_pages()
    page = pages.get(page_id, {})

    has_content = bool(page.get("audio") or page.get("image") or page.get("text"))

    # Media URL'lar
    audio_url = f"/media/{page['audio']}" if page.get("audio") else None
    image_url = f"/media/{page['image']}" if page.get("image") else None
    text = page.get("text", "")
    title = page.get("title", "QR Page")

    return templates.TemplateResponse("page.html", {
        "request": request,
        "page_id": page_id,
        "has_content": has_content,
        "audio_url": audio_url,
        "image_url": image_url,
        "text": text,
        "title": title,
    })


# ─── Health check ────────────────────────────────────────────
@app.get("/")
async def root():
    return {"status": "ok", "service": "QR Code Landing Pages"}


@app.get("/health")
async def health():
    return {"status": "healthy"}

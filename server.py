# server.py — REST API & Web Dashboard Server for Affiliate Bot
import asyncio
import logging
import os
import re
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import httpx

from config import BOT_TOKEN, CHANNEL_ID, AFFILIATE_IDS, ADMIN_IDS
from database import (
    init_db,
    get_settings,
    update_all_settings,
    get_all_posted_items,
    delete_posted_item,
    mark_item_posted,
    get_database_stats
)
from converter import process_single_link, process_multi_platform_links
from scraper import (
    fetch_single_product_manual,
    fetch_multi_platform_deals_with_fallback,
    fetch_flashsale_independent_pool,
    STEALTH_AVAILABLE
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AffiliateDashboardServer")

app = FastAPI(title="Affiliate Bot Control Center", version="2.0.0")

# CORS middleware for seamless local and remote dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Engine Runtime State
ENGINE_STATE = {
    "is_running": True,
    "last_scan_time": None,
    "last_scanned_item": None,
    "last_error": None,
    "scan_count": 0,
    "auto_pilot_task": None
}

# Simple secure session token store (in-memory for admin sessions)
ACTIVE_SESSIONS = set()
ADMIN_SECRET = os.getenv("ADMIN_SECRET", "admin123")  # Default secret, or Telegram Admin ID 8503838227

# ---------------------------------------------------------------------------
# Background Auto-Pilot Worker
# ---------------------------------------------------------------------------
async def auto_pilot_loop():
    """Background task running scheduled autonomous scans according to interval."""
    logger.info("🚀 Autonomous Scanner Auto-Pilot Loop started")
    while True:
        try:
            settings = get_settings()
            if not settings.get("is_paused") and ENGINE_STATE["is_running"]:
                interval_minutes = max(1, settings.get("interval", 30))
                category = settings.get("category", "sport")
                min_discount = settings.get("min_discount", 20)
                
                logger.info(f"⏳ [Auto-Pilot] Executing scan for category '{category}', min_disc {min_discount}%...")
                deal = fetch_multi_platform_deals_with_fallback(
                    kategori=category,
                    preferred_discount=min_discount,
                    is_flashsale=False
                )
                
                if deal:
                    # Post automatically to channel
                    await post_deal_to_telegram(deal)
                    ENGINE_STATE["last_scanned_item"] = deal.get("title")
                    ENGINE_STATE["scan_count"] += 1
                
                ENGINE_STATE["last_scan_time"] = datetime.now().isoformat()
                await asyncio.sleep(interval_minutes * 60)
            else:
                await asyncio.sleep(10)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"❌ [Auto-Pilot Error]: {e}")
            ENGINE_STATE["last_error"] = str(e)
            await asyncio.sleep(30)

@app.on_event("startup")
async def startup_event():
    init_db()
    # Start autonomous background task
    ENGINE_STATE["auto_pilot_task"] = asyncio.create_task(auto_pilot_loop())

@app.on_event("shutdown")
async def shutdown_event():
    if ENGINE_STATE["auto_pilot_task"]:
        ENGINE_STATE["auto_pilot_task"].cancel()

# ---------------------------------------------------------------------------
# Telegram Posting Helper
# ---------------------------------------------------------------------------
async def post_deal_to_telegram(deal_data: dict) -> bool:
    """Send formatted product photo + caption + inline button directly to Telegram channel."""
    offers = deal_data.get("offers", [])
    title = deal_data.get("title", "Rekomendasi Produk Pilihan")
    image_url = deal_data.get("image_url")
    product_id = deal_data.get("main_product_id")

    if len(offers) <= 1:
        offer = offers[0] if offers else deal_data
        badge = offer.get("badge", "Shopee")
        price_promo = offer.get("price_promo", 0)
        price_str = f"Rp {price_promo:,}".replace(",", ".") if price_promo > 0 else "Cek di Link"
        disc = offer.get("discount_percent", 0)
        aff_url = offer.get("affiliate_url") or offer.get("original_url", "")
        desc = offer.get("description", "Temukan produk berkualitas tinggi ini. Stok & promo bisa berubah sewaktu-waktu!")

        caption = "✨ *HIDDEN GEM & REKOMENDASI SPESIAL* ✨\n\n"
        caption += f"📦 *{title}*\n\n"
        if price_promo > 0:
            caption += f"💰 *Harga Spesial:* *{price_str}*"
            if disc > 0:
                caption += f" (~{disc}% OFF)"
            caption += f" ({badge})\n"
        else:
            caption += f"💰 *Cek Harga Promo di Link* ({badge})\n"
        caption += f"\n📝 *Deskripsi Singkat:*\n_{desc}_\n\n"
        caption += f"🔗 *Link Pembelian:*\n{aff_url}"

        buttons = [[{"text": f"🛒 Beli Sekarang ({badge})", "url": aff_url}]]
    else:
        caption = "🔥 *PERBANDINGAN HARGA TERBAIK* 🔥\n\n"
        caption += f"📦 *{title}*\n\n"
        buttons = []
        for off in offers[:4]:
            badge = off.get("badge", "🛒")
            price_str = f"Rp {off.get('price_promo', 0):,}".replace(",", ".")
            disc = off.get("discount_percent", 0)
            aff_url = off.get("affiliate_url") or off.get("original_url", "")
            cheapest = " 🏆 Termurah!" if off.get("is_cheapest") else ""

            caption += f"{badge}: *{price_str}*"
            if disc > 0:
                caption += f" ({disc}% OFF)"
            caption += f"{cheapest}\n"
            buttons.append([{"text": f"{badge} — {price_str}", "url": aff_url}])

    reply_markup = {"inline_keyboard": buttons}

    async with httpx.AsyncClient(timeout=20) as client:
        if image_url:
            resp = await client.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                json={
                    "chat_id": CHANNEL_ID,
                    "photo": image_url,
                    "caption": caption,
                    "parse_mode": "Markdown",
                    "reply_markup": reply_markup
                }
            )
        else:
            resp = await client.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": CHANNEL_ID,
                    "text": caption,
                    "parse_mode": "Markdown",
                    "reply_markup": reply_markup
                }
            )
        
        if resp.status_code == 200:
            if product_id:
                mark_item_posted(product_id, title)
            return True
        else:
            logger.error(f"❌ Telegram Send Failed: {resp.text}")
            return False

# ---------------------------------------------------------------------------
# Pydantic Request Models
# ---------------------------------------------------------------------------
class LoginRequest(BaseModel):
    username_or_id: str
    password: Optional[str] = None

class ConvertRequest(BaseModel):
    url: str

class ScrapeSingleRequest(BaseModel):
    url: str

class PostManualRequest(BaseModel):
    title: str
    image_url: Optional[str] = None
    affiliate_url: str
    price_promo: Optional[int] = 0
    discount_percent: Optional[int] = 0
    badge: Optional[str] = "Shopee"
    description: Optional[str] = ""

class EngineControlRequest(BaseModel):
    action: str  # "start", "stop", "pause", "resume"

class SettingsUpdateRequest(BaseModel):
    category: str
    min_discount: int
    interval: int
    is_paused: int

class TriggerScanRequest(BaseModel):
    mode: str  # "flashsale", "auto", "20", "30", "50", "70"
    category: Optional[str] = None
    post_to_channel: Optional[bool] = True

# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.post("/api/auth/login")
async def login(req: LoginRequest):
    """Authenticate via Telegram Admin ID or Admin Password."""
    uid = req.username_or_id.strip()
    pwd = (req.password or "").strip()

    is_telegram_admin = uid.isdigit() and int(uid) in ADMIN_IDS
    is_password_admin = pwd == ADMIN_SECRET or uid == ADMIN_SECRET

    if is_telegram_admin or is_password_admin:
        token = f"sess_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uid}"
        ACTIVE_SESSIONS.add(token)
        return {
            "success": True,
            "token": token,
            "user": {
                "id": uid,
                "role": "Super Admin",
                "channel": CHANNEL_ID
            }
        }
    raise HTTPException(status_code=401, detail="Kredensial tidak valid. Masukkan ID Telegram Admin atau Password.")

@app.get("/api/engine/status")
async def get_engine_status():
    """Retrieve live status of scraper engine, settings, and stats."""
    settings = get_settings()
    stats = get_database_stats()
    
    status_label = "Running"
    if not ENGINE_STATE["is_running"] or settings.get("is_paused"):
        status_label = "Paused"

    return {
        "engine": {
            "status": status_label,
            "is_running": ENGINE_STATE["is_running"] and not settings.get("is_paused"),
            "stealth_available": STEALTH_AVAILABLE,
            "last_scan_time": ENGINE_STATE["last_scan_time"],
            "last_scanned_item": ENGINE_STATE["last_scanned_item"],
            "scan_count": ENGINE_STATE["scan_count"],
            "target_channel": CHANNEL_ID,
            "affiliate_ids": AFFILIATE_IDS
        },
        "settings": settings,
        "stats": stats
    }

@app.post("/api/engine/control")
async def control_engine(req: EngineControlRequest):
    """Start, stop, pause, or resume the scraper engine."""
    settings = get_settings()
    action = req.action.lower()

    if action == "start":
        ENGINE_STATE["is_running"] = True
        update_all_settings(settings["category"], settings["min_discount"], settings["interval"], 0)
    elif action == "stop":
        ENGINE_STATE["is_running"] = False
        update_all_settings(settings["category"], settings["min_discount"], settings["interval"], 1)
    elif action == "pause":
        update_all_settings(settings["category"], settings["min_discount"], settings["interval"], 1)
    elif action == "resume":
        ENGINE_STATE["is_running"] = True
        update_all_settings(settings["category"], settings["min_discount"], settings["interval"], 0)
    else:
        raise HTTPException(status_code=400, detail="Aksi tidak dikenal. Gunakan: start, stop, pause, resume.")

    return {"success": True, "action": action, "current_settings": get_settings()}

@app.post("/api/settings")
async def update_settings_endpoint(req: SettingsUpdateRequest):
    """Update scraping parameters (category, min_discount, interval, is_paused)."""
    update_all_settings(req.category, req.min_discount, req.interval, req.is_paused)
    return {"success": True, "settings": get_settings()}

@app.post("/api/engine/scan")
async def trigger_scan(req: TriggerScanRequest):
    """Trigger an immediate live scan and optionally post to Telegram channel."""
    settings = get_settings()
    cat = req.category or settings.get("category", "sport")
    mode = req.mode

    is_flashsale = (mode == "flashsale")
    DISCOUNT_MAP = {
        "flashsale": 0,
        "auto": settings.get("min_discount", 20),
        "20": 20,
        "30": 30,
        "50": 50,
        "70": 70,
    }
    target_discount = DISCOUNT_MAP.get(mode, 20)

    try:
        deal = fetch_multi_platform_deals_with_fallback(
            kategori=cat,
            preferred_discount=target_discount,
            is_flashsale=is_flashsale
        )

        if not deal:
            return {
                "success": False,
                "message": f"Tidak ada produk baru yang memenuhi kriteria diskon {target_discount}% pada kategori '{cat}'."
            }

        posted = False
        if req.post_to_channel:
            posted = await post_deal_to_telegram(deal)

        ENGINE_STATE["last_scan_time"] = datetime.now().isoformat()
        ENGINE_STATE["last_scanned_item"] = deal.get("title")
        ENGINE_STATE["scan_count"] += 1

        return {
            "success": True,
            "posted_to_channel": posted,
            "deal": deal
        }
    except Exception as e:
        logger.error(f"❌ Scan Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/convert")
async def convert_link(req: ConvertRequest):
    """Convert standard/shortlink product URL to official affiliate link."""
    raw_url = req.url.strip()
    if not raw_url:
        raise HTTPException(status_code=400, detail="URL produk wajib diisi.")

    converted = process_single_link(raw_url)
    
    # Detect platform
    platform = "shopee"
    badge = "Shopee"
    if "tokopedia" in raw_url:
        platform = "tokopedia"
        badge = "Tokopedia"
    elif "blibli" in raw_url:
        platform = "blibli"
        badge = "Blibli"
    elif "lazada" in raw_url:
        platform = "lazada"
        badge = "Lazada"
    elif "tiktok" in raw_url:
        platform = "tiktok"
        badge = "TikTok Shop"

    return {
        "success": True,
        "platform": platform,
        "badge": badge,
        "original_url": raw_url,
        "affiliate_url": converted,
        "is_converted": converted != raw_url
    }

@app.post("/api/scrape/single")
async def scrape_single_link(req: ScrapeSingleRequest):
    """Scrape product details from raw link using Scrapling engine."""
    raw_url = req.url.strip()
    if not raw_url:
        raise HTTPException(status_code=400, detail="URL produk wajib diisi.")

    try:
        product = fetch_single_product_manual(raw_url)
        if not product:
            raise HTTPException(status_code=404, detail="Gagal mengekstrak data dari link tersebut.")
        return {"success": True, "product": product}
    except Exception as e:
        logger.error(f"❌ Single Scrape Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/scrape/post-to-channel")
async def post_manual_to_channel(req: PostManualRequest):
    """Post an item directly to the configured Telegram channel."""
    deal_dict = {
        "title": req.title,
        "image_url": req.image_url,
        "platform": req.badge.lower(),
        "offers": [{
            "title": req.title,
            "price_promo": req.price_promo or 0,
            "discount_percent": req.discount_percent or 0,
            "badge": req.badge,
            "affiliate_url": req.affiliate_url,
            "description": req.description
        }]
    }

    success = await post_deal_to_telegram(deal_dict)
    if success:
        return {"success": True, "message": "Produk berhasil diposting ke Channel!"}
    raise HTTPException(status_code=500, detail="Gagal mengirim ke channel. Periksa izin admin bot pada Channel.")

@app.get("/api/items")
async def list_items(search: str = "", limit: int = 50, offset: int = 0):
    """List all products stored in the SQLite database."""
    items = get_all_posted_items(limit=limit, offset=offset, search=search)
    stats = get_database_stats()
    return {
        "items": items,
        "total": stats["total_posted"],
        "limit": limit,
        "offset": offset
    }

@app.delete("/api/items/{product_id}")
async def delete_item(product_id: str):
    """Remove a product from the database to allow re-posting."""
    deleted = delete_posted_item(product_id)
    if deleted:
        return {"success": True, "message": f"Item {product_id} berhasil dihapus."}
    raise HTTPException(status_code=404, detail="Item tidak ditemukan.")

# ---------------------------------------------------------------------------
# Serve Frontend Static Web Application
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)

# bot.py
import logging
import re

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes,
)

from database import init_db, get_settings, mark_item_posted
from scraper import fetch_single_product_manual, fetch_multi_platform_deals_with_fallback
from config import BOT_TOKEN, CHANNEL_ID, ADMIN_IDS

# ---------------------------------------------------------------------------
# Konfigurasi Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# State percakapan per user
user_states: dict[int, str] = {}


# ---------------------------------------------------------------------------
# HELPER: Format caption & tombol untuk posting ke channel
# ---------------------------------------------------------------------------
def format_caption_and_buttons(deal_data: dict) -> tuple[str, list]:
    """Buat caption Telegram dan tombol inline dari data produk."""
    platform = deal_data.get("platform", "shopee").lower()

    PLATFORM_META = {
        "tokopedia": ("🟢 Tokopedia",   "🛒 Cek Produk di Tokopedia"),
        "blibli":    ("🔵 Blibli",      "🛒 Cek Produk di Blibli"),
        "lazada":    ("🟠 Lazada",      "🛒 Cek Produk di Lazada"),
        "tiktok":    ("🎵 TikTok Shop", "🛒 Beli di TikTok Shop"),
    }
    badge, btn_label = PLATFORM_META.get(platform, ("🧡 Shopee", "🛒 Cek Produk & Beli Disini"))

    # Untuk format single-product (dari manual atau flash sale)
    offer = (
        deal_data.get("offers", [deal_data])[0]
        if "offers" in deal_data
        else deal_data
    )

    title      = offer.get("title", "Produk Pilihan")
    price_promo= offer.get("price_promo", 0)
    discount   = offer.get("discount_percent", 0)
    sold       = offer.get("sold_count", "")
    desc       = offer.get("description", "Temukan produk berkualitas tinggi ini. Stok & promo bisa berubah sewaktu-waktu!")
    aff_url    = offer.get("affiliate_url") or offer.get("original_url", "")
    badge      = offer.get("badge", badge)

    harga_str = f"Rp {price_promo:,}".replace(",", ".") if price_promo > 0 else "Cek link"

    caption  = "✨ *HIDDEN GEM & REKOMENDASI SPESIAL* ✨\n\n"
    caption += f"📦 *{title}*\n\n"
    if price_promo > 0:
        caption += f"💰 *Harga Spesial:* *{harga_str}*"
        if discount > 0:
            caption += f" (~{discount}% OFF)"
        caption += f" ({badge})\n"
    else:
        caption += f"💰 *Cek Harga Promo di Link* ({badge})\n"
    if sold:
        caption += f"📦 Terjual: {sold}\n"
    caption += f"\n📝 *Deskripsi Singkat:*\n_{desc}_\n\n"
    caption += f"🔗 *Link Pembelian:*\n{aff_url}"

    buttons = [[InlineKeyboardButton(btn_label, url=aff_url)]]
    return caption, buttons


def format_multi_offer_caption(deal_data: dict) -> tuple[str, list]:
    """Buat caption untuk format multi-marketplace (beberapa penawaran sekaligus)."""
    title    = deal_data.get("title", "Produk Diskon")
    offers   = deal_data.get("offers", [])
    category = deal_data.get("category", "")
    fallback = deal_data.get("is_fallback_deal", False)

    caption  = "🔥 *PERBANDINGAN HARGA TERBAIK* 🔥\n\n"
    caption += f"📦 *{title}*\n"
    if category:
        caption += f"🏷️ Kategori: {category}\n"
    if fallback:
        caption += "_(Produk terbaik yang tersedia saat ini)_\n"
    caption += "\n"

    buttons = []
    for offer in offers[:4]:  # Maks 4 penawaran
        badge     = offer.get("badge", "🛒")
        price_str = f"Rp {offer.get('price_promo', 0):,}".replace(",", ".")
        disc      = offer.get("discount_percent", 0)
        aff_url   = offer.get("affiliate_url") or offer.get("original_url", "")
        cheapest  = " 🏆 Termurah!" if offer.get("is_cheapest") else ""

        caption += f"{badge}: *{price_str}*"
        if disc > 0:
            caption += f" ({disc}% OFF)"
        caption += f"{cheapest}\n"

        buttons.append([InlineKeyboardButton(f"{badge} — {price_str}", url=aff_url)])

    return caption, buttons


# ---------------------------------------------------------------------------
# COMMAND: /start
# ---------------------------------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if ADMIN_IDS and user_id not in ADMIN_IDS:
        await update.message.reply_text(
            f"⛔ Maaf, Anda tidak memiliki akses ke bot ini. (ID Anda: {user_id})"
        )
        return

    user_states[user_id] = "MENU_UTAMA"
    await update.message.reply_text(
        "🎛 *CONTROL PANEL ADMIN*\nPilih opsi utama manajemen bot:",
        parse_mode="Markdown",
        reply_markup=_main_menu_keyboard(),
    )


def _main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Scan Kategori & Diskon",  callback_data="menu_scan")],
        [InlineKeyboardButton("🔗 Input Link Produk Manual", callback_data="menu_manual")],
        [InlineKeyboardButton("⚙️ Admin Access",             callback_data="menu_admin")],
    ])


# ---------------------------------------------------------------------------
# CALLBACK: Inline Keyboard Handler
# ---------------------------------------------------------------------------
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    user_id = query.from_user.id

    if ADMIN_IDS and user_id not in ADMIN_IDS:
        await query.answer("Akses ditolak.", show_alert=True)
        return

    await query.answer()
    data = query.data

    # ── Menu utama ──────────────────────────────────────────────────────────
    if data == "menu_scan":
        await query.message.edit_text(
            "🎯 *LANGKAH 1: PILIH MODE SCANNING*\n"
            "Pilih 'FLASHSALE' untuk ambil semua produk flashsale otomatis,\n"
            "atau tentukan target diskon:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⚡ OTOMATIS FLASHSALE (All Marketplace)", callback_data="scan_flashsale")],
                [InlineKeyboardButton("🔥 Auto Best Deals (diskon terbaik ada)",  callback_data="scan_auto")],
                [
                    InlineKeyboardButton("🎯 Min. 20%", callback_data="scan_20"),
                    InlineKeyboardButton("🔥 Min. 30%", callback_data="scan_30"),
                ],
                [
                    InlineKeyboardButton("⚡ Min. 50%", callback_data="scan_50"),
                    InlineKeyboardButton("💎 Min. 70%", callback_data="scan_70"),
                ],
                [InlineKeyboardButton("🔙 Kembali",    callback_data="kembali_menu_utama")],
            ]),
        )

    elif data == "menu_manual":
        user_states[user_id] = "INPUT_MANUAL"
        await query.message.edit_text(
            "🔗 *MODE INPUT LINK TUNGGAL AKTIF*\n"
            "Silakan kirim link produk (Shopee/Tokopedia/Blibli/Lazada/TikTok) di chat ini.",
            parse_mode="Markdown",
        )

    elif data == "menu_admin":
        settings = get_settings()
        await query.message.edit_text(
            f"⚙️ *Admin Access*\n\n"
            f"• Kategori aktif: `{settings.get('category', '-')}`\n"
            f"• Diskon minimum: `{settings.get('min_discount', 20)}%`\n"
            f"• Status: `{'⏸ Dijeda' if settings.get('is_paused') else '▶️ Berjalan'}`\n\n"
            "_Pengaturan tambahan dapat dikonfigurasi langsung di_ `config.py`.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Kembali", callback_data="kembali_menu_utama")]
            ]),
        )

    elif data == "kembali_menu_utama":
        user_states[user_id] = "MENU_UTAMA"
        await query.message.edit_text(
            "🎛 *CONTROL PANEL ADMIN*\nPilih opsi utama manajemen bot:",
            parse_mode="Markdown",
            reply_markup=_main_menu_keyboard(),
        )

    # ── Handler tombol SCAN ─────────────────────────────────────────────────
    elif data.startswith("scan_"):
        await _handle_scan(query, data)


async def _handle_scan(query, data: str):
    """Eksekusi scan & posting otomatis ke channel berdasarkan pilihan menu."""
    settings     = get_settings()
    kategori     = settings.get("category", "sport")
    is_flashsale = data == "scan_flashsale"

    # Tentukan target diskon dari callback data
    DISCOUNT_MAP = {
        "scan_flashsale": 0,
        "scan_auto":      settings.get("min_discount", 20),
        "scan_20":        20,
        "scan_30":        30,
        "scan_50":        50,
        "scan_70":        70,
    }
    target_discount = DISCOUNT_MAP.get(data, 20)

    await query.message.reply_text(
        f"⏳ Mencari produk terbaik...\n"
        f"{'🔥 Mode: Flash Sale' if is_flashsale else f'🎯 Target diskon: min. {target_discount}%'}\n"
        f"Kategori: *{kategori}*",
        parse_mode="Markdown",
    )

    try:
        deal_data = fetch_multi_platform_deals_with_fallback(
            kategori=kategori,
            preferred_discount=target_discount,
            is_flashsale=is_flashsale,
        )

        if not deal_data:
            await query.message.reply_text(
                "❌ Tidak ada produk yang memenuhi kriteria saat ini.\n"
                "Coba pilih mode diskon yang lebih rendah atau ganti kategori."
            )
            return

        offers    = deal_data.get("offers", [])
        image_url = deal_data.get("image_url", "")
        product_id= deal_data.get("main_product_id", "")

        # Format caption & tombol
        if len(offers) == 1:
            # Single offer (flash sale / satu marketplace)
            caption, buttons = format_caption_and_buttons(deal_data)
        else:
            # Multi-marketplace comparison
            caption, buttons = format_multi_offer_caption(deal_data)

        reply_markup = InlineKeyboardMarkup(buttons)

        # Post ke channel
        if image_url:
            await query.bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=image_url,
                caption=caption,
                parse_mode="Markdown",
                reply_markup=reply_markup,
            )
        else:
            await query.bot.send_message(
                chat_id=CHANNEL_ID,
                text=caption,
                parse_mode="Markdown",
                reply_markup=reply_markup,
            )

        # Tandai sudah diposting (anti-duplikasi)
        if product_id:
            mark_item_posted(product_id, deal_data.get("title", ""))

        await query.message.reply_text(
            f"✅ Produk *{deal_data.get('title', '')}* berhasil diposting ke channel!\n"
            f"({len(offers)} penawaran dari {len(offers)} marketplace)",
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error(f"❌ [Scan Handler Error] {e}")
        await query.message.reply_text(
            "❌ Terjadi kesalahan saat scan & posting.\n"
            "Pastikan bot sudah menjadi Admin di Channel target."
        )


# ---------------------------------------------------------------------------
# MESSAGE HANDLER: Link / teks tunggal
# ---------------------------------------------------------------------------
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if ADMIN_IDS and user_id not in ADMIN_IDS:
        return

    text = update.message.text.strip()
    urls = re.findall(r"https?://[^\s]+", text)

    if not urls:
        await update.message.reply_text("❌ Link tidak valid. Mohon kirimkan URL produk yang benar.")
        return

    target_url = urls[0]
    await update.message.reply_text("⏳ Mengambil data produk asli dari link...")

    try:
        product_data = fetch_single_product_manual(target_url)
        if not product_data:
            await update.message.reply_text("❌ Gagal mengekstrak data dari link tersebut.")
            return

        caption, buttons = format_caption_and_buttons(product_data)
        reply_markup     = InlineKeyboardMarkup(buttons)
        image_url        = product_data.get("image_url")

        if image_url:
            await context.bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=image_url,
                caption=caption,
                parse_mode="Markdown",
                reply_markup=reply_markup,
            )
        else:
            await context.bot.send_message(
                chat_id=CHANNEL_ID,
                text=caption,
                parse_mode="Markdown",
                reply_markup=reply_markup,
            )

        await update.message.reply_text("✅ Produk berhasil diposting ke Channel!")

    except Exception as e:
        logger.error(f"❌ [handle_text_message Error] {e}")
        await update.message.reply_text(
            "❌ Terjadi kesalahan saat memposting.\n"
            "Pastikan bot sudah dijadikan Admin di Channel Anda."
        )


# ---------------------------------------------------------------------------
# MESSAGE HANDLER: Video + caption
# ---------------------------------------------------------------------------
async def handle_video_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if ADMIN_IDS and user_id not in ADMIN_IDS:
        return

    message      = update.message
    video_file_id= message.video.file_id if message.video else None
    caption_text = message.caption or ""

    if not video_file_id:
        await message.reply_text("❌ Mohon sertakan video bersamaan dengan link produk di caption.")
        return

    await message.reply_text("⏳ Memproses video dan data produk Anda...")

    urls         = re.findall(r"https?://[^\s]+", caption_text)
    product_data = None

    if urls:
        product_data = fetch_single_product_manual(urls[0])

    # Fallback jika scraping gagal
    if not product_data:
        product_data = {
            "platform":      "tiktok",
            "badge":         "🎵 TikTok Shop",
            "title":         "Rekomendasi Video Produk Spesial",
            "description":   "Ulasan lengkap produk berkualitas tinggi ada pada video di atas. Amankan promonya sekarang juga!",
            "affiliate_url": urls[0] if urls else "https://tiktok.com",
            "original_url":  urls[0] if urls else "https://tiktok.com",
        }

    title   = product_data.get("title", "Produk Pilihan")
    aff_url = product_data.get("affiliate_url", "")
    badge   = product_data.get("badge", "🎵 TikTok Shop")
    desc    = product_data.get("description", "Ulasan produk lengkap ada di video. Amankan promo sekarang!")

    formatted_caption  = "🎬 *VIDEO REVIEW PRODUK*\n\n"
    formatted_caption += f"📦 *Judul:* {title}\n\n"
    formatted_caption += f"📝 *Deskripsi:*\n_{desc}_\n\n"
    formatted_caption += f"🔗 *Link Pembelian ({badge}):*\n{aff_url}"

    buttons      = [[InlineKeyboardButton("🛒 Cek Produk & Beli Disini", url=aff_url)]]
    reply_markup = InlineKeyboardMarkup(buttons)

    try:
        await context.bot.send_video(
            chat_id=CHANNEL_ID,
            video=video_file_id,
            caption=formatted_caption,
            parse_mode="Markdown",
            reply_markup=reply_markup,
        )
        await message.reply_text("✅ Video berhasil diposting ke Channel!")
    except Exception as e:
        logger.error(f"❌ [handle_video_message Error] {e}")
        await message.reply_text(
            "❌ Terjadi kesalahan saat mengirim video.\n"
            "Pastikan bot adalah Admin di Channel."
        )


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN belum diset. Silakan isi BOT_TOKEN di file .env atau environment variables.")
        return
    init_db()
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(
        filters.VIDEO & filters.ChatType.PRIVATE,
        handle_video_message,
    ))
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
        handle_text_message,
    ))

    logger.info("🤖 Bot Affiliate (Scrapling Edition) berjalan!")
    application.run_polling()


if __name__ == "__main__":
    main()
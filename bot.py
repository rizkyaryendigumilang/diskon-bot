# bot.py
import logging
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

from database import init_db, get_settings, is_item_posted, mark_item_posted
from scraper import fetch_single_product_manual
from config import BOT_TOKEN, CHANNEL_ID

# Konfigurasi Logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Admin bot (ID Telegram Kiky)
ADMIN_IDS = [8503838227]  

user_states = {}

def format_caption_and_buttons(deal_data):
    platform = deal_data.get("platform", "shopee").lower()
    
    if "tokopedia" in platform:
        badge = "🟢 Tokopedia"
        btn_label = "🛒 Cek Produk di Tokopedia"
    elif "blibli" in platform:
        badge = "🔵 Blibli"
        btn_label = "🛒 Cek Produk di Blibli"
    elif "lazada" in platform:
        badge = "🟠 Lazada"
        btn_label = "🛒 Cek Produk di Lazada"
    elif "tiktok" in platform:
        badge = "🎵 TikTok Shop"
        btn_label = "🛒 Beli di TikTok Shop"
    else:
        badge = "🧡 Shopee"
        btn_label = "🛒 Cek Produk & Beli Disini"

    offer = deal_data.get("offers", [deal_data])[0] if "offers" in deal_data else deal_data
    
    harga_promo = f"Rp {offer.get('price_promo', 0):,}".replace(',', '.')
    title = offer.get('title', 'Produk Pilihan')
    aff_url = offer.get('affiliate_url') or offer.get('original_url')
    
    desc = offer.get('description', 'Temukan produk berkualitas tinggi ini sekarang juga. Stok dan promo dapat berubah sewaktu-waktu!')

    caption = f"✨ *HIDDEN GEM & REKOMENDASI SPESIAL* ✨\n\n"
    caption += f"📦 *{title}*\n\n"
    
    if offer.get('price_promo', 0) > 0:
        caption += f"💰 *Harga Spesial:* *{harga_promo}* ({badge})\n\n"
    else:
        caption += f"💰 *Cek Harga Promo di Link* ({badge})\n\n"
        
    caption += f"📝 *Deskripsi Singkat:*\n_{desc}_\n\n"
    caption += f"🔗 *Link Pembelian:*\n{aff_url}"

    buttons = [[InlineKeyboardButton(btn_label, url=aff_url)]]
    return caption, buttons


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if ADMIN_IDS and user_id not in ADMIN_IDS:
        await update.message.reply_text(f"⛔ Maaf, Anda tidak memiliki akses ke bot ini. (ID Anda: {user_id})")
        return

    user_states[user_id] = "MENU_UTAMA"

    keyboard = [
        [InlineKeyboardButton("🔍 Scan Kategori & Diskon", callback_data="menu_scan")],
        [InlineKeyboardButton("🔗 Input Link Produk Manual", callback_data="menu_manual")],
        [InlineKeyboardButton("⚙️ Admin Access", callback_data="menu_admin")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = "🎛 *CONTROL PANEL ADMIN*\nPilih opsi utama manajemen bot:"
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    if ADMIN_IDS and user_id not in ADMIN_IDS:
        await query.answer("Akses ditolak.", show_alert=True)
        return

    await query.answer()
    data = query.data

    if data == "menu_scan":
        keyboard = [
            [InlineKeyboardButton("⚡ OTOMATIS FLASHSALE (All Marketplace)", callback_data="scan_flashsale")],
            [InlineKeyboardButton("🔥 Auto Diskon / Best Deals", callback_data="scan_auto")],
            [
                InlineKeyboardButton("⚡ Diskon Min. 50%", callback_data="scan_50"),
                InlineKeyboardButton("💎 Diskon Min. 70%", callback_data="scan_70")
            ],
            [
                InlineKeyboardButton("🎯 Diskon Min. 20%", callback_data="scan_20"),
                InlineKeyboardButton("🔥 Diskon Min. 30%", callback_data="scan_30")
            ],
            [InlineKeyboardButton("🔙 Kembali", callback_data="kembali_menu_utama")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = (
            "🎯 *LANGKAH 1: PILIH MODE SCANNING*\n"
            "Pilih 'FLASHSALE' untuk ambil semua produk flashsale otomatis, atau tentukan target diskon:"
        )
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=reply_markup)
        
    elif data == "menu_manual":
        user_states[user_id] = "INPUT_MANUAL"
        text = (
            "🔗 *MODE INPUT LINK TUNGGAL AKTIF*\n"
            "Silakan kirim link produk (Shopee/Tokopedia/Blibli/Lazada/TikTok) di chat ini."
        )
        await query.message.edit_text(text, parse_mode="Markdown")
        
    elif data == "menu_admin":
        await query.message.edit_text("⚙️ Menu Admin Access. (Pengaturan tambahan dapat dikonfigurasi di sini)")

    elif data == "kembali_menu_utama":
        keyboard = [
            [InlineKeyboardButton("🔍 Scan Kategori & Diskon", callback_data="menu_scan")],
            [InlineKeyboardButton("🔗 Input Link Produk Manual", callback_data="menu_manual")],
            [InlineKeyboardButton("⚙️ Admin Access", callback_data="menu_admin")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = "🎛 *CONTROL PANEL ADMIN*\nPilih opsi utama manajemen bot:"
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=reply_markup)

    elif data.startswith("scan_"):
        await query.message.reply_text(f"⏳ Fitur '{data}' sedang dijalankan... (Logika scraper otomatis akan ditambahkan di tahap berikutnya)")


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if ADMIN_IDS and user_id not in ADMIN_IDS:
        return

    text = update.message.text.strip()
    urls = re.findall(r'https?://[^\s]+', text)
    
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
        reply_markup = InlineKeyboardMarkup(buttons)

        # Memposting menggunakan CHANNEL_ID dari config.py
        await context.bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=product_data["image_url"],
            caption=caption,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        await update.message.reply_text("✅ Produk berhasil diposting ke Channel!")

    except Exception as e:
        logger.error(f"❌ Error di handle_text_message: {e}")
        await update.message.reply_text(f"❌ Terjadi kesalahan saat memposting. Pastikan bot sudah dijadikan Admin di Channel Anda.")


async def handle_video_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if ADMIN_IDS and user_id not in ADMIN_IDS:
        return

    message = update.message
    video_file_id = message.video.file_id if message.video else None
    caption_text = message.caption or ""

    if not video_file_id:
        await message.reply_text("❌ Mohon sertakan video bersamaan dengan link produk di caption.")
        return

    await message.reply_text("⏳ Memproses video dan data produk Anda...")

    urls = re.findall(r'https?://[^\s]+', caption_text)
    product_data = None
    if urls:
        product_data = fetch_single_product_manual(urls[0])

    if not product_data:
        product_data = {
            "platform": "tiktok",
            "badge": "🎵 TikTok Shop",
            "title": "Rekomendasi Video Produk Spesial",
            "affiliate_url": urls[0] if urls else "https://tiktok.com",
            "original_url": urls[0] if urls else "https://tiktok.com"
        }

    title = product_data.get("title", "Produk Pilihan")
    aff_url = product_data.get("affiliate_url", "")
    badge = product_data.get("badge", "🎵 TikTok Shop")
    desc = product_data.get("description", "Ulasan lengkap produk berkualitas tinggi ada pada video di atas. Amankan promonya sekarang juga!")

    formatted_caption = f"🎬 *VIDEO REVIEW PRODUK*\n\n"
    formatted_caption += f"📦 *Judul:* {title}\n\n"
    formatted_caption += f"📝 *Deskripsi:*\n_{desc}_\n\n"
    formatted_caption += f"🔗 *Link Pembelian ({badge}):*\n{aff_url}"

    buttons = [[InlineKeyboardButton("🛒 Cek Produk & Beli Disini", url=aff_url)]]
    reply_markup = InlineKeyboardMarkup(buttons)

    try:
        # Memposting menggunakan CHANNEL_ID dari config.py
        await context.bot.send_video(
            chat_id=CHANNEL_ID,
            video=video_file_id,
            caption=formatted_caption,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        await message.reply_text("✅ Video berhasil diposting ke Channel!")
    except Exception as e:
        logger.error(f"❌ Error di handle_video_message: {e}")
        await message.reply_text(f"❌ Terjadi kesalahan saat mengirim video. Pastikan bot adalah Admin di Channel.")


def main():
    init_db()
    # Menjalankan bot menggunakan BOT_TOKEN dari config.py
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.VIDEO & filters.ChatType.PRIVATE, handle_video_message))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_text_message))

    logger.info("🤖 Bot Berjalan Sempurna dengan API Fetcher dan Menu Aktif!")
    application.run_polling()

if __name__ == "__main__":
    main()
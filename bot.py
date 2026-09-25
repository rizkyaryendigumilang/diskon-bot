# bot.py
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
from database import init_db, get_settings, update_setting, add_posted_item
from scraper import fetch_multi_platform_deals

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- MIDDLEWARE CHECKER ADMIN ---
def is_admin(user_id: int) -> bool:
    return user_id == config.ADMIN_ID


# --- FORMATTER PESAN & TOMBOL TELEGRAM ---
def build_promo_message(deal_data: dict):
    """Membentuk format pesan HTML dan Inline Keyboard Button dari data perbandingan."""
    category = deal_data['category'].upper()
    title = deal_data['title']
    offers = deal_data['offers']

    caption = (
        f"🔥 <b>PERBANDINGAN HARGA PROMO BEST SELLER!</b> 🔥\n"
        f"🏆 <b>Kategori:</b> #{category}\n\n"
        f"📌 <b>{title}</b>\n\n"
        f"📊 <b>Cek Perbandingan Harga Hari Ini:</b>\n"
    )

    keyboard = []

    for offer in offers:
        platform = offer['platform'].title()
        badge = offer['badge']
        price_orig = f"Rp {offer['price_original']:,}".replace(",", ".")
        price_promo = f"Rp {offer['price_promo']:,}".replace(",", ".")
        disc = offer['discount_percent']
        sold = offer['sold_count']
        aff_url = offer['affiliate_url']

        is_cheap_label = " 🔥 <i>(Paling Murah!)</i>" if offer.get("is_cheapest") else ""

        caption += (
            f"\n{badge}:\n"
            f"💰 <s>{price_orig}</s> ➡️ <b>{price_promo}</b> (Diskon {disc}%){is_cheap_label}\n"
            f"⭐️ <i>Terjual: {sold}</i>\n"
        )

        # Buat tombol inline per platform
        btn_text = f"🛒 Beli di {platform} ({price_promo})"
        keyboard.append([InlineKeyboardButton(btn_text, url=aff_url)])

    caption += (
        f"\n---\n"
        f"⚡ <i>Stok & promo dapat berubah sewaktu-waktu. Klik tombol di bawah untuk membeli!</i>"
    )

    reply_markup = InlineKeyboardMarkup(keyboard)
    return caption, reply_markup


# --- JOB SCHEDULER: AUTO-BLAST KE CHANNEL ---
async def job_auto_blast(app: Application):
    """Job otomatis yang dipanggil oleh scheduler untuk mencari dan blast promo."""
    logging.info("⏰ Scheduler berjalan: Memeriksa promo baru...")
    deal_data = fetch_multi_platform_deals()

    if not deal_data or not deal_data.get("offers"):
        return

    caption, reply_markup = build_promo_message(deal_data)
    main_product_id = deal_data["main_product_id"]
    title = deal_data["title"]

    try:
        # Kirim Foto + Caption + Inline Buttons ke Channel
        await app.bot.send_photo(
            chat_id=config.CHANNEL_ID,
            photo=deal_data["image_url"],
            caption=caption,
            parse_mode="HTML",
            reply_markup=reply_markup
        )
        # Simpan ke DB agar tidak duplikat
        add_posted_item(main_product_id, title)
        logging.info(f"✅ [SUCCESS] Promo '{title}' berhasil diblast ke {config.CHANNEL_ID}")
    except Exception as e:
        logging.error(f"❌ [ERROR] Gagal blast ke channel: {e}")


# --- HANDLER COMMANDS ADMIN (CONTROL PANEL) ---

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(
        "👋 **Selamat datang di Control Panel Admin!**\n\n"
        "Gunakan perintah berikut untuk mengontrol Bot Mesin Pencari Promo:\n"
        "🔹 `/config` - Lihat setting aktif saat ini\n"
        "🔹 `/set_category <sport/skincare/hobby>` - Ubah kategori target\n"
        "🔹 `/set_discount <angka>` - Ubah diskon minimal (%)\n"
        "🔹 `/set_platform <all/shopee/tokopedia/tiktok>` - Pilih platform target\n"
        "🔹 `/scan_now` - Paksa bot langsung blast promo sekarang\n"
        "🔹 `/pause` / `/resume` - Matikan/Jalankan auto-blast",
        parse_mode="Markdown"
    )

async def cmd_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    s = get_settings()
    status_str = "⏸️ PAUSED (Nonaktif)" if s.get("is_paused") else "🟢 ACTIVE (Berjalan)"
    
    msg = (
        "⚙️ **STATUS & SETTING SEARCH ENGINE:**\n\n"
        f"📌 **Status Bot:** `{status_str}`\n"
        f"🏷️ **Kategori Target:** `{s.get('category').upper()}`\n"
        f"💥 **Diskon Minimal:** `{s.get('min_discount')}%`\n"
        f"🛒 **Platform Target:** `{s.get('platform').upper()}`\n\n"
        f"📢 **Channel Blast:** `{config.CHANNEL_ID}`"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def cmd_set_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Format: `/set_category <sport/skincare/hobby>`", parse_mode="Markdown")
        return
    cat = context.args[0].lower()
    update_setting("category", cat)
    await update.message.reply_text(f"✅ Kategori berhasil diubah ke: *{cat.upper()}*", parse_mode="Markdown")

async def cmd_set_discount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Format: `/set_discount <angka>` (Contoh: `/set_discount 30`)", parse_mode="Markdown")
        return
    disc = int(context.args[0])
    update_setting("min_discount", disc)
    await update.message.reply_text(f"✅ Diskon minimal berhasil diubah ke: *{disc}%*", parse_mode="Markdown")

async def cmd_set_platform(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args or context.args[0].lower() not in ['all', 'shopee', 'tokopedia', 'tiktok']:
        await update.message.reply_text("Format: `/set_platform <all/shopee/tokopedia/tiktok>`", parse_mode="Markdown")
        return
    plat = context.args[0].lower()
    update_setting("platform", plat)
    await update.message.reply_text(f"✅ Platform target berhasil diubah ke: *{plat.upper()}*", parse_mode="Markdown")

async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    update_setting("is_paused", 1)
    await update.message.reply_text("⏸️ Auto-blast di-pause.")

async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    update_setting("is_paused", 0)
    await update.message.reply_text("🟢 Auto-blast di-resume.")

async def cmd_scan_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text("🔍 Memulai proses pencarian & blast sekarang...")
    await job_auto_blast(context.application)


# --- MAIN RUNNER ---
# --- MAIN RUNNER ---

# Fungsi pemicu untuk menyalakan Scheduler setelah event loop aktif
async def post_init(app: Application):
    scheduler = AsyncIOScheduler()
    # Jalankan job_auto_blast tiap 30 menit
    scheduler.add_job(job_auto_blast, 'interval', minutes=30, args=[app])
    scheduler.start()
    logging.info("⏰ AsyncIOScheduler berhasil diaktifkan!")

def main():
    # 1. Inisialisasi Database
    init_db()

    # 2. Inisialisasi Telegram Application dengan post_init
    app = Application.builder().token(config.BOT_TOKEN).post_init(post_init).build()

    # 3. Register Command Handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("config", cmd_config))
    app.add_handler(CommandHandler("set_category", cmd_set_category))
    app.add_handler(CommandHandler("set_discount", cmd_set_discount))
    app.add_handler(CommandHandler("set_platform", cmd_set_platform))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("resume", cmd_resume))
    app.add_handler(CommandHandler("scan_now", cmd_scan_now))

    print("🤖 Bot Diskon Kiky Multi-Platform Aktif & Berjalan...")
    app.run_polling()

if __name__ == "__main__":
    main()
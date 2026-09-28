# bot.py
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

from scraper import fetch_multi_platform_deals, fetch_tiktok_manual, process_custom_url
from database import mark_item_posted, get_settings, update_interval_setting
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logging.basicConfig(level=logging.INFO)
CHANNEL_ID = "@infodiskonbykiky"
BOT_TOKEN = "TOKEN_BOT_ANDA_DI_SINI"  # Masukkan token bot Telegram Anda

# --- 1. FORMATTER PESAN (CAPTION & TOMBOL) ---
def format_caption_and_buttons(deal_data):
    """Menyusun teks dan tombol interaktif."""
    if deal_data.get("platform") == "tiktok":
        caption = f"🔥 *RACUN TIKTOK SHOP!* 🔥\n\n📌 {deal_data['title']}\n\n⚡ *Stok terbatas, cek keranjang kuning di bawah!*"
        buttons = [[InlineKeyboardButton("🛒 Beli di TikTok Shop", url=deal_data['original_url'])]]
        return caption, buttons

    caption = f"🔥 *PERBANDINGAN HARGA PROMO BEST SELLER!* 🔥\n"
    caption += f"🏆 Kategori: #{deal_data['category'].upper().replace(' ', '_')}\n\n"
    caption += f"📌 *{deal_data['title']}*\n\n📊 *Cek Perbandingan Harga Hari Ini:*\n\n"
    
    buttons = []
    for offer in deal_data['offers']:
        harga_coret = f"Rp {offer['price_original']:,}".replace(',', '.')
        harga_promo = f"Rp {offer['price_promo']:,}".replace(',', '.')
        
        caption += f"{offer['badge']}\n💰 ~{harga_coret}~ ➡️ *{harga_promo}* (Diskon {int(offer['discount_percent'])}%)\n"
        if offer.get('is_cheapest'):
            caption += f"🔥 *(Paling Murah!)*\n"
        caption += f"⭐ Terjual: {offer['sold_count']}\n\n"
        
        btn_text = f"🛒 Beli di {offer['platform'].title()} ({harga_promo})"
        buttons.append([InlineKeyboardButton(btn_text, url=offer['affiliate_url'])])

    caption += "---\n⚡ *Stok & promo dapat berubah sewaktu-waktu. Klik tombol di bawah untuk membeli!*"
    return caption, buttons

# --- 2. EKSEKUTOR POST KE CHANNEL ---
async def execute_post(bot, deal_data=None, draft_data=None):
    """Mengirimkan post final ke channel `@infodiskonbykiky`."""
    try:
        if draft_data:
            await bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=draft_data['photo'],
                caption=draft_data['caption'],
                parse_mode="Markdown",
                reply_markup=draft_data['reply_markup']
            )
            return True
            
        if deal_data:
            caption, buttons = format_caption_and_buttons(deal_data)
            reply_markup = InlineKeyboardMarkup(buttons)
            await bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=deal_data['image_url'],
                caption=caption,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
            if "main_product_id" in deal_data:
                mark_item_posted(deal_data['main_product_id'])
            return True
    except Exception as e:
        logging.error(f"❌ Gagal post ke channel: {e}")
    return False

# --- 3. AUTO-POST BACKGROUND WORKER ---
async def auto_post_job(context: ContextTypes.DEFAULT_TYPE):
    """Pekerjaan latar belakang otomatis sesuai interval."""
    settings = get_settings()
    if settings.get("is_paused") == 1 or settings.get("interval") == 0:
        return
        
    kategori = settings.get("category", "sport")
    deal_data = fetch_multi_platform_deals(kategori)
    if deal_data:
        await execute_post(context.bot, deal_data=deal_data)
        logging.info("🤖 Auto-post latar belakang berhasil dikirim ke channel.")

# --- 4. UI INTERAKTIF ADMIN ---
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menampilkan Control Panel utama."""
    keyboard = [
        [InlineKeyboardButton("🔍 Scan Kategori (Preview Post)", callback_data='menu_category')],
        [InlineKeyboardButton("🔗 Input Link Produk Manual", callback_data='menu_input_link')],
        [InlineKeyboardButton("⏱️ Atur Interval Auto-Post", callback_data='menu_interval_settings')],
        [InlineKeyboardButton("⚙️ Status Bot", callback_data='menu_config')]
    ]
    teks = "🎛️ *CONTROL PANEL ADMIN*\nPilih opsi manajemen post channel:"
    if update.message:
        await update.message.reply_text(teks, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menangani aksi klik tombol."""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == 'menu_category':
        keyboard = [
            [InlineKeyboardButton("💄 Skincare", callback_data='scan_skincare'),
             InlineKeyboardButton("👟 Sepatu Lari", callback_data='scan_sepatu')],
            [InlineKeyboardButton("🔙 Kembali", callback_data='menu_main')]
        ]
        await query.edit_message_text("🛒 *Pilih Kategori untuk di-Scan:*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data.startswith('scan_'):
        kategori = data.split('_')[1]
        await query.edit_message_text(f"⏳ Sedang memindai promo real-time untuk: *{kategori.upper()}* ...")
        
        deal_data = fetch_multi_platform_deals(kategori)
        if deal_data:
            caption, buttons_channel = format_caption_and_buttons(deal_data)
            reply_markup_channel = InlineKeyboardMarkup(buttons_channel)
            
            context.user_data['draft_post'] = {
                'photo': deal_data['image_url'],
                'caption': caption,
                'reply_markup': reply_markup_channel
            }
            
            admin_buttons = buttons_channel + [
                [InlineKeyboardButton("🚀 POST KE CHANNEL", callback_data='confirm_post')],
                [InlineKeyboardButton("❌ Batal / Hapus Draft", callback_data='cancel_post')]
            ]
            
            await query.message.reply_photo(
                photo=deal_data['image_url'],
                caption=caption + "\n\n⚠️ *PREVIEW DRAFT. Belum diposting ke channel.*",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(admin_buttons)
            )
        else:
            await query.message.reply_text("❌ Tidak ditemukan barang diskon yang sesuai saat ini.")

    # --- PENGATURAN INTERVAL WAKTU ---
    elif data == 'menu_interval_settings':
        settings = get_settings()
        curr_int = settings.get("interval", 30)
        keyboard = [
            [InlineKeyboardButton("⚡ 5 Menit", callback_data='set_int_5'),
             InlineKeyboardButton("🕒 15 Menit", callback_data='set_int_15')],
            [InlineKeyboardButton("🕒 30 Menit", callback_data='set_int_30'),
             InlineKeyboardButton("🛑 OFF (Manual Only)", callback_data='set_int_0')],
            [InlineKeyboardButton("🔙 Kembali", callback_data='menu_main')]
        ]
        await query.edit_message_text(
            f"⏱️ *PENGATURAN INTERVAL AUTO-POST*\nSaat ini interval aktif: *{curr_int if curr_int > 0 else 'OFF'} Menit*.\nPilih durasi baru:",
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )

    elif data.startswith('set_int_'):
        menit = int(data.replace('set_int_', ''))
        update_interval_setting(menit)
        
        # Update Job di Scheduler secara dinamis
        if context.application.job_queue:
            pass # (Menggunakan apscheduler langsung di bawah)
        
        global scheduler
        scheduler.remove_all_jobs()
        if menit > 0:
            scheduler.add_job(auto_post_job, 'interval', minutes=menit, id='auto_job', kwargs={'context': context.application})
            scheduler.start()
            await query.edit_message_text(f"✅ *Interval Auto-Post berhasil diubah ke {menit} Menit!*", parse_mode="Markdown")
        else:
            await query.edit_message_text("🛑 *Auto-Post DIMATIKAN.*\nBot sekarang dalam mode *Manual Only* (Hanya post jika Anda klik tombol/input link).", parse_mode="Markdown")

    elif data == 'confirm_post':
        draft = context.user_data.get('draft_post')
        if draft:
            sukses = await execute_post(context.bot, draft_data=draft)
            if sukses:
                await query.edit_message_caption(caption="✅ *PRODUK BERHASIL DIPOSTING KE CHANNEL!*", parse_mode="Markdown")
                context.user_data['draft_post'] = None
        else:
            await query.edit_message_caption("❌ Draft sudah kedaluwarsa atau kosong.")

    elif data == 'cancel_post':
        context.user_data['draft_post'] = None
        await query.message.delete()
        await query.message.reply_text("🗑️ Draft post dibatalkan.")

    elif data == 'menu_input_link':
        context.user_data['awaiting_link'] = True
        await query.edit_message_text("🔗 *MODE INPUT LINK AKTIF*\nSilakan kirim link produk (Shopee/Tokopedia/TikTok) di chat ini.", parse_mode="Markdown")

    elif data == 'menu_main':
        keyboard = [
            [InlineKeyboardButton("🔍 Scan Kategori (Preview Post)", callback_data='menu_category')],
            [InlineKeyboardButton("🔗 Input Link Produk Manual", callback_data='menu_input_link')],
            [InlineKeyboardButton("⏱️ Atur Interval Auto-Post", callback_data='menu_interval_settings')],
            [InlineKeyboardButton("⚙️ Status Bot", callback_data='menu_config')]
        ]
        await query.edit_message_text("🎛️ *CONTROL PANEL ADMIN*\nPilih opsi manajemen post channel:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == 'menu_config':
        st = get_settings()
        status_auto = f"{st.get('interval')} Menit" if st.get('interval') > 0 else "OFF (Manual Only)"
        await query.edit_message_text(f"⚙️ *STATUS BOT AKTIF*\n- Kategori Default: {st.get('category').upper()}\n- Interval Auto-Post: {status_auto}", parse_mode="Markdown")

# --- 5. HANDLER INPUT LINK MANUAL ---
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menerima link manual, membuat draft preview, dan memberi akses post ke channel."""
    if not context.user_data.get('awaiting_link'):
        return 
        
    url = update.message.text.strip()
    deal_data = None
    
    if "tiktok.com" in url:
        await update.message.reply_text("🎵 Memproses link TikTok...")
        deal_data = fetch_tiktok_manual(url)
    elif "shopee" in url or "tokopedia" in url:
        await update.message.reply_text("🔍 Memproses perbandingan harga marketplace...")
        deal_data = process_custom_url(url)
    else:
        await update.message.reply_text("❌ URL tidak valid. Masukkan link Shopee, Tokopedia, atau TikTok.")
        context.user_data['awaiting_link'] = False
        return

    if deal_data:
        caption, buttons_channel = format_caption_and_buttons(deal_data)
        
        context.user_data['draft_post'] = {
            'photo': deal_data['image_url'],
            'caption': caption,
            'reply_markup': InlineKeyboardMarkup(buttons_channel)
        }
        
        admin_buttons = buttons_channel + [
            [InlineKeyboardButton("🚀 POST KE CHANNEL", callback_data='confirm_post')],
            [InlineKeyboardButton("❌ Batal / Hapus Draft", callback_data='cancel_post')]
        ]
        
        await update.message.reply_photo(
            photo=deal_data['image_url'],
            caption=caption + "\n\n⚠️ *PREVIEW DRAFT. Belum diposting ke channel.*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(admin_buttons)
        )
    else:
        await update.message.reply_text("❌ Gagal mengekstrak data dari link tersebut.")
        
    context.user_data['awaiting_link'] = False

# Inisialisasi Global Scheduler
scheduler = AsyncIOScheduler()

# --- MAIN SETUP ---
if __name__ == '__main__':
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler('start', cmd_start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    # Ambil pengaturan awal interval dari database (Default 30 menit)
    initial_settings = get_settings()
    init_interval = initial_settings.get("interval", 30)
    
    if init_interval > 0:
        scheduler.add_job(auto_post_job, 'interval', minutes=init_interval, id='auto_job', kwargs={'context': application})
        scheduler.start()
        logging.info(f"⏰ Scheduler Auto-Post aktif ({init_interval} Menit)!")
    else:
        logging.info("🛑 Scheduler Auto-Post diatur dalam posisi OFF (Manual Only).")

    logging.info("🤖 Bot Berjalan Sempurna!")
    application.run_polling()
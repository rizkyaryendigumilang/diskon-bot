# config.py
import os

# Token Bot Telegram (dapat diset via environment variable BOT_TOKEN)
BOT_TOKEN = os.getenv("BOT_TOKEN", "8664285364:AAEA-jQ-Ba7dey9QnC0c_i6Si271Kt4v0OI")

# Username Channel Publik Anda
CHANNEL_ID = os.getenv("CHANNEL_ID", "@infodiskonbykiky")

# Konfigurasi ID Afiliasi Marketplace
AFFILIATE_IDS = {
    "shopee":    os.getenv("AFFILIATE_SHOPEE_ID", "11330881434"),
    "tokopedia": os.getenv("AFFILIATE_TOKOPEDIA_ID", "YOUR_TOKOPEDIA_AFF_ID"),
    "blibli":    os.getenv("AFFILIATE_BLIBLI_ID", "YOUR_BLIBLI_AFF_ID"),
    "lazada":    os.getenv("AFFILIATE_LAZADA_ID", "YOUR_LAZADA_AFF_ID"),
    "tiktok":    os.getenv("AFFILIATE_TIKTOK_ID", "YOUR_TIKTOK_AFF_ID"),
}

# Admin Telegram (Telegram User ID, dipisahkan koma jika lebih dari satu)
_admin_env = os.getenv("ADMIN_IDS", "8503838227")
ADMIN_IDS = [int(x.strip()) for x in _admin_env.split(",") if x.strip().isdigit()]
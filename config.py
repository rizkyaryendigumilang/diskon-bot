# config.py
import os

def _load_env_file(filepath=".env"):
    """Muat variabel lingkungan dari file .env lokal jika tersedia."""
    if os.path.isfile(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k and k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass

_load_env_file()

# Token Bot Telegram (diset via environment variable BOT_TOKEN atau .env)
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

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
# converter.py
import logging
import re
from config import AFFILIATE_IDS

def process_single_link(url: str) -> str:
    """
    Menangani jalur konversi afiliasi secara spesifik:
    - Jalur Shortlink / Link Share HP (digunakan langsung)
    - Jalur Link Panjang Web (dikonversi otomatis via ekstraksi ID produk)
    """
    if not url:
        return ""
    
    try:
        clean_url = url.strip()
        
        # JALUR 2: SHORTLINK / LINK SHARE HP
        if any(short_domain in clean_url for short_domain in ["s.shopee.co.id", "s.id/", "bit.ly/", "vt.tiktok.com"]):
            return clean_url

        # JALUR 1: LINK PANJANG WEB (Konversi otomatis ke format affiliate)
        if "shopee.co.id" in clean_url:
            shop_id = None
            item_id = None
            
            match_web = re.search(r"-i\.(\d+)\.(\d+)", clean_url)
            if match_web:
                shop_id = match_web.group(1)
                item_id = match_web.group(2)
            else:
                match_mob = re.search(r"/product/(\d+)/(\d+)", clean_url)
                if match_mob:
                    shop_id = match_mob.group(1)
                    item_id = match_mob.group(2)
            
            if shop_id and item_id:
                # Mengambil ID Affiliate Shopee dari config.py
                affiliate_tag = AFFILIATE_IDS.get("shopee", "")
                return f"https://shopee.co.id/product/{shop_id}/{item_id}?d_id={affiliate_tag}"
                
        return clean_url
        
    except Exception as e:
        logging.error(f"❌ [Converter Error]: {e}")
        return url

def process_multi_platform_links(links_dict: dict) -> dict:
    converted = {}
    for platform, url in links_dict.items():
        if url:
            converted[platform] = process_single_link(url)
        else:
            converted[platform] = None
    return converted
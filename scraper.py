# scraper.py
import requests
import urllib.parse
import random
import logging
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

from database import get_settings, is_item_posted
from converter import process_multi_platform_links

logging.basicConfig(level=logging.INFO)

# 1. Inisialisasi generator User-Agent Dinamis
ua = UserAgent(fallback="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

def get_headers():
    """Menghasilkan Header HTTP dengan User-Agent acak setiap kali dipanggil."""
    random_ua = ua.random
    return {
        "User-Agent": random_ua,
        "Accept": "application/json, text/html, */*",
        "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://shopee.co.id/",
        "Connection": "keep-alive"
    }

# --- MODUL SCRAPER SPESIFIK PER PLATFORM ---

def fetch_shopee_live(category: str, min_discount: int) -> dict:
    """Mengambil data LIVE dari internal API Shopee Search."""
    encoded_keyword = urllib.parse.quote(category)
    url = f"https://shopee.co.id/api/v4/search/search_items?keyword={encoded_keyword}&limit=10&newest=0"
    
    headers = get_headers()
    logging.info(f"🧡 [Shopee LIVE] Mencari '{category}' | UA: {headers['User-Agent'][:40]}...")

    try:
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        
        items = data.get("items", [])
        for item in items:
            basic = item.get("item_basic", {})
            discount = basic.get("raw_discount", 0)
            
            # Filter berdasarkan diskon minimal admin
            if discount >= min_discount:
                item_id = basic.get("itemid")
                shop_id = basic.get("shopid")
                product_id = f"shp_{item_id}"
                
                # Cek histori agar tidak duplikat
                if is_item_posted(product_id):
                    continue

                price = basic.get("price", 0) / 100000
                image_id = basic.get("image")
                
                return {
                    "platform": "shopee",
                    "product_id": product_id,
                    "badge": "🧡 Shopee Mall/Star (Live)",
                    "title": basic.get("name"),
                    "price_original": int(price / (1 - (discount / 100))),
                    "price_promo": int(price),
                    "discount_percent": discount,
                    "sold_count": f"{basic.get('historical_sold', 0)}+",
                    "image_url": f"https://down-id.img.susercontent.com/file/{image_id}",
                    "original_url": f"https://shopee.co.id/product/{shop_id}/{item_id}"
                }
    except Exception as e:
        logging.error(f"❌ [Shopee API Error] {e}")

    return None


def fetch_tokopedia_deal(category: str, min_discount: int) -> dict:
    """Mengambil item promo terbaik dari Tokopedia (Mock/Static structure untuk cloud)."""
    headers = get_headers()
    logging.info(f"🟢 [Tokopedia] Requesting data | UA: {headers['User-Agent'][:40]}...")

    product_id = f"tkp_{category}_102"
    
    if is_item_posted(product_id):
        return None

    return {
        "platform": "tokopedia",
        "product_id": product_id,
        "badge": "🟢 Official Store",
        "title": f"Sepatu Running Technical Pro - Special Edition ({category.title()})",
        "price_original": 350000,
        "price_promo": 169000,
        "discount_percent": 51,
        "sold_count": "5k+",
        "image_url": "https://picsum.photos/600/600?random=1",
        "original_url": f"https://tokopedia.com/official/{category}_102"
    }


def fetch_tiktok_deal(category: str, min_discount: int) -> dict:
    """Mengambil item promo terbaik dari TikTok Shop (Mock/Static structure untuk cloud)."""
    headers = get_headers()
    logging.info(f"🖤 [TikTok Shop] Requesting data | UA: {headers['User-Agent'][:40]}...")

    product_id = f"ttk_{category}_103"
    
    if is_item_posted(product_id):
        return None

    return {
        "platform": "tiktok",
        "product_id": product_id,
        "badge": "🖤 TikTok Mall",
        "title": f"Sepatu Running Technical Pro - Special Edition ({category.title()})",
        "price_original": 350000,
        "price_promo": 172000,
        "discount_percent": 50,
        "sold_count": "8k+",
        "image_url": "https://picsum.photos/600/600?random=1",
        "original_url": f"https://tiktok.com/shop/product/{category}_103"
    }


# --- ENGINE AGGREGATOR MULTI-PLATFORM ---

def fetch_multi_platform_deals() -> dict:
    """
    Membaca setting admin, mengambil data live dari e-commerce, 
    dan merakitnya ke dalam 1 pesan perbandingan harga.
    """
    settings = get_settings()
    if settings.get("is_paused") == 1:
        logging.info("⏸️ Bot sedang di-pause oleh Admin. Scanning dilewati.")
        return None

    category = settings.get("category", "sport")
    min_discount = settings.get("min_discount", 20)
    target_platform = settings.get("platform", "all")

    logging.info(f"🔎 Scanning Promo LIVE - Kategori: {category.upper()} | Diskon Min: {min_discount}% | Platform: {target_platform.upper()}")

    # 1. Fetch data (Mengeksekusi Shopee Live API)
    shopee_data = fetch_shopee_live(category, min_discount) if target_platform in ['all', 'shopee'] else None
    tokped_data = fetch_tokopedia_deal(category, min_discount) if target_platform in ['all', 'tokopedia'] else None
    tiktok_data = fetch_tiktok_deal(category, min_discount) if target_platform in ['all', 'tiktok'] else None

    # Jika tidak ada produk baru ditemukan
    if not shopee_data and not tokped_data and not tiktok_data:
        logging.info("ℹ️ Tidak ada produk promo baru yang ditemukan saat ini.")
        return None

    # 2. Ambil metadata utama (Memprioritaskan data real dari Shopee jika tersedia)
    main_item = shopee_data or tokped_data or tiktok_data

    # 3. Kumpulkan URL asli
    raw_links = {
        "shopee": shopee_data["original_url"] if shopee_data else None,
        "tokopedia": tokped_data["original_url"] if tokped_data else None,
        "tiktok": tiktok_data["original_url"] if tiktok_data else None
    }

    # 4. Otomatis ubah menjadi Link Afiliasi via converter.py
    affiliate_links = process_multi_platform_links(raw_links)

    # 5. Gabungkan hasil penawaran
    platforms_offer = []
    
    if shopee_data:
        shopee_data["affiliate_url"] = affiliate_links["shopee"]
        platforms_offer.append(shopee_data)
        
    if tokped_data:
        tokped_data["affiliate_url"] = affiliate_links["tokopedia"]
        platforms_offer.append(tokped_data)
        
    if tiktok_data:
        tiktok_data["affiliate_url"] = affiliate_links["tiktok"]
        platforms_offer.append(tiktok_data)

    # 6. Urutkan penawaran berdasarkan harga promo termurah
    platforms_offer.sort(key=lambda x: x["price_promo"])
    
    # Tandai platform dengan harga termurah
    if platforms_offer:
        platforms_offer[0]["is_cheapest"] = True

    # 7. Kembalikan data utuh
    return {
        "title": main_item["title"],
        "category": category,
        "image_url": main_item["image_url"],
        "main_product_id": main_item["product_id"],
        "offers": platforms_offer
    }
# scraper.py
import requests
import urllib.parse
import logging
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

from database import get_settings, is_item_posted
from converter import process_multi_platform_links

logging.basicConfig(level=logging.INFO)
ua = UserAgent(fallback="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

def get_headers():
    return {
        "User-Agent": ua.random,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    }

def fetch_shopee_live(keyword: str, min_discount: int = 20) -> dict:
    """Mencari barang diskon/Flash Sale di Shopee."""
    encoded_keyword = urllib.parse.quote(keyword)
    url = f"https://shopee.co.id/api/v4/search/search_items?keyword={encoded_keyword}&limit=15&newest=0&discount_only=1&order=sales"
    
    headers = get_headers()
    headers["Referer"] = "https://shopee.co.id/"

    try:
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        
        items = data.get("items", [])
        for item in items:
            basic = item.get("item_basic", {})
            discount = basic.get("raw_discount", 0)
            
            if discount >= min_discount:
                item_id = basic.get("itemid")
                shop_id = basic.get("shopid")
                product_id = f"shp_{item_id}"
                
                if is_item_posted(product_id):
                    continue

                price_promo = basic.get("price", 0) / 100000
                price_orig = price_promo / (1 - (discount / 100)) if discount > 0 else price_promo
                
                return {
                    "platform": "shopee",
                    "product_id": product_id,
                    "badge": "🧡 Shopee",
                    "title": basic.get("name"),
                    "price_original": int(price_orig),
                    "price_promo": int(price_promo),
                    "discount_percent": discount,
                    "sold_count": f"{basic.get('historical_sold', 0)}+",
                    "image_url": f"https://down-id.img.susercontent.com/file/{basic.get('image')}",
                    "original_url": f"https://shopee.co.id/product/{shop_id}/{item_id}"
                }
    except Exception as e:
        logging.error(f"❌ [Shopee Error] {e}")
    return None

def fetch_tokopedia_live(keyword: str) -> dict:
    """Mencari pembanding di Tokopedia menggunakan nama produk."""
    url = "https://gql.tokopedia.com/graphql/SearchProductQueryV4"
    headers = get_headers()
    headers.update({"Content-Type": "application/json", "Origin": "https://www.tokopedia.com", "Tkpd-UserId": "0"})

    payload = [{
        "operationName": "SearchProductQueryV4",
        "variables": {"params": f"q={urllib.parse.quote(keyword)}&source=search&ob=23&st=product&rt=4,5"},
        "query": "query SearchProductQueryV4($params: String!) { ace_search_product_v4(params: $params) { data { products { id name url imageUrl price price { original text } discountPercentage } } } }"
    }]

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        products = response.json()[0].get("data", {}).get("ace_search_product_v4", {}).get("data", {}).get("products", [])
        
        if products:
            item = products[0]
            raw_url = item.get("url", "")
            price_orig_str = item.get("price", {}).get("original", "0").replace("Rp", "").replace(".", "").strip()
            price_orig = int(price_orig_str) if price_orig_str.isdigit() else 0
            price_promo_str = item.get("price", {}).get("text", "0").replace("Rp", "").replace(".", "").strip()
            price_promo = int(price_promo_str) if price_promo_str.isdigit() else 0

            return {
                "platform": "tokopedia",
                "product_id": f"tkp_{item.get('id')}",
                "badge": "🟢 Tokopedia",
                "title": item.get("name"),
                "price_original": price_orig if price_orig > 0 else price_promo,
                "price_promo": price_promo,
                "discount_percent": item.get("discountPercentage", 0),
                "sold_count": "Cek Web",
                "image_url": item.get("imageUrl"),
                "original_url": raw_url.split("?")[0] if "?" in raw_url else raw_url
            }
    except Exception as e:
        logging.error(f"❌ [Tokopedia Error] {e}")
    return None

def fetch_tiktok_manual(url: str) -> dict:
    """Mengambil meta-data dari link TikTok Shop."""
    try:
        response = requests.get(url, headers=get_headers(), timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        title_meta = soup.find("meta", property="og:title")
        desc_meta = soup.find("meta", property="og:description")
        image_meta = soup.find("meta", property="og:image")
        
        title = title_meta["content"] if title_meta else "Produk TikTok Shop Viral"
        if desc_meta and "TikTok" in title:
            title = desc_meta["content"][:100] + "..."
            
        if not image_meta:
            return None
            
        return {
            "platform": "tiktok",
            "title": title,
            "image_url": image_meta["content"],
            "original_url": url
        }
    except Exception as e:
        logging.error(f"❌ [TikTok Scrape Error] {e}")
        return None

def fetch_multi_platform_deals(kategori: str) -> dict:
    """Otomatisasi pencarian komparatif Shopee vs Tokopedia."""
    settings = get_settings()
    min_discount = settings.get("min_discount", 20)

    shopee_data = fetch_shopee_live(kategori, min_discount)
    if not shopee_data:
        return None

    tokped_data = fetch_tokopedia_live(shopee_data["title"])

    raw_links = {
        "shopee": shopee_data["original_url"],
        "tokopedia": tokped_data["original_url"] if tokped_data else None
    }
    aff_links = process_multi_platform_links(raw_links)

    offers = []
    shopee_data["affiliate_url"] = aff_links["shopee"]
    offers.append(shopee_data)
        
    if tokped_data:
        tokped_data["affiliate_url"] = aff_links["tokopedia"]
        offers.append(tokped_data)

    offers.sort(key=lambda x: x["price_promo"])
    if offers:
        offers[0]["is_cheapest"] = True

    return {
        "platform": "shopee_tokopedia",
        "title": shopee_data["title"],
        "category": kategori,
        "image_url": shopee_data["image_url"],
        "main_product_id": shopee_data["product_id"],
        "offers": offers
    }

def process_custom_url(url: str) -> dict:
    """Mengekstrak judul dari URL manual (Shopee/Tokped) dan membandingkannya."""
    try:
        response = requests.get(url, headers=get_headers(), timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        title_tag = soup.find("title")
        if not title_tag:
            return None
            
        raw_title = title_tag.text.replace("Jual", "").replace("Shopee Indonesia", "").replace("Tokopedia", "").split("|")[0].strip()
        return fetch_multi_platform_deals(raw_title)
    except Exception as e:
        logging.error(f"❌ [Custom URL Error] {e}")
        return None
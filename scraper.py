# scraper.py
import requests
import urllib.parse
import logging
import re
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

from database import get_settings, is_item_posted
from converter import process_multi_platform_links, process_single_link

logging.basicConfig(level=logging.INFO)
ua = UserAgent(fallback="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

def get_headers():
    return {
        "User-Agent": ua.random,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en:q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }

# ==========================================
# 1. MODUL PENCARIAN & PEMBANDING REGULER (EXACT MATCH)
# ==========================================
def fetch_shopee_live(keyword: str, min_discount: int = 20) -> dict:
    encoded_keyword = urllib.parse.quote(keyword)
    url = f"https://shopee.co.id/api/v4/search/search_items?keyword={encoded_keyword}&limit=15&newest=0&discount_only=1&order=sales"
    
    headers = get_headers()
    headers["Referer"] = "https://shopee.co.id/"

    try:
        response = requests.get(url, headers=headers, timeout=12)
        if response.status_code != 200:
            return None
            
        data = response.json()
        items = data.get("items", [])
        for item in items:
            basic = item.get("item_basic", {})
            discount = basic.get("raw_discount", 0)
            
            if discount >= min_discount:
                item_id = basic.get("itemid")
                shop_id = basic.get("shopid")
                if not item_id or not shop_id:
                    continue
                    
                product_id = f"shp_{item_id}"
                if is_item_posted(product_id):
                    continue

                price_promo = basic.get("price", 0) / 100000
                price_orig = price_promo / (1 - (discount / 100)) if discount > 0 else price_promo * 1.3
                
                return {
                    "platform": "shopee",
                    "product_id": product_id,
                    "badge": "🧡 Shopee",
                    "title": basic.get("name"),
                    "price_original": int(price_orig),
                    "price_promo": int(price_promo),
                    "discount_percent": discount,
                    "sold_count": f"{basic.get('historical_sold', 50)}+",
                    "image_url": f"https://down-id.img.susercontent.com/file/{basic.get('image')}",
                    "original_url": f"https://shopee.co.id/product/{shop_id}/{item_id}"
                }
    except Exception as e:
        logging.error(f"❌ [Shopee Error] {e}")
    return None

def fetch_tokopedia_live(keyword: str) -> dict:
    url = "https://gql.tokopedia.com/graphql/SearchProductQueryV4"
    headers = get_headers()
    headers.update({"Content-Type": "application/json", "Origin": "https://www.tokopedia.com", "Tkpd-UserId": "0"})

    payload = [{
        "operationName": "SearchProductQueryV4",
        "variables": {"params": f"q={urllib.parse.quote(keyword)}&source=search&ob=23&st=product&rt=4,5"},
        "query": "query SearchProductQueryV4($params: String!) { ace_search_product_v4(params: $params) { data { products { id name url imageUrl price price { original text } discountPercentage } } } }"
    }]

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=12)
        if response.status_code != 200:
            return None
            
        products = response.json()[0].get("data", {}).get("ace_search_product_v4", {}).get("data", {}).get("products", [])
        if products:
            item = products[0]
            product_id = f"tkp_{item.get('id')}"
            if is_item_posted(product_id):
                return None
                
            raw_url = item.get("url", "")
            price_orig_str = item.get("price", {}).get("original", "0").replace("Rp", "").replace(".", "").strip()
            price_orig = int(price_orig_str) if price_orig_str.isdigit() else 0
            price_promo_str = item.get("price", {}).get("text", "0").replace("Rp", "").replace(".", "").strip()
            price_promo = int(price_promo_str) if price_promo_str.isdigit() else 0

            return {
                "platform": "tokopedia",
                "product_id": product_id,
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

def fetch_blibli_live(keyword: str) -> dict:
    try:
        url = f"https://www.blibli.com/backend/search/products?searchTerm={urllib.parse.quote(keyword)}&start=0&count=5"
        response = requests.get(url, headers=get_headers(), timeout=12)
        if response.status_code != 200 or "application/json" not in response.headers.get("Content-Type", ""):
            return None
            
        products = response.json().get("data", {}).get("products", [])
        if products:
            item = products[0]
            product_id = f"blb_{item.get('uniqueId')}"
            if is_item_posted(product_id):
                return None
                
            price_data = item.get("price", {})
            price_promo = price_data.get("price", 0)
            price_orig = price_data.get("strikeThroughPrice", price_promo)
            
            return {
                "platform": "blibli",
                "product_id": product_id,
                "badge": "🔵 Blibli",
                "title": item.get("name"),
                "price_original": int(price_orig),
                "price_promo": int(price_promo),
                "discount_percent": item.get("discount", 0),
                "sold_count": "Cek Web",
                "image_url": item.get("images", [""])[0],
                "original_url": "https://www.blibli.com" + item.get("url", "")
            }
    except Exception as e:
        logging.error(f"❌ [Blibli Error] {e}")
    return None

def fetch_lazada_live(keyword: str) -> dict:
    try:
        url = f"https://www.lazada.co.id/catalog/?q={urllib.parse.quote(keyword)}"
        response = requests.get(url, headers=get_headers(), timeout=12)
        if response.status_code != 200:
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        div_cards = soup.find_all("div", {"data-qa-locator": "product-item"}, limit=1)
        if div_cards:
            card = div_cards[0]
            title_tag = card.find("a", {"title": True})
            if not title_tag:
                return None
            title = title_tag["title"]
            product_id = f"lzd_{abs(hash(title))}"
            if is_item_posted(product_id):
                return None
                
            img_tag = card.find("img")
            link_tag = card.find("a")
            return {
                "platform": "lazada",
                "product_id": product_id,
                "badge": "🟠 Lazada",
                "title": title,
                "price_original": 100000,
                "price_promo": 50000,
                "discount_percent": 30,
                "sold_count": "Cek Web",
                "image_url": img_tag["src"] if img_tag and img_tag.get("src") else "",
                "original_url": "https:" + link_tag["href"] if link_tag and link_tag.get("href") else ""
            }
    except Exception as e:
        logging.error(f"❌ [Lazada Error] {e}")
    return None


# ==========================================
# 2. MODUL INDEPENDEN STABIL UNTUK FLASH SALE / ALL DEALS
# ==========================================
def fetch_flashsale_independent_pool() -> dict:
    try:
        url = "https://shopee.co.id/api/v4/search/search_items?keyword=flash%20sale&limit=15&newest=0&discount_only=1"
        headers = get_headers()
        headers["Referer"] = "https://shopee.co.id/"
        res = requests.get(url, headers=headers, timeout=10)
        
        if res.status_code == 200:
            items = res.json().get("items", [])
            for item in items:
                basic = item.get("item_basic", {})
                pid = f"shp_fs_{basic.get('itemid')}"
                if not is_item_posted(pid) and basic.get('itemid'):
                    p_promo = basic.get("price", 0) / 100000
                    disc = basic.get("raw_discount", 30)
                    return {
                        "platform": "shopee", "product_id": pid, "badge": "🧡 Shopee (Flash Sale)",
                        "title": basic.get("name"), "price_original": int(p_promo / (1 - (disc/100)) if disc > 0 else p_promo * 1.3),
                        "price_promo": int(p_promo), "discount_percent": disc,
                        "sold_count": f"{basic.get('historical_sold', 50)}+",
                        "image_url": f"https://down-id.img.susercontent.com/file/{basic.get('image')}",
                        "original_url": f"https://shopee.co.id/product/{basic.get('shopid')}/{basic.get('itemid')}",
                        "is_single_source": True
                    }
    except Exception as e:
        logging.error(f"⚠️ [FlashSale Shopee Error]: {e}")

    try:
        url = "https://www.blibli.com/backend/search/products?searchTerm=promo&start=0&count=5"
        res = requests.get(url, headers=get_headers(), timeout=10)
        if res.status_code == 200 and "application/json" in res.headers.get("Content-Type", ""):
            products = res.json().get("data", {}).get("products", [])
            for item in products:
                pid = f"blb_fs_{item.get('uniqueId')}"
                if not is_item_posted(pid):
                    p_data = item.get("price", {})
                    return {
                        "platform": "blibli", "product_id": pid, "badge": "🔵 Blibli (Flash Sale)",
                        "title": item.get("name"), "price_original": int(p_data.get("strikeThroughPrice", 0) or p_data.get("price", 0)),
                        "price_promo": int(p_data.get("price", 0)), "discount_percent": item.get("discount", 25),
                        "sold_count": "Cek Web", "image_url": item.get("images", [""])[0],
                        "original_url": "https://www.blibli.com" + item.get("url", ""), "is_single_source": True
                    }
    except Exception as e:
        logging.error(f"⚠️ [FlashSale Blibli Error]: {e}")

    return None


# ==========================================
# 3. PENGATUR UTAMA & MANUAL SCRAPER
# ==========================================
def fetch_multi_platform_deals(kategori: str, custom_min_discount: int = None, is_flashsale: bool = False) -> dict:
    settings = get_settings()
    min_discount = custom_min_discount if custom_min_discount is not None else settings.get("min_discount", 20)

    if is_flashsale:
        flash_item = fetch_flashsale_independent_pool()
        if not flash_item:
            return None
        
        flash_item["affiliate_url"] = process_single_link(flash_item["original_url"])
        return {
            "platform": "single_flashsale",
            "title": flash_item["title"],
            "category": "Flash Sale Global",
            "min_discount_used": 0,
            "image_url": flash_item["image_url"],
            "main_product_id": flash_item["product_id"],
            "offers": [flash_item]
        }

    shopee_data = fetch_shopee_live(kategori, min_discount)
    if not shopee_data:
        return None

    product_title = shopee_data["title"]

    tokped_data = fetch_tokopedia_live(product_title)
    blibli_data = fetch_blibli_live(product_title)
    lazada_data = fetch_lazada_live(product_title)

    raw_links = {
        "shopee": shopee_data["original_url"],
        "tokopedia": tokped_data["original_url"] if tokped_data else None,
        "blibli": blibli_data["original_url"] if blibli_data else None,
        "lazada": lazada_data["original_url"] if lazada_data else None
    }
    aff_links = process_multi_platform_links(raw_links)

    offers = []
    shopee_data["affiliate_url"] = aff_links["shopee"]
    offers.append(shopee_data)
        
    if tokped_data:
        tokped_data["affiliate_url"] = aff_links["tokopedia"]
        offers.append(tokped_data)
        
    if blibli_data:
        blibli_data["affiliate_url"] = aff_links["blibli"]
        offers.append(blibli_data)
        
    if lazada_data:
        lazada_data["affiliate_url"] = aff_links["lazada"]
        offers.append(lazada_data)

    offers.sort(key=lambda x: x["price_promo"])
    if offers:
        offers[0]["is_cheapest"] = True

    return {
        "platform": "multi_marketplace",
        "title": product_title,
        "category": kategori,
        "min_discount_used": min_discount,
        "image_url": shopee_data["image_url"],
        "main_product_id": shopee_data["product_id"],
        "offers": offers
    }

def fetch_multi_platform_deals_with_fallback(kategori: str, preferred_discount: int, is_flashsale: bool = False) -> dict:
    if is_flashsale:
        return fetch_multi_platform_deals(kategori, custom_min_discount=0, is_flashsale=True)

    thresholds = [preferred_discount, 50, 30, 15, 5]
    for threshold in thresholds:
        result = fetch_multi_platform_deals(kategori, custom_min_discount=threshold, is_flashsale=False)
        if result:
            if threshold < preferred_discount:
                result["is_fallback_deal"] = True
            return result
    return None

def fetch_single_product_manual(url: str) -> dict:
    """Mengambil data produk tunggal dari link manual dengan dukungan jalur link panjang & shortlink."""
    try:
        session = requests.Session()
        headers = get_headers()
        headers["Referer"] = "https://shopee.co.id/"
        
        response = session.get(url, headers=headers, timeout=15, allow_redirects=True)
        final_url = response.url

        if "tiktok.com" in final_url or "vt.tiktok.com" in final_url:
            return fetch_tiktok_manual(final_url)

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. Ambil Title yang akurat
        title = None
        title_meta = soup.find("meta", property="og:title")
        if title_meta and title_meta.get("content"):
            title = title_meta.get("content")
            
        if not title or "Shopee Indonesia" in title:
            title_tag = soup.find("title")
            if title_tag:
                title = title_tag.text.split("|")[0].strip()
                
        if not title or "Shopee Indonesia" in title:
            title = "✨ Rekomendasi Produk Pilihan Spesial"

        # 2. Ambil Foto Produk
        image_url = None
        if "s.shopee.co.id" not in url and "bit.ly" not in url and "s.id" not in url:
            image_meta = soup.find("meta", property="og:image")
            if image_meta and image_meta.get("content"):
                content = image_meta.get("content")
                if "http" in content and "logo" not in content and "banner" not in content:
                    image_url = content

        if not image_url or "svg" in image_url:
            image_url = "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=800&auto=format&fit=crop&q=80"

        if image_url.startswith("//"):
            image_url = "https:" + image_url

        # 3. Konversi Link Menjadi Affiliate melalui converter.py
        affiliate_url = process_single_link(url)

        # 4. Deteksi Platform & Badge
        platform_name = "shopee"
        badge = "🧡 Shopee"
        if "tokopedia" in final_url:
            platform_name, badge = "tokopedia", "🟢 Tokopedia"
        elif "blibli" in final_url:
            platform_name, badge = "blibli", "🔵 Blibli"
        elif "lazada" in final_url:
            platform_name, badge = "lazada", "🟠 Lazada"

        return {
            "platform": platform_name,
            "badge": badge,
            "title": title,
            "image_url": image_url,
            "original_url": final_url,
            "affiliate_url": affiliate_url
        }
    except Exception as e:
        logging.error(f"❌ [Single Manual Scrape Error] {e}")
        return None

def fetch_tiktok_manual(url: str) -> dict:
    try:
        response = requests.get(url, headers=get_headers(), timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        title_meta = soup.find("meta", property="og:title")
        image_meta = soup.find("meta", property="og:image")
        title = title_meta["content"] if title_meta and title_meta.get("content") else "Produk TikTok Shop"
        
        image_url = image_meta["content"] if image_meta and image_meta.get("content") else None
        if not image_url:
            image_url = "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=800&auto=format&fit=crop&q=80"
            
        return {
            "platform": "tiktok", "badge": "🎵 TikTok Shop", "title": title,
            "image_url": image_url, "original_url": url, "affiliate_url": process_single_link(url)
        }
    except Exception as e:
        logging.error(f"❌ [TikTok Scrape Error] {e}")
        return None
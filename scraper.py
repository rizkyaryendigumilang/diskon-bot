# scraper.py — Ditenagai oleh Scrapling
#
# Strategi Fetcher:
#   Fetcher         → API JSON (Shopee search, Tokopedia GQL, Blibli)  — cepat, stealth headers
#   StealthyFetcher → Shortlink un-shortening + halaman produk         — bypass antibot (butuh Camoufox)
#   DynamicFetcher  → Lazada (JS-rendered)                             — headless Playwright
#
# Catatan: StealthyFetcher & DynamicFetcher butuh Camoufox terinstall.
# Jalankan: python -m camoufox fetch
# Jika belum, bot otomatis fallback ke Fetcher biasa.
#
import logging
import re
import urllib.parse

from scrapling.fetchers import Fetcher

# Graceful import: StealthyFetcher & DynamicFetcher opsional (butuh Camoufox + Playwright)
try:
    from scrapling.fetchers import StealthyFetcher, DynamicFetcher
    STEALTH_AVAILABLE = True
except ImportError:
    STEALTH_AVAILABLE = False
    StealthyFetcher = None
    DynamicFetcher  = None

from database import get_settings, is_item_posted
from converter import process_multi_platform_links, process_single_link

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helper: buat instance Fetcher (ringan, tanpa browser)
# ---------------------------------------------------------------------------
def _fetcher() -> Fetcher:
    """Fetcher ringan dengan stealth headers bawaan Scrapling."""
    return Fetcher()

# ---------------------------------------------------------------------------
# 1. SHOPEE — Pencarian Live via API
# ---------------------------------------------------------------------------
def fetch_shopee_live(keyword: str, min_discount: int = 20) -> dict | None:
    """Cari produk Shopee lewat API resmi dengan filter diskon minimum."""
    encoded = urllib.parse.quote(keyword)
    url = (
        f"https://shopee.co.id/api/v4/search/search_items"
        f"?keyword={encoded}&limit=15&newest=0&discount_only=1&order=sales"
    )
    try:
        fetcher = _fetcher()
        response = fetcher.get(
            url,
            headers={
                "Referer": "https://shopee.co.id/",
                "Accept": "application/json",
            },
            timeout=15,
        )
        if not response or response.status != 200:
            return None

        data = response.json()
        items = data.get("items", [])

        for item in items:
            basic = item.get("item_basic", {})
            discount = basic.get("raw_discount", 0)
            if discount < min_discount:
                continue

            item_id = basic.get("itemid")
            shop_id = basic.get("shopid")
            if not item_id or not shop_id:
                continue

            product_id = f"shp_{item_id}"
            if is_item_posted(product_id):
                continue

            price_promo = basic.get("price", 0) / 100000
            price_orig  = (
                price_promo / (1 - discount / 100) if discount > 0
                else price_promo * 1.3
            )
            return {
                "platform":        "shopee",
                "product_id":      product_id,
                "badge":           "🧡 Shopee",
                "title":           basic.get("name"),
                "price_original":  int(price_orig),
                "price_promo":     int(price_promo),
                "discount_percent": discount,
                "sold_count":      f"{basic.get('historical_sold', 50)}+",
                "image_url":       f"https://down-id.img.susercontent.com/file/{basic.get('image')}",
                "original_url":    f"https://shopee.co.id/product/{shop_id}/{item_id}",
            }

    except Exception as e:
        logger.error(f"❌ [Shopee Search Error] {e}")
    return None


# ---------------------------------------------------------------------------
# 2. TOKOPEDIA — GraphQL Live
# ---------------------------------------------------------------------------
def fetch_tokopedia_live(keyword: str) -> dict | None:
    """Cari produk Tokopedia via GraphQL."""
    url = "https://gql.tokopedia.com/graphql/SearchProductQueryV4"
    payload = [{
        "operationName": "SearchProductQueryV4",
        "variables": {
            "params": f"q={urllib.parse.quote(keyword)}&source=search&ob=23&st=product&rt=4,5"
        },
        "query": (
            "query SearchProductQueryV4($params: String!) {"
            "  ace_search_product_v4(params: $params) {"
            "    data { products { id name url imageUrl"
            "      price { original text } discountPercentage } } } }"
        ),
    }]
    try:
        fetcher = _fetcher()
        response = fetcher.post(
            url,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Origin": "https://www.tokopedia.com",
                "Tkpd-UserId": "0",
            },
            timeout=15,
        )
        if not response or response.status != 200:
            return None

        json_data = response.json()
        if not json_data or not isinstance(json_data, list) or not json_data[0]:
            return None

        first_data = json_data[0].get("data")
        if not first_data or not isinstance(first_data, dict):
            return None

        products = (
            first_data
            .get("ace_search_product_v4", {})
            .get("data", {})
            .get("products", [])
        )
        if not products:
            return None

        item = products[0]
        product_id = f"tkp_{item.get('id')}"
        if is_item_posted(product_id):
            return None

        raw_url        = item.get("url", "")
        price_obj      = item.get("price", {})
        price_orig_str = re.sub(r"[^\d]", "", price_obj.get("original", "0"))
        price_promo_str= re.sub(r"[^\d]", "", price_obj.get("text",     "0"))
        price_orig     = int(price_orig_str)  if price_orig_str  else 0
        price_promo    = int(price_promo_str) if price_promo_str else 0

        return {
            "platform":         "tokopedia",
            "product_id":       product_id,
            "badge":            "🟢 Tokopedia",
            "title":            item.get("name"),
            "price_original":   price_orig if price_orig > 0 else price_promo,
            "price_promo":      price_promo,
            "discount_percent": item.get("discountPercentage", 0),
            "sold_count":       "Cek Web",
            "image_url":        item.get("imageUrl"),
            "original_url":     raw_url.split("?")[0] if "?" in raw_url else raw_url,
        }

    except Exception as e:
        logger.error(f"❌ [Tokopedia Error] {e}")
    return None


# ---------------------------------------------------------------------------
# 3. BLIBLI — JSON API
# ---------------------------------------------------------------------------
def fetch_blibli_live(keyword: str) -> dict | None:
    """Cari produk Blibli via backend JSON API."""
    url = f"https://www.blibli.com/backend/search/products?searchTerm={urllib.parse.quote(keyword)}&start=0&count=5"
    try:
        fetcher = _fetcher()
        response = fetcher.get(url, timeout=15)
        if not response or response.status != 200:
            return None

        products = response.json().get("data", {}).get("products", [])
        if not products:
            return None

        item       = products[0]
        item_id    = item.get("formattedId") or item.get("sku") or item.get("id") or item.get("uniqueId")
        if not item_id:
            return None
        product_id = f"blb_{item_id}"
        if is_item_posted(product_id):
            return None

        price_data  = item.get("price", {})
        price_promo = int(price_data.get("salePrice") or price_data.get("minPrice") or price_data.get("price") or 0)
        price_orig  = int(price_data.get("listPrice") or price_data.get("strikeThroughPrice") or price_promo)

        return {
            "platform":         "blibli",
            "product_id":       product_id,
            "badge":            "🔵 Blibli",
            "title":            item.get("name"),
            "price_original":   price_orig,
            "price_promo":      price_promo,
            "discount_percent": int(price_data.get("discount", 0)),
            "sold_count":       "Cek Web",
            "image_url":        (item.get("images") or [""])[0],
            "original_url":     "https://www.blibli.com" + item.get("url", ""),
        }

    except Exception as e:
        logger.error(f"❌ [Blibli Error] {e}")
    return None


# ---------------------------------------------------------------------------
# 4. LAZADA — DynamicFetcher (JS-rendered)
# ---------------------------------------------------------------------------
def fetch_lazada_live(keyword: str) -> dict | None:
    """
    Cari produk Lazada menggunakan DynamicFetcher (headless Playwright).
    Karena halaman Lazada butuh JavaScript untuk merender produk.
    """
    url = f"https://www.lazada.co.id/catalog/?q={urllib.parse.quote(keyword)}"
    try:
        # StealthyFetcher (Patchright Chromium) untuk JS-rendered. Fallback ke DynamicFetcher / Fetcher jika belum ada.
        if STEALTH_AVAILABLE and StealthyFetcher is not None:
            page = StealthyFetcher().fetch(url, headless=True, timeout=30000, wait_selector='[data-qa-locator="product-item"]')
        elif STEALTH_AVAILABLE and DynamicFetcher is not None:
            page = DynamicFetcher().fetch(url, timeout=30000, wait_selector='[data-qa-locator="product-item"]')
        else:
            logger.warning("⚠️ Browser fetcher tidak tersedia, pakai Fetcher biasa untuk Lazada")
            page = _fetcher().get(url, timeout=20)
        if not page:
            return None

        cards = page.css('[data-qa-locator="product-item"]', auto_save=True)
        if not cards:
            return None

        card = cards[0]
        title_el = card.css('a[title]')
        if not title_el:
            return None

        title      = title_el[0].attrib.get("title", "Produk Lazada")
        product_id = f"lzd_{abs(hash(title))}"
        if is_item_posted(product_id):
            return None

        img_el  = card.css("img")
        link_el = card.css("a")
        img_src = img_el[0].attrib.get("src", "") if img_el else ""
        link_href = link_el[0].attrib.get("href", "") if link_el else ""

        # Coba ekstrak harga dari teks
        price_els = card.css('[class*="price"]')
        price_promo = 0
        price_orig  = 0
        if price_els:
            prices_text = [re.sub(r"[^\d]", "", el.text) for el in price_els if el.text]
            prices_int  = [int(p) for p in prices_text if p]
            if prices_int:
                price_promo = min(prices_int)
                price_orig  = max(prices_int)

        return {
            "platform":         "lazada",
            "product_id":       product_id,
            "badge":            "🟠 Lazada",
            "title":            title,
            "price_original":   price_orig  if price_orig  > 0 else price_promo,
            "price_promo":      price_promo if price_promo > 0 else 50000,
            "discount_percent": 0,
            "sold_count":       "Cek Web",
            "image_url":        ("https:" + img_src) if img_src.startswith("//") else img_src,
            "original_url":     ("https:" + link_href) if link_href.startswith("//") else link_href,
        }

    except Exception as e:
        logger.error(f"❌ [Lazada Error] {e}")
    return None


# ---------------------------------------------------------------------------
# 5. SHOPEE FLASH SALE — Pool independen
# ---------------------------------------------------------------------------
def fetch_flashsale_independent_pool() -> dict | None:
    """Ambil satu produk flash sale aktif dari Shopee atau Blibli."""
    # -- Shopee flash sale
    try:
        url = (
            "https://shopee.co.id/api/v4/search/search_items"
            "?keyword=flash%20sale&limit=15&newest=0&discount_only=1"
        )
        fetcher = _fetcher()
        res = fetcher.get(url, headers={"Referer": "https://shopee.co.id/"}, timeout=12)
        if res and res.status == 200:
            for item in res.json().get("items", []):
                basic = item.get("item_basic", {})
                pid   = f"shp_fs_{basic.get('itemid')}"
                if basic.get("itemid") and not is_item_posted(pid):
                    p_promo = basic.get("price", 0) / 100000
                    disc    = basic.get("raw_discount", 30)
                    return {
                        "platform":         "shopee",
                        "product_id":       pid,
                        "badge":            "🧡 Shopee (Flash Sale)",
                        "title":            basic.get("name"),
                        "price_original":   int(p_promo / (1 - disc / 100) if disc > 0 else p_promo * 1.3),
                        "price_promo":      int(p_promo),
                        "discount_percent": disc,
                        "sold_count":       f"{basic.get('historical_sold', 50)}+",
                        "image_url":        f"https://down-id.img.susercontent.com/file/{basic.get('image')}",
                        "original_url":     f"https://shopee.co.id/product/{basic.get('shopid')}/{basic.get('itemid')}",
                        "is_single_source": True,
                    }
    except Exception as e:
        logger.error(f"⚠️ [FlashSale Shopee Error] {e}")

    # -- Blibli fallback
    try:
        url = "https://www.blibli.com/backend/search/products?searchTerm=promo&start=0&count=5"
        res = _fetcher().get(url, timeout=12)
        if res and res.status == 200:
            for item in res.json().get("data", {}).get("products", []):
                item_id = item.get("formattedId") or item.get("sku") or item.get("id") or item.get("uniqueId")
                if not item_id:
                    continue
                pid = f"blb_fs_{item_id}"
                if not is_item_posted(pid):
                    p = item.get("price", {})
                    p_promo = int(p.get("salePrice") or p.get("minPrice") or p.get("price") or 0)
                    p_orig = int(p.get("listPrice") or p.get("strikeThroughPrice") or p_promo)
                    return {
                        "platform":         "blibli",
                        "product_id":       pid,
                        "badge":            "🔵 Blibli (Flash Sale)",
                        "title":            item.get("name"),
                        "price_original":   p_orig,
                        "price_promo":      p_promo,
                        "discount_percent": int(p.get("discount", 25)),
                        "sold_count":       "Cek Web",
                        "image_url":        (item.get("images") or [""])[0],
                        "original_url":     "https://www.blibli.com" + item.get("url", ""),
                        "is_single_source": True,
                    }
    except Exception as e:
        logger.error(f"⚠️ [FlashSale Blibli Error] {e}")

    return None


# ---------------------------------------------------------------------------
# 6. ORCHESTRATOR — Multi-marketplace + Flash Sale
# ---------------------------------------------------------------------------
def fetch_multi_platform_deals(
    kategori: str,
    custom_min_discount: int = None,
    is_flashsale: bool = False,
) -> dict | None:
    """Koordinator utama: ambil produk dari semua marketplace dan gabungkan."""
    settings    = get_settings()
    min_discount = custom_min_discount if custom_min_discount is not None else settings.get("min_discount", 20)

    if is_flashsale:
        flash_item = fetch_flashsale_independent_pool()
        if not flash_item:
            return None
        flash_item["affiliate_url"] = process_single_link(flash_item["original_url"])
        return {
            "platform":         "single_flashsale",
            "title":            flash_item["title"],
            "category":         "Flash Sale Global",
            "min_discount_used": 0,
            "image_url":        flash_item["image_url"],
            "main_product_id":  flash_item["product_id"],
            "offers":           [flash_item],
        }

    # Coba Shopee terlebih dahulu sebagai anchor utama
    shopee_data = fetch_shopee_live(kategori, min_discount)
    main_deal = shopee_data
    anchor_name = "shopee"

    # Jika Shopee tidak return hasil / rate-limited, gunakan Blibli sebagai anchor
    if not main_deal:
        logger.info(f"Shopee live tidak menemukan deals untuk '{kategori}', beralih ke Blibli...")
        blibli_deal = fetch_blibli_live(kategori)
        if blibli_deal:
            main_deal = blibli_deal
            anchor_name = "blibli"

    # Jika tetap belum dapat, coba pool flashsale sebagai fallback
    if not main_deal:
        logger.info("Mencari dari pool flashsale sebagai fallback...")
        flash_item = fetch_flashsale_independent_pool()
        if flash_item:
            flash_item["affiliate_url"] = process_single_link(flash_item["original_url"])
            return {
                "platform":         "single_flashsale",
                "title":            flash_item["title"],
                "category":         f"{kategori} (Flash Sale)",
                "min_discount_used": 0,
                "image_url":        flash_item["image_url"],
                "main_product_id":  flash_item["product_id"],
                "offers":           [flash_item],
            }
        return None

    product_title = main_deal["title"]

    # Cari produk serupa di marketplace lain untuk pembanding
    tokped_data = fetch_tokopedia_live(product_title)
    blibli_data = main_deal if anchor_name == "blibli" else fetch_blibli_live(product_title)
    lazada_data = fetch_lazada_live(product_title)
    shopee_deal = main_deal if anchor_name == "shopee" else fetch_shopee_live(product_title, min_discount=0)

    # Konversi semua URL ke affiliate link
    raw_links = {
        "shopee":    shopee_deal["original_url"] if shopee_deal else None,
        "tokopedia": tokped_data["original_url"] if tokped_data else None,
        "blibli":    blibli_data["original_url"] if blibli_data else None,
        "lazada":    lazada_data["original_url"] if lazada_data else None,
    }
    aff_links = process_multi_platform_links(raw_links)

    offers = []
    if shopee_deal:
        shopee_deal["affiliate_url"] = aff_links["shopee"]
        offers.append(shopee_deal)

    if blibli_data and blibli_data not in offers:
        blibli_data["affiliate_url"] = aff_links["blibli"]
        offers.append(blibli_data)

    if tokped_data:
        tokped_data["affiliate_url"] = aff_links["tokopedia"]
        offers.append(tokped_data)

    if lazada_data:
        lazada_data["affiliate_url"] = aff_links["lazada"]
        offers.append(lazada_data)

    offers.sort(key=lambda x: x.get("price_promo", 0))
    if offers:
        offers[0]["is_cheapest"] = True

    return {
        "platform":         "multi_marketplace" if len(offers) > 1 else main_deal.get("platform", "marketplace"),
        "title":            product_title,
        "category":         kategori,
        "min_discount_used": min_discount,
        "image_url":        main_deal.get("image_url", ""),
        "main_product_id":  main_deal.get("product_id", ""),
        "offers":           offers,
    }


def fetch_multi_platform_deals_with_fallback(
    kategori: str,
    preferred_discount: int,
    is_flashsale: bool = False,
) -> dict | None:
    """Coba fetch dengan threshold diskon bertahap jika threshold utama tidak menemukan produk."""
    if is_flashsale:
        return fetch_multi_platform_deals(kategori, custom_min_discount=0, is_flashsale=True)

    for threshold in [preferred_discount, 50, 30, 15, 5]:
        result = fetch_multi_platform_deals(kategori, custom_min_discount=threshold)
        if result:
            if threshold < preferred_discount:
                result["is_fallback_deal"] = True
            return result
    return None


# ---------------------------------------------------------------------------
# 7. MANUAL SCRAPER — Input link tunggal (StealthyFetcher)
# ---------------------------------------------------------------------------
def _extract_shopee_ids_from_url(url: str) -> tuple[str | None, str | None]:
    """Ekstrak shop_id dan item_id dari URL Shopee (format panjang atau /product/)."""
    m = re.search(r"-i\.(\d+)\.(\d+)", url)
    if m:
        return m.group(1), m.group(2)
    m = re.search(r"/product/(\d+)/(\d+)", url)
    if m:
        return m.group(1), m.group(2)
    return None, None


def _fetch_shopee_product_api(shop_id: str, item_id: str) -> dict | None:
    """Tembak API internal Shopee untuk mendapatkan data produk yang 100% akurat."""
    api_url = (
        f"https://shopee.co.id/api/v4/item/get"
        f"?itemid={item_id}&shopid={shop_id}"
    )
    try:
        response = _fetcher().get(
            api_url,
            headers={"Referer": f"https://shopee.co.id/product/{shop_id}/{item_id}"},
            timeout=15,
        )
        if not response or response.status != 200:
            return None

        item = response.json().get("data", {}) or {}
        if not item:
            return None

        price_promo = item.get("price", 0) / 100000
        discount    = item.get("raw_discount", 0)
        price_orig  = (
            price_promo / (1 - discount / 100) if discount > 0
            else item.get("price_before_discount", price_promo * 1.2) / 100000
        )

        # Gambar: ambil dari list images (lebih presisi dari og:image)
        images     = item.get("images", [])
        image_url  = (
            f"https://down-id.img.susercontent.com/file/{images[0]}"
            if images else None
        )

        description_raw = item.get("description", "")
        description     = description_raw[:300].strip() if description_raw else ""

        return {
            "title":            item.get("name"),
            "image_url":        image_url,
            "price_promo":      int(price_promo),
            "price_original":   int(price_orig),
            "discount_percent": discount,
            "description":      description,
            "sold_count":       f"{item.get('historical_sold', 0)}+",
        }

    except Exception as e:
        logger.error(f"❌ [Shopee API Internal Error] {e}")
    return None


def fetch_single_product_manual(url: str) -> dict | None:
    """
    Ambil data produk dari link tunggal yang dikirim user.
    Jalur ganda:
      - Shortlink (s.shopee.co.id, bit.ly, s.id)  → StealthyFetcher un-shortening
      - Link panjang web                            → ekstrak ID → API internal
      - TikTok                                      → StealthyFetcher parse og: tags
    """
    if not url:
        return None
    try:
        # ── Langkah 1: Resolve URL (ikuti semua redirect termasuk shortlink) ──
        is_shortlink = any(d in url for d in ["s.shopee.co.id", "s.id/", "bit.ly/", "vt.tiktok.com"])

        if is_shortlink:
            if STEALTH_AVAILABLE and StealthyFetcher is not None:
                # StealthyFetcher (Camoufox) → bypass bot-check + ikuti redirect
                stealthy_res = StealthyFetcher().fetch(
                    url, headless=True, network_idle=True, timeout=25000,
                )
                final_url = stealthy_res.url if stealthy_res else url
            else:
                # Fallback: Fetcher biasa dengan allow_redirects
                logger.warning("⚠️ StealthyFetcher tidak tersedia, pakai Fetcher biasa untuk resolve shortlink")
                plain_res = _fetcher().get(url, timeout=15)
                final_url = plain_res.url if plain_res else url
        else:
            # Untuk link panjang, Fetcher biasa sudah cukup
            plain_res = _fetcher().get(url, timeout=15)
            final_url = plain_res.url if plain_res else url

        logger.info(f"🔗 Final URL setelah resolve: {final_url}")

        # ── Langkah 2: Routing berdasarkan platform ──
        if "tiktok.com" in final_url:
            return _fetch_tiktok_manual(final_url)

        # ── Langkah 3: Shopee — dual path ──
        if "shopee.co.id" in final_url:
            shop_id, item_id = _extract_shopee_ids_from_url(final_url)

            if shop_id and item_id:
                api_data = _fetch_shopee_product_api(shop_id, item_id)
                if api_data and api_data.get("title"):
                    aff_url = process_single_link(
                        f"https://shopee.co.id/product/{shop_id}/{item_id}"
                    )
                    return {
                        "platform":         "shopee",
                        "badge":            "🧡 Shopee",
                        "title":            api_data["title"],
                        "image_url":        api_data["image_url"],
                        "price_promo":      api_data["price_promo"],
                        "price_original":   api_data["price_original"],
                        "discount_percent": api_data["discount_percent"],
                        "description":      api_data["description"],
                        "sold_count":       api_data["sold_count"],
                        "original_url":     final_url,
                        "affiliate_url":    aff_url,
                    }

        # ── Langkah 4: Tokopedia / Blibli / Lazada / Shopee web — parse metadata ──
        fallback_res = None
        if STEALTH_AVAILABLE and StealthyFetcher is not None:
            try:
                fallback_res = StealthyFetcher().fetch(final_url, headless=True, timeout=25000)
            except Exception as e:
                logger.warning(f"⚠️ Stealthy fetch gagal pada {final_url}: {e}")

        if not fallback_res:
            fallback_res = _fetcher().get(final_url, timeout=15)

        if not fallback_res:
            return None

        title   = _og(fallback_res, "og:title") or _title_tag(fallback_res) or "✨ Rekomendasi Produk Pilihan"
        img_url = _og(fallback_res, "og:image") or None
        desc    = _og(fallback_res, "og:description") or ""

        # Bersihkan judul generik
        for suffix in [" | Tokopedia", " - Blibli.com", " - Lazada", " | Shopee Indonesia", " | Blibli"]:
            title = title.replace(suffix, "").strip()

        if img_url and img_url.startswith("//"):
            img_url = "https:" + img_url

        # Coba ekstrak harga dan diskon dari deskripsi atau teks
        price_promo = 0
        discount_percent = 0
        price_match = re.search(r"Rp\s*([\d\.,]+)", desc or title)
        if price_match:
            digits = re.sub(r"[^\d]", "", price_match.group(1))
            if digits:
                price_promo = int(digits)

        disc_match = re.search(r"Diskon\s*(\d+)%", desc or title, re.IGNORECASE)
        if disc_match:
            discount_percent = int(disc_match.group(1))

        # Fallback image jika img_url kosong atau logo generic
        if not img_url or "homepage_fb_rebranding" in img_url or "logo" in img_url.lower():
            img_tags = fallback_res.css("img[src*='catalog'], img[src*='product'], img[src*='images']")
            if img_tags:
                src = img_tags[0].attrib.get("src", "")
                if src:
                    img_url = ("https:" + src) if src.startswith("//") else src

        if not img_url:
            img_url = "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=800&auto=format&fit=crop&q=80"

        # Tentukan platform dari final_url
        if "tokopedia" in final_url:
            platform, badge = "tokopedia", "🟢 Tokopedia"
        elif "blibli" in final_url:
            platform, badge = "blibli", "🔵 Blibli"
        elif "lazada" in final_url:
            platform, badge = "lazada", "🟠 Lazada"
        elif "tiktok" in final_url:
            platform, badge = "tiktok", "🎵 TikTok Shop"
        else:
            platform, badge = "shopee", "🧡 Shopee"

        return {
            "platform":         platform,
            "badge":            badge,
            "title":            title,
            "price_promo":      price_promo,
            "price_original":   int(price_promo * 1.3) if price_promo > 0 else 0,
            "discount_percent": discount_percent,
            "image_url":        img_url,
            "description":      desc[:300] if desc else "Produk rekomendasi pilihan terbaik.",
            "original_url":     final_url,
            "affiliate_url":    process_single_link(final_url),
        }

    except Exception as e:
        logger.error(f"❌ [Single Manual Scrape Error] {e}")
    return None


# ---------------------------------------------------------------------------
# 8. TIKTOK MANUAL SCRAPER
# ---------------------------------------------------------------------------
def _fetch_tiktok_manual(url: str) -> dict | None:
    """Ambil data produk TikTok menggunakan StealthyFetcher (atau Fetcher biasa sebagai fallback)."""
    try:
        if STEALTH_AVAILABLE and StealthyFetcher is not None:
            res = StealthyFetcher().fetch(url, headless=True, network_idle=True, timeout=25000)
        else:
            logger.warning("⚠️ StealthyFetcher tidak tersedia, pakai Fetcher biasa untuk TikTok")
            res = _fetcher().get(url, timeout=15)
        if not res:
            return None

        title   = _og(res, "og:title")       or "Produk TikTok Shop"
        img_url = _og(res, "og:image")       or None
        desc    = _og(res, "og:description") or ""

        return {
            "platform":      "tiktok",
            "badge":         "🎵 TikTok Shop",
            "title":         title,
            "image_url":     img_url,
            "description":   desc[:300],
            "original_url":  url,
            "affiliate_url": process_single_link(url),
        }
    except Exception as e:
        logger.error(f"❌ [TikTok Scrape Error] {e}")
    return None


# ---------------------------------------------------------------------------
# Helpers: ekstrak meta tag dari Scrapling response
# ---------------------------------------------------------------------------
def _og(response, property_name: str) -> str | None:
    """Ambil content dari meta og: / meta name tag via Scrapling CSS selector."""
    try:
        # Scrapling mengekspos .css() pada response page
        els = response.css(f'meta[property="{property_name}"]')
        if els:
            return els[0].attrib.get("content", "").strip() or None
        # Fallback: meta name
        els = response.css(f'meta[name="{property_name}"]')
        if els:
            return els[0].attrib.get("content", "").strip() or None
    except Exception:
        pass
    return None


def _title_tag(response) -> str | None:
    """Ambil teks dari tag <title>."""
    try:
        els = response.css("title")
        if els:
            return els[0].text.split("|")[0].strip() or None
    except Exception:
        pass
    return None
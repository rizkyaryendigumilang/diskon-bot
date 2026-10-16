"""test_bot.py — Script untuk smoke test semua modul bot affiliate."""
import sys
sys.stdout.reconfigure(encoding="utf-8")

PASS = "[OK]"
WARN = "[WARN]"
FAIL = "[FAIL]"

# ─── 1. Scrapling Fetchers ───────────────────────────────────────────────────
print("=" * 50)
print("[1] Scrapling Fetchers")
print("=" * 50)
try:
    from scrapling.fetchers import Fetcher
    print(f"{PASS} Fetcher imported")
except ImportError as e:
    print(f"{FAIL} Fetcher: {e}")
    sys.exit(1)

try:
    from scrapling.fetchers import StealthyFetcher, DynamicFetcher
    print(f"{PASS} StealthyFetcher + DynamicFetcher imported")
    stealth_ok = True
except ImportError as e:
    print(f"{WARN} StealthyFetcher tidak tersedia: {e}")
    stealth_ok = False

# ─── 2. Modul bot ────────────────────────────────────────────────────────────
print()
print("=" * 50)
print("[2] Import modul bot")
print("=" * 50)
try:
    import scraper
    print(f"{PASS} scraper.py  (STEALTH_AVAILABLE={scraper.STEALTH_AVAILABLE})")
except Exception as e:
    print(f"{FAIL} scraper.py: {e}")

try:
    import bot
    print(f"{PASS} bot.py")
except Exception as e:
    print(f"{FAIL} bot.py: {e}")

try:
    import database
    database.init_db()
    print(f"{PASS} database.py (init_db OK)")
except Exception as e:
    print(f"{FAIL} database.py: {e}")

try:
    import converter
    test_url = "https://shopee.co.id/product/12345/67890"
    result_url = converter.process_single_link(test_url)
    print(f"{PASS} converter.py  -> {result_url[:60]}")
except Exception as e:
    print(f"{FAIL} converter.py: {e}")

# ─── 3. Live API Test — Shopee Search ────────────────────────────────────────
print()
print("=" * 50)
print("[3] Live Test: Shopee Search API")
print("=" * 50)
try:
    result = scraper.fetch_shopee_live("kaos pria", min_discount=20)
    if result:
        title = result.get("title", "")[:55]
        price = result.get("price_promo", 0)
        disc  = result.get("discount_percent", 0)
        img   = result.get("image_url", "")[:55]
        print(f"{PASS} Produk ditemukan!")
        print(f"     Judul : {title}")
        print(f"     Harga : Rp {price:,}  ({disc}% OFF)")
        print(f"     Gambar: {img}")
    else:
        print(f"{WARN} Shopee tidak return hasil — mungkin kena rate limit atau API berubah")
except Exception as e:
    print(f"{FAIL} Shopee fetch error: {e}")

# ─── 4. Live API Test — Blibli Search ────────────────────────────────────────
print()
print("=" * 50)
print("[4] Live Test: Blibli Search API")
print("=" * 50)
try:
    result = scraper.fetch_blibli_live("kaos pria")
    if result:
        title = result.get("title", "")[:55]
        price = result.get("price_promo", 0)
        print(f"{PASS} Produk ditemukan!")
        print(f"     Judul : {title}")
        print(f"     Harga : Rp {price:,}")
    else:
        print(f"{WARN} Blibli tidak return hasil")
except Exception as e:
    print(f"{FAIL} Blibli fetch error: {e}")

# ─── 5. Converter Test — Shopee shortlink ────────────────────────────────────
print()
print("=" * 50)
print("[5] Converter: Shopee affiliate URL")
print("=" * 50)
try:
    long_url = "https://shopee.co.id/Kaos-Pria-i.123456.987654321"
    aff = converter.process_single_link(long_url)
    if "d_id=" in aff:
        print(f"{PASS} Affiliate link berhasil dibuat")
        print(f"     -> {aff}")
    else:
        print(f"{WARN} d_id tidak ditemukan di URL: {aff}")
except Exception as e:
    print(f"{FAIL} Converter error: {e}")

print()
print("=" * 50)
print("SELESAI — Bot siap dijalankan dengan: python bot.py")
print("=" * 50)

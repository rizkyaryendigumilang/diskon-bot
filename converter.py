# converter.py
import urllib.parse
from config import AFFILIATE_IDS

def clean_url(url: str) -> str:
    """Membersihkan query parameter bawaan (seperti tracking id share) dari URL asli."""
    return url.split('?')[0]

def convert_to_affiliate(url: str, platform: str) -> str:
    """
    Mengonversi URL produk asli menjadi Link Afiliasi sesuai platform.
    """
    cleaned_url = clean_url(url)
    encoded_url = urllib.parse.quote(cleaned_url, safe='')

    if platform == "shopee":
        aff_id = AFFILIATE_IDS.get("shopee", "")
        # Template Deep Link / Redirect Shopee Affiliate
        return f"https://s.shopee.co.id/redirect?url={encoded_url}&sub_id={aff_id}"

    elif platform == "tokopedia":
        aff_id = AFFILIATE_IDS.get("tokopedia", "")
        # Template Deep Link / Redirect Tokopedia Affiliate / Aggregator
        return f"https://tokopedia.link/aff?url={encoded_url}&aff_id={aff_id}"

    elif platform == "tiktok":
        aff_id = AFFILIATE_IDS.get("tiktok", "")
        # Template Deep Link / Redirect TikTok Shop Affiliate
        return f"https://vt.tiktok.com/redirect?url={encoded_url}&sub_id={aff_id}"

    else:
        # Fallback jika platform tidak dikenal
        return cleaned_url


def process_multi_platform_links(links_dict: dict) -> dict:
    """
    Menerima dictionary link produk asli dari 3 platform dan mengembalikannya
    dalam bentuk link yang sudah ter-convert menjadi link afiliasi.
    
    Contoh Input:
    {
        "shopee": "https://shopee.co.id/product/123/456",
        "tokopedia": "https://tokopedia.com/toko/sepatu",
        "tiktok": "https://tiktok.com/shop/p/789"
    }
    """
    affiliate_links = {}
    for platform, original_url in links_dict.items():
        if original_url:
            affiliate_links[platform] = convert_to_affiliate(original_url, platform)
        else:
            affiliate_links[platform] = None
            
    return affiliate_links
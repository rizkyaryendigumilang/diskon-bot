# database.py
import sqlite3
from datetime import datetime

DB_NAME = "bot_settings.db"

def init_db():
    """Inisialisasi database SQLite dan tabel yang diperlukan."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Tabel untuk mencatat produk yang sudah diposting (mencegah duplikasi)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posted_items (
            product_id TEXT UNIQUE,
            title TEXT,
            posted_at TIMESTAMP
        )
    ''')
    
    # Auto-migration jika kolom belum ada pada database lama
    cols = [r[1] for r in cursor.execute("PRAGMA table_info(posted_items)").fetchall()]
    if "title" not in cols:
        cursor.execute("ALTER TABLE posted_items ADD COLUMN title TEXT")
    if "posted_at" not in cols:
        cursor.execute("ALTER TABLE posted_items ADD COLUMN posted_at TIMESTAMP")
    
    # Tabel untuk menyimpan pengaturan bot (kategori, diskon, interval, status)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            min_discount INTEGER,
            interval INTEGER,
            is_paused INTEGER
        )
    ''')
    
    conn.commit()
    conn.close()

def is_item_posted(product_id: str) -> bool:
    """Mengecek apakah suatu produk sudah pernah diposting sebelumnya."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM posted_items WHERE product_id = ?", (product_id,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def mark_item_posted(product_id: str, title: str = "Produk Diskon"):
    """Menandai produk bahwa sudah diposting ke channel."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR IGNORE INTO posted_items (product_id, title, posted_at) VALUES (?, ?, ?)", 
            (product_id, title, datetime.now())
        )
        conn.commit()
    except Exception as e:
        print(f"❌ [DB Error mark_item_posted]: {e}")
    finally:
        conn.close()

def get_settings() -> dict:
    """Mengambil konfigurasi aktif dari database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT category, min_discount, interval, is_paused FROM settings WHERE id = 1")
    row = cursor.fetchone()
    
    if not row:
        # Masukkan data default jika tabel settings masih kosong
        cursor.execute(
            "INSERT INTO settings (id, category, min_discount, interval, is_paused) VALUES (1, 'sport', 20, 30, 0)"
        )
        conn.commit()
        row = ('sport', 20, 30, 0)
        
    conn.close()
    return {
        "category": row[0], 
        "min_discount": row[1], 
        "interval": row[2], 
        "is_paused": row[3]
    }

def update_interval_setting(interval: int):
    """Memperbarui durasi interval waktu auto-post."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE settings SET interval = ? WHERE id = 1", (interval,))
    conn.commit()
    conn.close()

def update_category_setting(category: str):
    """Memperbarui kategori default."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE settings SET category = ? WHERE id = 1", (category,))
    conn.commit()
    conn.close()

def update_all_settings(category: str, min_discount: int, interval: int, is_paused: int):
    """Memperbarui semua konfigurasi engine sekaligus."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE settings SET category = ?, min_discount = ?, interval = ?, is_paused = ? WHERE id = 1",
        (category, min_discount, interval, is_paused)
    )
    conn.commit()
    conn.close()

def get_all_posted_items(limit: int = 100, offset: int = 0, search: str = "") -> list[dict]:
    """Mengambil daftar produk yang telah diposting dengan pencarian opsional."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    if search:
        query = """
            SELECT rowid, product_id, title, posted_at 
            FROM posted_items 
            WHERE title LIKE ? OR product_id LIKE ? 
            ORDER BY rowid DESC LIMIT ? OFFSET ?
        """
        pattern = f"%{search}%"
        cursor.execute(query, (pattern, pattern, limit, offset))
    else:
        query = """
            SELECT rowid, product_id, title, posted_at 
            FROM posted_items 
            ORDER BY rowid DESC LIMIT ? OFFSET ?
        """
        cursor.execute(query, (limit, offset))
        
    rows = cursor.fetchall()
    conn.close()
    
    items = []
    for r in rows:
        # Tentukan platform badge dari prefix product_id
        pid = r[1] or ""
        platform = "shopee"
        badge = "Shopee"
        if pid.startswith("tkp_"):
            platform = "tokopedia"
            badge = "Tokopedia"
        elif pid.startswith("blb_"):
            platform = "blibli"
            badge = "Blibli"
        elif pid.startswith("lzd_"):
            platform = "lazada"
            badge = "Lazada"
        elif pid.startswith("ttk_") or "tiktok" in pid:
            platform = "tiktok"
            badge = "TikTok Shop"
            
        items.append({
            "id": r[0],
            "product_id": pid,
            "title": r[2] or "Produk Tanpa Judul",
            "posted_at": str(r[3]) if r[3] else "",
            "platform": platform,
            "badge": badge
        })
    return items

def delete_posted_item(product_id: str) -> bool:
    """Menghapus item dari posted_items sehingga dapat di-scrape/dipost ulang."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM posted_items WHERE product_id = ?", (product_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def get_database_stats() -> dict:
    """Mengambil statistik cepat jumlah postingan dan marketplace."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM posted_items")
    total_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT product_id FROM posted_items")
    pids = [r[0] for r in cursor.fetchall() if r[0]]
    conn.close()
    
    breakdown = {"shopee": 0, "tokopedia": 0, "blibli": 0, "lazada": 0, "tiktok": 0, "other": 0}
    for p in pids:
        if p.startswith("shp_"):
            breakdown["shopee"] += 1
        elif p.startswith("tkp_"):
            breakdown["tokopedia"] += 1
        elif p.startswith("blb_"):
            breakdown["blibli"] += 1
        elif p.startswith("lzd_"):
            breakdown["lazada"] += 1
        elif p.startswith("ttk_") or "tiktok" in p:
            breakdown["tiktok"] += 1
        else:
            breakdown["other"] += 1
            
    return {
        "total_posted": total_count,
        "breakdown": breakdown
    }
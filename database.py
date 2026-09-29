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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT UNIQUE,
            title TEXT,
            posted_at TIMESTAMP
        )
    ''')
    
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
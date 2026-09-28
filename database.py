# database.py
import sqlite3

def init_db():
    conn = sqlite3.connect('bot_settings.db')
    cursor = conn.cursor()
    
    # Tabel Pengaturan Bot (Kategori, Min Diskon, Status Pause, dan Interval Waktu)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            min_discount INTEGER,
            is_paused INTEGER,
            interval INTEGER
        )
    ''')
    
    # Tabel Histori Produk Ter-post (Mencegah duplikasi)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posted_items (
            product_id TEXT PRIMARY KEY
        )
    ''')
    
    # Masukkan data default jika belum ada
    cursor.execute("SELECT COUNT(*) FROM settings")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO settings (category, min_discount, is_paused, interval) VALUES (?, ?, ?, ?)", 
                       ("sport", 20, 0, 30))
        
    conn.commit()
    conn.close()

def get_settings():
    conn = sqlite3.connect('bot_settings.db')
    cursor = conn.cursor()
    cursor.execute("SELECT category, min_discount, is_paused, interval FROM settings WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"category": row[0], "min_discount": row[1], "is_paused": row[2], "interval": row[3]}
    return {"category": "sport", "min_discount": 20, "is_paused": 0, "interval": 30}

def update_interval_setting(minutes: int):
    conn = sqlite3.connect('bot_settings.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE settings SET interval = ? WHERE id = 1", (minutes,))
    conn.commit()
    conn.close()

def is_item_posted(product_id: str) -> bool:
    conn = sqlite3.connect('bot_settings.db')
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM posted_items WHERE product_id = ?", (product_id,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def mark_item_posted(product_id: str):
    conn = sqlite3.connect('bot_settings.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO posted_items (product_id) VALUES (?)", (product_id,))
    conn.commit()
    conn.close()

# Inisialisasi DB saat modul dipanggil
init_db()
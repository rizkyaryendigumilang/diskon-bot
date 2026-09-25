# database.py
import sqlite3
from config import DB_NAME

def get_connection():
    """Membuat koneksi ke file database SQLite."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # Mengembalikan hasil query dalam bentuk dictionary-like
    return conn

def init_db():
    """Inisialisasi tabel database saat bot pertama kali dijalankan."""
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Tabel Konfigurasi Admin (Setting Engine)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY DEFAULT 1,
            category TEXT DEFAULT 'sport',
            min_discount INTEGER DEFAULT 20,
            platform TEXT DEFAULT 'all',
            is_paused INTEGER DEFAULT 0
        )
    ''')

    # Insert default settings jika tabel masih kosong
    cursor.execute('SELECT COUNT(*) FROM settings')
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO settings (id, category, min_discount, platform, is_paused)
            VALUES (1, 'sport', 20, 'all', 0)
        ''')

    # 2. Tabel Histori Postingan (Anti-Duplicate Filter)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posted_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT UNIQUE,
            title TEXT,
            posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()
    print("✅ Database SQLite berhasil diinisialisasi!")

# --- FUNGSI PENGELOLA SETTINGS (ADMIN CONTROL) ---

def get_settings():
    """Mengambil konfigurasi aktif saat ini."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT category, min_discount, platform, is_paused FROM settings WHERE id = 1')
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else {}

def update_setting(key: str, value):
    """Mengubah parameter konfigurasi admin (category, min_discount, platform, is_paused)."""
    conn = get_connection()
    cursor = conn.cursor()
    # Query dinamis sesuai field yang diubah
    query = f"UPDATE settings SET {key} = ? WHERE id = 1"
    cursor.execute(query, (value,))
    conn.commit()
    conn.close()

# --- FUNGSI ANTI-DUPLICATE (HISTORI POSTINGAN) ---

def is_item_posted(product_id: str) -> bool:
    """Mengecek apakah produk sudah pernah di-blast ke channel."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM posted_items WHERE product_id = ?', (product_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def add_posted_item(product_id: str, title: str):
    """Menyimpan ID produk yang baru saja di-blast."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO posted_items (product_id, title) VALUES (?, ?)', (product_id, title))
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # Abaikan jika ID sudah ada
    finally:
        conn.close()
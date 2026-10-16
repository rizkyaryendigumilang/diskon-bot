# DiskonBot — Affiliate Marketing Bot & Web Dashboard

Sistem otomatisasi penarik diskon dan konversi link afiliasi multi-marketplace (Shopee, Tokopedia, Blibli, Lazada, TikTok) untuk Channel Telegram `@infodiskonbykiky`, dilengkapi Web Dashboard Control Center (Flat Design 2D).

---

## 🚀 Pilihan Cara Menjalankan Sistem

Anda dapat memilih untuk menjalankan **semua service sekaligus** dalam 1 perintah, atau menjalankannya **secara terpisah**:

### Opsi A: Jalankan SEMUA Service Sekaligus (Frontend + Bot)
Mengaktifkan Web Dashboard di port 8000 dan Telegram Bot polling secara bersamaan.

* **Via Batch Script (Double-click / CMD):**
  ```cmd
  start_diskon_bot.bat
  ```
  *(Atau ketik `start_all.bat` — ini otomatis membuka 2 jendela konsol untuk masing-masing service)*

* **Via Terminal Tunggal / Python:**
  ```powershell
  python start_all.py
  ```
  *(Menjalankan keduanya dalam satu sesi terminal, tekan `Ctrl+C` untuk mematikan keduanya sekaligus)*

---

### Opsi B: Jalankan Secara Terpisah (Independent)

#### 1. Menjalankan Frontend Saja (Web Dashboard & REST API)
* **Via Batch Script:**
  ```cmd
  start_frontend.bat
  ```
* **Via Terminal:**
  ```powershell
  python server.py
  ```
* **Akses Browser:** Buka [http://localhost:8000](http://localhost:8000)
* **Kredensial Login:** Password default `admin123` atau ID Telegram Admin `8503838227`.

#### 2. Menjalankan Bot Telegram Saja (Polling Service)
* **Via Batch Script:**
  ```cmd
  start_bot.bat
  ```
* **Via Terminal:**
  ```powershell
  python bot.py
  ```

---

## 📁 Struktur File Utama

- [start_diskon_bot.bat](file:///c:/Users/rizky/Documents/Dev/diskon-bot/start_diskon_bot.bat): Script 1-klik untuk mengaktifkan SEMUA service (Frontend + Bot) di jendela terpisah.
- [start_all.py](file:///c:/Users/rizky/Documents/Dev/diskon-bot/start_all.py): Master runner Python untuk menjalankan kedua service sekaligus.
- [start_frontend.bat](file:///c:/Users/rizky/Documents/Dev/diskon-bot/start_frontend.bat): Script 1-klik untuk start Frontend saja.
- [start_bot.bat](file:///c:/Users/rizky/Documents/Dev/diskon-bot/start_bot.bat): Script 1-klik untuk start Telegram Bot saja.
- [server.py](file:///c:/Users/rizky/Documents/Dev/diskon-bot/server.py): Backend FastAPI & Static Web Server untuk frontend dashboard.
- [index.html](file:///c:/Users/rizky/Documents/Dev/diskon-bot/index.html): Tampilan Flat Design 2D UI frontend (Live Monitor, Converter, Engine Control, Settings).
- [bot.py](file:///c:/Users/rizky/Documents/Dev/diskon-bot/bot.py): Telegram Bot Polling v20.8 (Menu Admin, Scan, Video Review Handler).
- [scraper.py](file:///c:/Users/rizky/Documents/Dev/diskon-bot/scraper.py): Scrapling Engine v0.4 (Patchright StealthyFetcher & DynamicFetcher).
- [converter.py](file:///c:/Users/rizky/Documents/Dev/diskon-bot/converter.py): Dual-path Affiliate Link Converter.
- [database.py](file:///c:/Users/rizky/Documents/Dev/diskon-bot/database.py): SQLite Database & Anti-Duplikasi.
- [config.py](file:///c:/Users/rizky/Documents/Dev/diskon-bot/config.py): Konfigurasi Token, Channel ID, dan Affiliate ID.

# start_all.py — Unified Master Launcher for DiskonBot
import os
import signal
import subprocess
import sys
import time

def main():
    print("=" * 60)
    print("  DISKON-BOT: MEMULAI SEMUA SERVICE (FRONTEND + BOT)")
    print("=" * 60)

    # 1. Start Frontend Server
    print("  [1/2] Menjalankan Frontend Web Dashboard (http://localhost:8000)...")
    p_server = subprocess.Popen([sys.executable, "server.py"])
    time.sleep(1.5)

    # 2. Start Telegram Bot Service
    print("  [2/2] Menjalankan Telegram Bot Service (@infodiskonbykiky)...")
    p_bot = subprocess.Popen([sys.executable, "bot.py"])

    print("=" * 60)
    print("  ✅ SEMUA SERVICE BERHASIL DIAKTIFKAN!")
    print("  - Frontend Dashboard : http://localhost:8000")
    print("  - Telegram Bot       : Polling aktif")
    print("  Tekan Ctrl+C untuk menghentikan semua service sekaligus.")
    print("=" * 60)

    def shutdown(sig=None, frame=None):
        print("\n⏳ Menghentikan seluruh service...")
        for p, name in [(p_server, "Frontend Server"), (p_bot, "Telegram Bot")]:
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    p.kill()
                print(f"  🛑 {name} dihentikan.")
        print("Selesai.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, shutdown)

    try:
        while True:
            # Monitor process health
            if p_server.poll() is not None:
                print(f"⚠️ Frontend Server berhenti dengan kode {p_server.poll()}")
                break
            if p_bot.poll() is not None:
                print(f"⚠️ Telegram Bot berhenti dengan kode {p_bot.poll()}")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        shutdown()

if __name__ == "__main__":
    main()

# keep_alive.py
import threading
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot Info Diskon Aktif dan Berjalan 24 Jam!")

    # Mematikan log bawaan agar terminal tidak spam
    def log_message(self, format, *args):
        pass

def run():
    # Render akan memberikan port secara dinamis lewat environment variable
    port = int(os.environ.get('PORT', 8080))
    server_address = ('0.0.0.0', port)
    httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)
    print(f"🌐 Dummy Web Server berjalan di port {port} untuk mengelabui Render...")
    httpd.serve_forever()

def keep_alive():
    t = threading.Thread(target=run)
    t.daemon = True
    t.start()
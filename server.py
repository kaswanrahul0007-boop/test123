#!/usr/bin/env python3
"""Hello-message website served over HTTPS (default 131.1.65.123:443)."""
import os
import ssl
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

HOST = os.environ.get("HOST", "131.1.65.123")
PORT = int(os.environ.get("PORT", "443"))
CERT = os.environ.get("CERT", "cert.pem")
KEY = os.environ.get("KEY", "key.pem")

PAGE = b"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hello</title>
<style>body{display:grid;place-items:center;height:100vh;margin:0;font-family:system-ui,sans-serif;background:#0f172a;color:#f8fafc}h1{font-size:3rem}</style>
</head>
<body><h1>Hello, World!</h1></body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(PAGE)))
        self.end_headers()
        self.wfile.write(PAGE)


def ensure_cert():
    if os.path.exists(CERT) and os.path.exists(KEY):
        return
    subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "365",
         "-keyout", KEY, "-out", CERT, "-subj", f"/CN={HOST}",
         "-addext", f"subjectAltName=IP:{HOST}"],
        check=True, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    ensure_cert()
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(CERT, KEY)
    try:
        httpd = HTTPServer((HOST, PORT), Handler)
    except OSError as e:
        sys.exit(f"Cannot bind {HOST}:{PORT}: {e}\n(Port 443 needs root, and {HOST} must be an address on this machine.)")
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    print(f"Serving https://{HOST}:{PORT}")
    httpd.serve_forever()

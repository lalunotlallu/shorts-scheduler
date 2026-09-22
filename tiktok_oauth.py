import base64
import hashlib
import json
import os
import secrets
import threading
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

BASE_DIR = Path(r"E:\ShortsScheduler")
ENV_FILE = BASE_DIR / ".env"
TOKEN_FILE = BASE_DIR / "tiktok_token.json"

AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"

def load_env():
    values = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values

env = load_env()

CLIENT_KEY = env["TIKTOK_CLIENT_KEY"]
CLIENT_SECRET = env["TIKTOK_CLIENT_SECRET"]
REDIRECT_URI = env["TIKTOK_REDIRECT_URI"]

parsed = urllib.parse.urlparse(REDIRECT_URI)
HOST = parsed.hostname or "localhost"
PORT = parsed.port or 80

code_verifier = secrets.token_urlsafe(64)
challenge = hashlib.sha256(
    code_verifier.encode()
).hexdigest()

state = secrets.token_urlsafe(32)
result = {}

class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        params = urllib.parse.parse_qs(
            urllib.parse.urlparse(self.path).query
        )

        if params.get("state", [""])[0] != state:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Invalid state.")
            return

        if "error" in params:
            result["error"] = params["error"][0]
        else:
            result["code"] = params.get("code", [""])[0]

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(
            b"<h1>TikTok authorization complete.</h1>"
            b"<p>You can close this browser window.</p>"
        )

        threading.Thread(
            target=server.shutdown,
            daemon=True
        ).start()

    def log_message(self, format, *args):
        pass

server = HTTPServer((HOST, PORT), CallbackHandler)

params = {
    "client_key": CLIENT_KEY,
    "response_type": "code",
    "scope": "user.info.basic,video.publish",
    "redirect_uri": REDIRECT_URI,
    "state": state,
    "code_challenge": challenge,
    "code_challenge_method": "S256",
}

auth_url = AUTH_URL + "?" + urllib.parse.urlencode(params)

print("Opening TikTok authorization...")
print()
print(auth_url)
print()

webbrowser.open(auth_url)

server.serve_forever()

if "error" in result:
    raise RuntimeError(f"TikTok authorization failed: {result['error']}")

authorization_code = result.get("code")

if not authorization_code:
    raise RuntimeError("No authorization code received.")

token_data = urllib.parse.urlencode({
    "client_key": CLIENT_KEY,
    "client_secret": CLIENT_SECRET,
    "code": authorization_code,
    "grant_type": "authorization_code",
    "redirect_uri": REDIRECT_URI,
    "code_verifier": code_verifier,
}).encode()

request = urllib.request.Request(
    TOKEN_URL,
    data=token_data,
    headers={
        "Content-Type": "application/x-www-form-urlencoded",
    },
    method="POST",
)

with urllib.request.urlopen(request, timeout=60) as response:
    tokens = json.loads(response.read().decode("utf-8"))

if "access_token" not in tokens:
    raise RuntimeError(f"TikTok token exchange failed: {tokens}")

TOKEN_FILE.write_text(
    json.dumps(tokens, indent=2),
    encoding="utf-8"
)

print()
print("SUCCESS!")
print(f"Token saved to: {TOKEN_FILE}")
print()
print("Access token received.")
print("Refresh token received:", "refresh_token" in tokens)
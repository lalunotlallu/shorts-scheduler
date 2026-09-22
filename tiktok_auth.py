import hashlib
import json
import os
import secrets
import string
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlencode, urlparse, parse_qs
from urllib.request import Request, urlopen


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(BASE_DIR, ".env")
TOKEN_FILE = os.path.join(BASE_DIR, "tiktok_token.json")

AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"

REDIRECT_URI = "http://localhost:3455/callback/"
PORT = 3455


def load_env():
    if not os.path.exists(ENV_FILE):
        raise RuntimeError(".env file not found.")

    values = {}

    with open(ENV_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()

    return values


env = load_env()

CLIENT_KEY = env.get("TIKTOK_CLIENT_KEY")
CLIENT_SECRET = env.get("TIKTOK_CLIENT_SECRET")

if not CLIENT_KEY:
    raise RuntimeError("TIKTOK_CLIENT_KEY missing from .env")

if not CLIENT_SECRET:
    raise RuntimeError("TIKTOK_CLIENT_SECRET missing from .env")


# --------------------------------------------------
# PKCE
# --------------------------------------------------

def generate_code_verifier():
    alphabet = string.ascii_letters + string.digits + "-._~"
    return "".join(secrets.choice(alphabet) for _ in range(64))


def generate_code_challenge(verifier):
    digest = hashlib.sha256(
        verifier.encode("ascii")
    ).hexdigest()

    return digest


# --------------------------------------------------
# OAuth callback
# --------------------------------------------------

result = {}
server = None


class CallbackHandler(BaseHTTPRequestHandler):

    def do_GET(self):

        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        result["code"] = params.get("code", [None])[0]
        result["state"] = params.get("state", [None])[0]
        result["error"] = params.get("error", [None])[0]
        result["error_description"] = params.get(
            "error_description",
            [None]
        )[0]

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()

        if result["code"]:
            self.wfile.write(
                b"""
                <html>
                <body style="font-family:Arial;text-align:center;padding:60px">
                <h1>TikTok connected!</h1>
                <p>You can close this window and return to Shorts Scheduler.</p>
                </body>
                </html>
                """
            )
        else:
            self.wfile.write(
                b"""
                <html>
                <body style="font-family:Arial;text-align:center;padding:60px">
                <h1>TikTok authorization failed.</h1>
                <p>Return to the Shorts Scheduler window for details.</p>
                </body>
                </html>
                """
            )

        threading.Thread(
            target=server.shutdown,
            daemon=True
        ).start()

    def log_message(self, format, *args):
        pass


# --------------------------------------------------
# Token exchange
# --------------------------------------------------

def exchange_code(code, code_verifier):

    data = urlencode({
        "client_key": CLIENT_KEY,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
        "code_verifier": code_verifier,
    }).encode()

    request = Request(
        TOKEN_URL,
        data=data,
        headers={
            "Content-Type":
                "application/x-www-form-urlencoded",
            "Cache-Control":
                "no-cache",
        },
        method="POST",
    )

    with urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8")

    return json.loads(body)


# --------------------------------------------------
# Main
# --------------------------------------------------

def main():

    global server

    state = secrets.token_urlsafe(32)

    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(
        code_verifier
    )

    params = {
        "client_key": CLIENT_KEY,
        "response_type": "code",
        "scope": "user.info.basic,video.publish,video.upload",
        "redirect_uri": REDIRECT_URI,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }

    authorization_url = (
        AUTH_URL
        + "?"
        + urlencode(params)
    )

    server = HTTPServer(
        ("localhost", PORT),
        CallbackHandler
    )

    print()
    print("=" * 60)
    print("TIKTOK LOGIN")
    print("=" * 60)
    print()
    print("Opening TikTok authorization...")
    print()

    threading.Thread(
        target=server.serve_forever,
        daemon=True
    ).start()

    webbrowser.open(authorization_url)

    print("Waiting for TikTok authorization...")
    print()

    server.serve_forever()

    server.server_close()

    if result.get("error"):
        print()
        print("TikTok authorization failed:")
        print(result["error"])
        print(result.get("error_description"))
        return

    code = result.get("code")

    if not code:
        print("No authorization code received.")
        return

    if result.get("state") != state:
        print("ERROR: State verification failed.")
        return

    print("Authorization received.")
    print("Exchanging code for tokens...")

    token_data = exchange_code(
        code,
        code_verifier
    )

    if "access_token" not in token_data:
        print()
        print("Token exchange failed:")
        print(json.dumps(
            token_data,
            indent=2
        ))
        return

    with open(
        TOKEN_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            token_data,
            f,
            indent=2
        )

    print()
    print("=" * 60)
    print("SUCCESS")
    print("=" * 60)
    print()
    print("TikTok account connected.")
    print()
    print(f"Token saved to:")
    print(TOKEN_FILE)
    print()


if __name__ == "__main__":
    main()
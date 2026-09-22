import json
import os
import time
import requests
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE_DIR = Path(r"E:\ShortsScheduler")
TOKEN_FILE = BASE_DIR / "tiktok_token.json"
def load_env():
    values = {}
    env_file = BASE_DIR / ".env"

    if not env_file.exists():
        return values

    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()

    return values


ENV = load_env()
CLIENT_KEY = ENV.get("TIKTOK_CLIENT_KEY") or os.getenv("TIKTOK_CLIENT_KEY")
CLIENT_SECRET = ENV.get("TIKTOK_CLIENT_SECRET") or os.getenv("TIKTOK_CLIENT_SECRET")

INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"
STATUS_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"
CREATOR_INFO_URL = "https://open.tiktokapis.com/v2/post/publish/creator_info/query/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"

CHUNK_SIZE = 10 * 1024 * 1024  # 10 MB


def load_token():
    if not TOKEN_FILE.exists():
        raise RuntimeError("tiktok_token.json not found.")

    with TOKEN_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)
def save_token(token_data):
    with TOKEN_FILE.open("w", encoding="utf-8") as f:
        json.dump(token_data, f, indent=2)


def refresh_access_token(refresh_token):
    data = urllib.parse.urlencode({
        "client_key": CLIENT_KEY,
        "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }).encode("utf-8")

    request = urllib.request.Request(
        TOKEN_URL,
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"TikTok token refresh HTTP {e.code}: {body}")

    if "access_token" not in result:
        raise RuntimeError(f"TikTok token refresh failed: {result}")

    save_token(result)
    return result


def api_post(url, access_token, payload):
    data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"TikTok API HTTP {e.code}: {body}")


def upload_file(upload_url, video_path):
    video_size = video_path.stat().st_size

    total_chunks = video_size // CHUNK_SIZE

    print(f"Video size: {video_size:,} bytes")
    print(f"Chunk size: {CHUNK_SIZE:,} bytes")
    print(f"Total chunks: {total_chunks}")

    with video_path.open("rb") as f:

        for chunk_number in range(total_chunks):

            start = chunk_number * CHUNK_SIZE

            if chunk_number == total_chunks - 1:
                end = video_size
            else:
                end = min(start + CHUNK_SIZE, video_size)

            chunk_size = end - start

            data = f.read(chunk_size)

            content_range = f"bytes {start}-{end - 1}/{video_size}"

            print(
                f"Uploading chunk {chunk_number + 1}/{total_chunks} "
                f"({start:,}-{end - 1:,})"
            )

            request = urllib.request.Request(
                upload_url,
                data=data,
                headers={
                    "Content-Type": "video/mp4",
                    "Content-Length": str(len(data)),
                    "Content-Range": content_range,
                },
                method="PUT",
            )

            try:
                with urllib.request.urlopen(request, timeout=180) as response:

                    print(
                        f"  TikTok response: {response.status}"
                    )

                    if response.status not in (200, 201, 206):
                        raise RuntimeError(
                            f"Unexpected upload status: {response.status}"
                        )

            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")

                raise RuntimeError(
                    f"TikTok upload HTTP {e.code}: {body}"
                )

            time.sleep(1)


def wait_for_publish(access_token, publish_id, timeout_seconds=180):

    started = time.time()

    while time.time() - started < timeout_seconds:

        result = api_post(
            STATUS_URL,
            access_token,
            {"publish_id": publish_id},
        )

        error = result.get("error", {})

        if error.get("code") != "ok":
            raise RuntimeError(
                f"Status check failed: {error}"
            )

        data = result.get("data", {})
        status = data.get("status")

        print(f"TikTok publish status: {status}")

        if status == "PUBLISH_COMPLETE":
            return True

        if status in {"FAILED", "PUBLISH_FAILED"}:
            raise RuntimeError(
                f"TikTok publishing failed: {data}"
            )

        time.sleep(5)

    raise RuntimeError(
        "Timed out waiting for TikTok publishing."
    )

def get_creator_info(access_token):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    response = requests.post(
        CREATOR_INFO_URL,
        headers=headers,
        json={},
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    if data.get("error", {}).get("code") not in (None, "ok"):
        raise RuntimeError(
            f"TikTok creator info error: {data.get('error')}"
        )

    return data.get("data", {})

def upload_to_tiktok(video_path, caption="", privacy_level=None):

    video_path = Path(video_path)

    if not video_path.exists():
        print(f"TikTok: video not found: {video_path}")
        return False

    try:

        token_data = load_token()

        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")

        if not access_token:
            if not refresh_token:
                raise RuntimeError("No TikTok access or refresh token.")

            token_data = refresh_access_token(refresh_token)
            access_token = token_data["access_token"]

        creator_info = get_creator_info(access_token)

        print(
            f"TikTok creator: "
            f"{creator_info.get('creator_nickname', 'Unknown')}"
            f" (@{creator_info.get('creator_username', 'Unknown')})"
        )

        privacy_options = creator_info.get(
            "privacy_level_options", []
        )

        if not privacy_options:
            raise RuntimeError(
                "TikTok returned no privacy level options."
            )

        print(
            f"TikTok privacy options: "
            f"{', '.join(privacy_options)}"
        )

        video_size = video_path.stat().st_size

        print()
        print("=" * 60)
        print("TIKTOK DIRECT POST")
        print("=" * 60)

        print(f"Video: {video_path.name}")
        print(f"Size: {video_size:,} bytes")

        total_chunks = video_size // CHUNK_SIZE

        payload = {
            "post_info": {
                "title": caption,
                "privacy_level": (
                    privacy_level
                    if privacy_level in privacy_options
                    else (
                        "SELF_ONLY"
                        if "SELF_ONLY" in privacy_options
                        else privacy_options[0]
                    )
                ),
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": video_size,
                "chunk_size": CHUNK_SIZE,
                "total_chunk_count": total_chunks,
            },
        }

        print()
        print("Initializing TikTok Direct Post...")

        result = api_post(
            INIT_URL,
            access_token,
            payload,
        )

        error = result.get("error", {})

        if error.get("code") != "ok":
            raise RuntimeError(
                f"TikTok initialization failed: {error}"
            )

        publish_id = result["data"]["publish_id"]
        upload_url = result["data"]["upload_url"]

        print("TikTok publish ID received.")

        print()
        print("Uploading video in chunks...")

        upload_file(
            upload_url,
            video_path,
        )

        print()
        print("Video upload complete.")

        print()
        print("Waiting for TikTok processing...")

        success = wait_for_publish(
            access_token,
            publish_id,
        )

        if success:

            print()
            print("TikTok: PUBLISH_COMPLETE")
            print("=" * 60)

            return True

    except Exception as exc:

        print()
        print(f"TikTok upload failed: {exc}")
        print("=" * 60)

        return False


if __name__ == "__main__":

    test_video = Path(
        r"E:\Shorts\eea-1.mp4"
    )

    success = upload_to_tiktok(
        test_video
    )

    print()

    if success:
        print("TEST RESULT: SUCCESS")
    else:
        print("TEST RESULT: FAILED")
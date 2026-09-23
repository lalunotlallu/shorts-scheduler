import sys
import os
import subprocess
sys.path.insert(0, r"E:\ShortsScheduler")
from uploader import load_token, get_creator_info
import json
from datetime import date, datetime, time, timedelta
from pathlib import Path

import streamlit as st

for key in [
    "TIKTOK_CLIENT_KEY",
    "TIKTOK_CLIENT_SECRET",
    "TIKTOK_ACCESS_TOKEN",
    "TIKTOK_REFRESH_TOKEN",
]:
    if key in st.secrets:
        os.environ[key] = st.secrets[key]

SHORTS_FOLDER = Path(r"E:\Shorts")
SCHEDULE_FILE = Path(r"E:\ShortsScheduler\schedule.json")

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}


st.set_page_config(
    page_title="Shorts Scheduler",
    page_icon="🎬",
    layout="wide",
)

st.title("🎬 Shorts Scheduler")
st.caption("Schedule and control your Shorts publishing queue.")
# --------------------------------------------------
# TikTok account
# --------------------------------------------------

privacy_options = []
tiktok_privacy = None
st.header("🎵 TikTok")

try:
    token_data = load_token()
    access_token = token_data.get("access_token")

    if access_token:
        creator_info = get_creator_info(access_token)

        nickname = creator_info.get(
            "creator_nickname",
            "Unknown",
        )

        username = creator_info.get(
            "creator_username",
            "Unknown",
        )

        privacy_options = creator_info.get(
            "privacy_level_options",
            [],
        )

        st.success(
            f"Connected: **{nickname}** "
            f"(@{username})"
        )

        st.caption(
            "Available privacy options: "
            + ", ".join(privacy_options)
        )

    else:
        st.warning(
            "TikTok is not connected."
        )

        if st.button("🔗 Connect TikTok"):
            subprocess.Popen([
                sys.executable,
                r"E:\ShortsScheduler\tiktok_oauth.py",
            ])

            st.info(
                "TikTok authorization opened in your browser. "
                "Complete the authorization, then refresh this page."
            )

except Exception as exc:
    st.error(
        f"Could not load TikTok account: {exc}"
    )


# --------------------------------------------------
# Helpers
# --------------------------------------------------

def load_schedule():
    if not SCHEDULE_FILE.exists():
        return {}

    try:
        text = SCHEDULE_FILE.read_text(encoding="utf-8").strip()

        if not text:
            return {}

        return json.loads(text)

    except Exception:
        return {}


def save_schedule(schedule):
    SCHEDULE_FILE.write_text(
        json.dumps(schedule, indent=2),
        encoding="utf-8",
    )


# --------------------------------------------------
# Folder
# --------------------------------------------------

SHORTS_FOLDER.mkdir(parents=True, exist_ok=True)

videos = sorted(
    [
        p
        for p in SHORTS_FOLDER.iterdir()
        if p.is_file()
        and p.suffix.lower() in VIDEO_EXTENSIONS
    ],
    key=lambda p: p.name.lower(),
)


# --------------------------------------------------
# Session state
# --------------------------------------------------

if "selected_videos" not in st.session_state:
    st.session_state.selected_videos = {}

for video in videos:
    st.session_state.selected_videos.setdefault(
        str(video),
        True,
    )

for path in list(st.session_state.selected_videos):
    if not Path(path).exists():
        del st.session_state.selected_videos[path]


# --------------------------------------------------
# Current schedule status
# --------------------------------------------------

schedule = load_schedule()

if schedule:
    scheduler_state = schedule.get(
        "scheduler_state",
        "active",
    )
else:
    scheduler_state = "cancelled"


# --------------------------------------------------
# Status banner
# --------------------------------------------------

if scheduler_state == "active":
    st.success("🟢 Schedule is ACTIVE")

elif scheduler_state == "paused":
    st.warning("⏸️ Schedule is PAUSED")

else:
    st.info("⚪ No active schedule")


# --------------------------------------------------
# Schedule controls
# --------------------------------------------------

col1, col2, col3 = st.columns(3)

with col1:
    if st.button(
        "⏸️ Pause Schedule",
        use_container_width=True,
        disabled=scheduler_state != "active",
    ):
        schedule["scheduler_state"] = "paused"
        save_schedule(schedule)
        st.rerun()

with col2:
    if st.button(
        "▶️ Resume Schedule",
        use_container_width=True,
        disabled=scheduler_state != "paused",
    ):
        schedule["scheduler_state"] = "active"
        save_schedule(schedule)
        st.rerun()

with col3:
    if st.button(
        "🗑️ Cancel Schedule",
        use_container_width=True,
        disabled=not bool(schedule),
    ):
        cancelled_schedule = schedule.copy()
        cancelled_schedule["scheduler_state"] = "cancelled"

        for item in cancelled_schedule.get("items", []):
            if item.get("status") == "scheduled":
                item["status"] = "cancelled"

        save_schedule(cancelled_schedule)
        st.rerun()


# --------------------------------------------------
# Shorts library
# --------------------------------------------------

st.header("📁 Shorts")

st.caption(f"Folder: `{SHORTS_FOLDER}`")

if not videos:

    st.info(
        "No Shorts found. Put rendered videos into "
        f"`{SHORTS_FOLDER}`."
    )

else:

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "Select All",
            use_container_width=True,
        ):
            for video in videos:
                st.session_state.selected_videos[
                    str(video)
                ] = True

            st.rerun()

    with col2:
        if st.button(
            "Deselect All",
            use_container_width=True,
        ):
            for video in videos:
                st.session_state.selected_videos[
                    str(video)
                ] = False

            st.rerun()

    st.divider()

    selected_count = 0

    for video in videos:

        selected = st.checkbox(
            video.name,
            value=st.session_state.selected_videos.get(
                str(video),
                True,
            ),
            key=f"video_{video.name}",
        )

        st.session_state.selected_videos[
            str(video)
        ] = selected

        if selected:
            selected_count += 1

    st.write(
        f"**{selected_count} Shorts selected**"
    )


# --------------------------------------------------
# Scheduling settings
# --------------------------------------------------

st.header("📅 New Schedule")

col1, col2 = st.columns(2)

with col1:
    start_date = st.date_input(
        "Start date",
        value=date.today(),
    )

with col2:
    upload_time = st.time_input(
        "First upload",
        value=time(20, 30),
    )


col1, col2 = st.columns(2)

with col1:
    interval_days = st.number_input(
        "Days between uploads",
        min_value=1,
        max_value=30,
        value=1,
        step=1,
    )

with col2:
    order = st.selectbox(
        "Video order",
        [
            "Filename order",
            "Random order",
        ],
    )


# --------------------------------------------------
# Platforms
# --------------------------------------------------

st.subheader("Platforms")

col1, col2, col3 = st.columns(3)

with col1:
    platform_youtube = st.checkbox(
        "YouTube Shorts",
        value=True,
    )

with col2:
    platform_tiktok = st.checkbox(
        "TikTok",
        value=True,
    )

with col3:
    platform_instagram = st.checkbox(
        "Instagram Reels",
        value=True,
    )

# --------------------------------------------------
# TikTok publishing settings
# --------------------------------------------------

if platform_tiktok:
    st.caption("TikTok publishing settings")

    tiktok_privacy = st.selectbox(
        "Privacy level",
        privacy_options,
        index=(
            privacy_options.index("SELF_ONLY")
            if "SELF_ONLY" in privacy_options
            else 0
        ),
    )

# --------------------------------------------------
# Create schedule
# --------------------------------------------------

if st.button(
    "🚀 Create Schedule",
    type="primary",
    use_container_width=True,
):

    selected = [
        video
        for video in videos
        if st.session_state.selected_videos.get(
            str(video),
            False,
        )
    ]

    if not selected:
        st.error(
            "Select at least one Short."
        )
        st.stop()

    platforms = []

    if platform_youtube:
        platforms.append("youtube")

    if platform_tiktok:
        platforms.append("tiktok")

    if platform_instagram:
        platforms.append("instagram")

    if not platforms:
        st.error(
            "Select at least one platform."
        )
        st.stop()

    if order == "Random order":
        import random
        random.shuffle(selected)

    items = []

    for index, video in enumerate(selected):

        scheduled_date = (
            start_date
            + timedelta(
                days=index * int(interval_days)
            )
        )

        scheduled_datetime = datetime.combine(
            scheduled_date,
            upload_time,
        )

        items.append({
            "id": index + 1,
            "video": str(video),
            "filename": video.name,
            "scheduled_at": scheduled_datetime.isoformat(),
            "platforms": platforms,
            "caption": video.stem,
            "tiktok_privacy": (
                tiktok_privacy
                if platform_tiktok
                else None
            ),
            "status": "scheduled",
        })

    schedule = {
        "created_at": datetime.now().isoformat(),
        "scheduler_state": "active",
        "settings": {
            "start_date": start_date.isoformat(),
            "upload_time": upload_time.strftime(
                "%H:%M"
            ),
            "interval_days": int(
                interval_days
            ),
            "order": order,
            "platforms": platforms,
        },
        "items": items,
    }

    save_schedule(schedule)

    st.success(
        f"Schedule created with "
        f"{len(items)} Shorts."
    )

    st.rerun()


# --------------------------------------------------
# Current schedule
# --------------------------------------------------

st.header("📋 Current Schedule")

schedule = load_schedule()

if schedule and schedule.get("items"):

    items = schedule["items"]

    for item in items:

        scheduled = datetime.fromisoformat(
            item["scheduled_at"]
        )

        platforms = ", ".join(
            platform.title()
            for platform in item.get(
                "platforms",
                [],
            )
        )

        status = item.get(
            "status",
            "scheduled",
        )

        if status == "scheduled":
            icon = "⏳"

        elif status == "uploaded":
            icon = "✅"

        elif status == "failed":
            icon = "❌"

        elif status == "cancelled":
            icon = "🚫"

        else:
            icon = "•"

        st.write(
            f"{icon} "
            f"**{scheduled.strftime('%d %b %Y, %I:%M %p')}** "
            f"— {item['filename']} "
            f"— {platforms} "
            f"— `{status}`"
        )

else:

    st.info(
        "No scheduled Shorts."
    )
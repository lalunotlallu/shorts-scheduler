import json
import time
from datetime import datetime
from pathlib import Path

from uploader import upload_to_tiktok


BASE_DIR = Path(r"E:\ShortsScheduler")
SCHEDULE_FILE = BASE_DIR / "schedule.json"


def load_schedule():
    if not SCHEDULE_FILE.exists():
        return None

    try:
        return json.loads(
            SCHEDULE_FILE.read_text(
                encoding="utf-8"
            )
        )
    except json.JSONDecodeError as exc:
        print(
            f"Could not read schedule.json: {exc}"
        )
        return None


def save_schedule(schedule):
    SCHEDULE_FILE.write_text(
        json.dumps(
            schedule,
            indent=2
        ),
        encoding="utf-8",
    )


def check_schedule():

    schedule = load_schedule()

    if not schedule:
        print("No active schedule.")
        return

    state = schedule.get(
        "scheduler_state",
        "active"
    )

    if state == "paused":
        print("Schedule is PAUSED.")
        return

    if state == "cancelled":
        print("Schedule is CANCELLED.")
        return

    items = schedule.get(
        "items",
        []
    )

    if not items:
        print("Schedule contains no items.")
        return

    now = datetime.now()

    print()
    print("=" * 60)
    print("SHORTS SCHEDULER")
    print("=" * 60)
    print(
        f"Current time: "
        f"{now.strftime('%Y-%m-%d %H:%M:%S')}"
    )
    print()

    due_count = 0

    for item in items:

        scheduled_at = datetime.fromisoformat(
            item["scheduled_at"]
        )

        filename = item.get(
            "filename",
            "Unknown"
        )

        status = item.get(
            "status",
            "scheduled"
        )

        platforms = item.get(
            "platforms",
            []
        )

        if status == "uploaded":
            state_text = "UPLOADED"

        elif status == "failed":
            state_text = "FAILED"

        elif status == "cancelled":
            state_text = "CANCELLED"

        elif scheduled_at > now:
            state_text = "WAITING"

        else:

            due_count += 1

            video_path = Path(
                item["video"]
            )

            if not video_path.exists():

                print(
                    f"ERROR: Video not found: "
                    f"{video_path}"
                )

                item["status"] = "failed"
                state_text = "FAILED"

            elif "tiktok" in platforms:

                print()
                print(
                    f"Uploading to TikTok: "
                    f"{filename}"
                )

                success = upload_to_tiktok(
                    video_path,
                    item.get("caption", ""),
                    item.get("tiktok_privacy"),
                )

                if success:
                    item["status"] = "uploaded"
                    item["uploaded_at"] = datetime.now().isoformat()
                    state_text = "UPLOADED"

                else:
                    item["status"] = "failed"
                    state_text = "FAILED"

            else:

                print(
                    f"No uploader configured "
                    f"for: "
                    f"{', '.join(platforms)}"
                )

                item["status"] = "failed"
                state_text = "FAILED"

        print(
            f"[{state_text:9}] "
            f"{scheduled_at.strftime('%d %b %Y %H:%M')}  "
            f"{filename}  "
            f"({', '.join(platforms)})"
        )

    save_schedule(schedule)

    print()
    print(
        f"Due items: {due_count}"
    )
    print("=" * 60)


if __name__ == "__main__":

    print(
        "Starting Shorts Scheduler..."
    )

    print(
        "Press Ctrl+C to stop."
    )

    print()

    while True:

        try:

            check_schedule()

            time.sleep(60)

        except KeyboardInterrupt:

            print(
                "\nScheduler stopped."
            )

            break

        except Exception as exc:

            print(
                f"Scheduler error: {exc}"
            )

            time.sleep(60)
"""Set the semantic model's scheduled refresh (Step 10e): daily at 06:00 Central, email on failure.

Same as Service > semantic model > Settings > Refresh > "Configure a refresh schedule".
A refresh copies Databricks -> Power BI; it does not re-read the Excel file
(run tools/load_to_databricks.py for that).

Run from the project root:
    python3 -I tools/set_refresh_schedule.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fabric  # noqa: E402

SCHEDULE = {
    "enabled": True,
    "days": ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
    "times": ["06:00"],
    "localTimeZoneId": "Central Standard Time",   # Windows time zone ID; follows daylight saving time
    "notifyOption": "MailOnFailure",
}

ROOT = Path(__file__).resolve().parent.parent
env = dict(line.split("=", 1) for line in (ROOT / "tools" / ".published.env").read_text().split())
url = fabric.dataset_url(env["SEMANTIC_MODEL_ID"]) + "/refreshSchedule"

fabric.call("PATCH", url, {"value": SCHEDULE})
_, _, current = fabric.call("GET", url)
print("Refresh schedule now:")
for key in ("enabled", "days", "times", "localTimeZoneId", "notifyOption"):
    print(f"  {key:<16} {current.get(key)}")

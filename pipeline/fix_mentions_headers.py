#!/usr/bin/env python3
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MENTIONS_DIR = ROOT / "gdelt_raw" / "mentions"


def infer_header() -> list[str]:
    """Return the header that matches the actual field order in these mentions rows."""
    return [
        "GlobalEventID",
        "MentionType",
        "MentionSourceName",
        "MentionIdentifier",
        "SentenceID",
        "Actor1CharOffset",
        "Actor2CharOffset",
        "ActionCharOffset",
        "InRawText",
        "Confidence",
        "MentionDocLen",
        "MentionDocTone",
        "Extra1",
        "Extra2",
    ]


def fix_file(path: Path) -> bool:
    with path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))

    if not rows:
        return False

    header = infer_header()
    old_header = [
        "GlobalEventID",
        "EventTimeDate",
        "MentionTimeDate",
        "MentionType",
        "MentionSourceName",
        "MentionIdentifier",
        "SentenceID",
        "Actor1CharOffset",
        "Actor2CharOffset",
        "ActionCharOffset",
        "InRawText",
        "Confidence",
        "MentionDocLen",
        "MentionDocTone",
    ]

    if rows[0] == header:
        cleaned = [header] + [row for row in rows[1:] if row != old_header]
    elif rows[0] == old_header:
        cleaned = [header] + [row for row in rows[1:] if row != old_header]
    else:
        cleaned = rows

    if cleaned != rows:
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(cleaned)
        return True
    return False


def main() -> None:
    files = sorted(MENTIONS_DIR.rglob("*.csv"))
    updated = 0
    for path in files:
        if fix_file(path):
            updated += 1
            print(f"updated {path}")
    print(f"Processed {len(files)} files; updated {updated}.")


if __name__ == "__main__":
    main()

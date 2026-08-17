import io
import sys
import time
import zipfile
from pathlib import Path

import pandas as pd
import requests

# ── CONFIG ─────────────────────────────────────────────────────────────────────
START_DATE = "20260701"   # YYYYMMDD
END_DATE   = "20260805"   # YYYYMMDD

DATA_DIR   = Path("gdelt_raw")

# 4 evenly-spaced samples per day (UTC): midnight, 6am, noon, 6pm
SAMPLE_HOURS = {"000000", "060000", "120000", "180000"}

# Set False to disable either file type
DOWNLOAD_EVENTS   = False
DOWNLOAD_MENTIONS = True   # needed for link prediction ground truth

# Filter events to conflict/terrorism only (saves space; mentions are NOT filtered
# since you need ALL mentions for a conflict event, regardless of mention tone)
CONFLICT_ONLY = True
CONFLICT_ROOT_CODES = {"14", "15", "16", "17", "18", "19", "20"}

DELAY_SECS = 0.5
MASTER_URL = "http://data.gdeltproject.org/gdeltv2/masterfilelist.txt"

# ── COLUMN DEFINITIONS ─────────────────────────────────────────────────────────

EVENT_COLS = [
    "GlobalEventID", "Day", "MonthYear", "Year", "FractionDate",
    "Actor1Code", "Actor1Name", "Actor1CountryCode", "Actor1KnownGroupCode",
    "Actor1EthnicCode", "Actor1Religion1Code", "Actor1Religion2Code",
    "Actor1Type1Code", "Actor1Type2Code", "Actor1Type3Code",
    "Actor2Code", "Actor2Name", "Actor2CountryCode", "Actor2KnownGroupCode",
    "Actor2EthnicCode", "Actor2Religion1Code", "Actor2Religion2Code",
    "Actor2Type1Code", "Actor2Type2Code", "Actor2Type3Code",
    "IsRootEvent", "EventCode", "EventBaseCode", "EventRootCode",
    "QuadClass", "GoldsteinScale", "NumMentions", "NumSources",
    "NumArticles", "AvgTone",
    "Actor1Geo_Type", "Actor1Geo_FullName", "Actor1Geo_CountryCode",
    "Actor1Geo_ADM1Code", "Actor1Geo_ADM2Code",
    "Actor1Geo_Lat", "Actor1Geo_Long", "Actor1Geo_FeatureID",
    "Actor2Geo_Type", "Actor2Geo_FullName", "Actor2Geo_CountryCode",
    "Actor2Geo_ADM1Code", "Actor2Geo_ADM2Code",
    "Actor2Geo_Lat", "Actor2Geo_Long", "Actor2Geo_FeatureID",
    "ActionGeo_Type", "ActionGeo_FullName", "ActionGeo_CountryCode",
    "ActionGeo_ADM1Code", "ActionGeo_ADM2Code",
    "ActionGeo_Lat", "ActionGeo_Long", "ActionGeo_FeatureID",
    "DATEADDED", "SOURCEURL",
]


MENTION_COLS = [
    "GlobalEventID",
    "EventTimeDate",              # when the event occurred (YYYYMMDDHHMMSS)
    "MentionTimeDate",            # when the article was published (YYYYMMDDHHMMSS)
    "MentionType",                # 1=WEB 2=CITATIONONLY 3=CORE 4=DOCCAS
    "MentionSourceName",
    "MentionIdentifier",          # article URL
    "SentenceID",
    "Actor1CharOffset",
    "Actor2CharOffset",
    "ActionCharOffset",
    "InRawText",
    "Confidence",
    "MentionDocLen",
    "MentionDocTone",
    "MentionDocTranslationInfo",
    "Extras",                     # single field, usually empty, reserved
]


# ── HELPERS ────────────────────────────────────────────────────────────────────

def fetch_master_list() -> list[str]:
    """Fetch master list for getting the list of event and mentions file."""
    print("Fetching master file list (may take ~30 seconds)...")
    r = requests.get(MASTER_URL, timeout=120)
    r.raise_for_status()
    return r.text.strip().splitlines()


def filter_urls(lines: list[str]) -> dict[str, list[str]]:
    """
    Return two sorted URL lists: one for events, one for mentions.
    Both filtered to the date range and sampled hours.
    """
    events, mentions = [], []
    for line in lines:
        parts = line.split()
        if len(parts) < 3:
            continue
        url       = parts[2]
        fname     = url.split("/")[-1]
        file_date = fname[:8]
        file_time = fname[8:14]

        if file_date < START_DATE or file_date > END_DATE:
            continue
        if file_time not in SAMPLE_HOURS:
            continue

        if url.endswith(".export.CSV.zip"):
            events.append(url)
        elif url.endswith(".mentions.CSV.zip"):
            mentions.append(url)

    return {"events": sorted(events), "mentions": sorted(mentions)}


def download_zip(url: str, retries: int = 3) -> str:
    """Download a zip, return the inner CSV as a string."""
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                return z.read(z.namelist()[0]).decode("utf-8", errors="replace")
        except Exception as exc:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise exc


def parse_events(csv_text: str) -> pd.DataFrame:
    df = pd.read_csv(
        io.StringIO(csv_text), sep="\t", header=None,
        names=EVENT_COLS, dtype=str, low_memory=False,
    )
    if CONFLICT_ONLY:
        df = df[df["EventRootCode"].isin(CONFLICT_ROOT_CODES)]
    return df


def parse_mentions(csv_text: str) -> pd.DataFrame:
    """Parse Mentions file and return its dataframe"""
    return pd.read_csv(
        io.StringIO(csv_text), sep="\t", header=None,
        names=MENTION_COLS, dtype=str, low_memory=False,
    )


def process_batch(urls: list[str], file_type: str,
                  parse_fn, out_dir: Path,
                  suffix_strip: str) -> tuple[int, int, int]:
    """Download, parse, and save a batch of files. Returns (downloaded, skipped, failed)."""
    downloaded, skipped, failed = 0, 0, 0
    total = len(urls)

    for i, url in enumerate(urls, 1):
        raw_name  = url.split("/")[-1]
        csv_name  = raw_name.replace(suffix_strip, ".csv")
        date_part = csv_name[:8]
        year_dir  = out_dir / date_part[:4]
        year_dir.mkdir(parents=True, exist_ok=True)
        dest   = year_dir / csv_name
        prefix = f"[{file_type}  {i:>5}/{total}]"

        if dest.exists():
            skipped += 1
            print(f"{prefix}  –  {csv_name}  (already exists)")
            continue

        try:
            csv_text = download_zip(url)
            df       = parse_fn(csv_text)
            df.to_csv(dest, index=False, header=True)
            downloaded += 1
            print(f"{prefix}  ✓  {csv_name}  ({len(df):,} rows)")
        except Exception as exc:
            failed += 1
            print(f"{prefix}  ✗  {csv_name}  — {exc}")

        time.sleep(DELAY_SECS)

    return downloaded, skipped, failed


# ── MAIN ───────────────────────────────────────────────────────────────────────

def main():
    lines    = fetch_master_list()
    url_sets = filter_urls(lines)

    ev_count = len(url_sets["events"])   if DOWNLOAD_EVENTS   else 0
    mn_count = len(url_sets["mentions"]) if DOWNLOAD_MENTIONS else 0

    print(f"""
=====================================================
 GDELT v2 Download Plan
 Date range    : {START_DATE} → {END_DATE}
 Samples/day   : {len(SAMPLE_HOURS)}  ({', '.join(sorted(SAMPLE_HOURS))})
 Events files  : {ev_count}  {'(conflict-filtered)' if CONFLICT_ONLY else '(all)'}
 Mentions files: {mn_count}  (used for link prediction ground truth)
 Output        : {DATA_DIR.resolve()}
=====================================================
""")

    totals = {"downloaded": 0, "skipped": 0, "failed": 0}

    if DOWNLOAD_EVENTS and url_sets["events"]:
        print("── Downloading Events ──────────────────────────────")
        d, s, f = process_batch(
            urls        = url_sets["events"],
            file_type   = "events  ",
            parse_fn    = parse_events,
            out_dir     = DATA_DIR / "events",
            suffix_strip= ".export.CSV.zip",
        )
        totals["downloaded"] += d
        totals["skipped"]    += s
        totals["failed"]     += f

    if DOWNLOAD_MENTIONS and url_sets["mentions"]:
        print("\n── Downloading Mentions ────────────────────────────")
        d, s, f = process_batch(
            urls        = url_sets["mentions"],
            file_type   = "mentions",
            parse_fn    = parse_mentions,
            out_dir     = DATA_DIR / "mentions",
            suffix_strip= ".mentions.CSV.zip",
        )
        totals["downloaded"] += d
        totals["skipped"]    += s
        totals["failed"]     += f

    print(f"""
=====================================================
 Done.
 Downloaded : {totals['downloaded']}
 Skipped    : {totals['skipped']}  (already on disk)
 Failed     : {totals['failed']}
=====================================================

Directory layout:
  gdelt_raw/
    events/
      2024/  20240601000000.csv ...
      2025/  ...
      2026/  ...
    mentions/
      2024/  20240601000000.csv ...
      2025/  ...
      2026/  ...

Next step: ingestion pipeline reads events/ and mentions/
together to build the FalkorDB graph and implicit link pairs.
""")


if __name__ == "__main__":
    main()

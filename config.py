import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 6379))
GRAPH_NAME = os.getenv("GRAPH_NAME", "Geopolitics")
DATA_DIR = Path("DATA_DIR", "data/gdelt_raw")

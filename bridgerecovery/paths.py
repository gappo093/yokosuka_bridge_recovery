from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
RAW_DIR = DATA_DIR / "raw"
SCENARIO_DIR = DATA_DIR / "scenario"
RESULTS_DIR = ROOT / "results"

GRAPH_PATH = RAW_DIR / "yokosuka_drive.graphml"
HUBS_PATH = RAW_DIR / "hubs.csv"
BRIDGES_ALL_PATH = RAW_DIR / "bridges_all.csv"
SCENARIO_PATH = SCENARIO_DIR / "scenario.json"
DAMAGED_CSV_PATH = SCENARIO_DIR / "damaged_bridges.csv"

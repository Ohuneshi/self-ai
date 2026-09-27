"""Legacy JSON memory import helper."""
from pathlib import Path
import json
root=Path(__file__).resolve().parents[1]
for p in sorted((root/"seed_memory").glob("*.json")):
    print(p.name, json.loads(p.read_text(encoding="utf-8")))

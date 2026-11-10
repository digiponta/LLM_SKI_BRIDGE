"""Run from repo root: python experiments/evidence_roundtrip.py."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.llm_cha_mock import roundtrip


if __name__ == "__main__":
    for target in ("SD-EVIDENCE", "SD-PENDING", "MISSING"):
        result = roundtrip(target_sd=target)
        print(json.dumps(result, ensure_ascii=False, indent=2))

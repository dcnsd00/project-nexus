from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .analysis import analyze
from .collector import MempoolClient


def _write_json(path: str, payload: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="NEXUS RCSC: read-only Bitcoin block research")
    parser.add_argument("--count", type=int, default=10, help="number of recent blocks to collect (1..5000)")
    parser.add_argument("--start-height", type=int, default=None, help="latest height if omitted")
    parser.add_argument("--out", default="data/blocks.json", help="raw normalized block dataset path")
    parser.add_argument("--analysis-out", default="results/analysis.json", help="analysis report path")
    parser.add_argument("--pause", type=float, default=0.15, help="pause between per-block API requests")
    args = parser.parse_args()

    client = MempoolClient(pause_seconds=args.pause)
    records = client.fetch_recent(count=args.count, start_height=args.start_height)
    report = analyze(records)
    _write_json(args.out, {
        "dataset_schema_version": "0.1.0",
        "source": "Mempool.space public REST API",
        "records": records,
    })
    _write_json(args.analysis_out, report)
    print(json.dumps({
        "dataset_path": args.out,
        "analysis_path": args.analysis_out,
        "blocks_requested": args.count,
        "blocks_collected": len(records),
        "verified_header_and_pow": report["header_and_pow_verified_count"],
        "records_with_errors": report["records_with_errors"],
    }, indent=2))


if __name__ == "__main__":
    main()

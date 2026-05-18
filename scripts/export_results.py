#!/usr/bin/env python3
"""Export longterm companion experiment logs into analysis-friendly files."""

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOG_DIR = ROOT / "storage" / "logs"
DEFAULT_OUTPUT_DIR = ROOT / "storage" / "exports"

SESSION_RATING_FIELDS = [
    "felt_understood",
    "natural_empathy",
    "matched_current_need",
    "low_template_feeling",
    "natural_history_usage",
    "willing_to_continue",
    "non_preachy",
    "overall_supportiveness",
]

SESSION_FREE_TEXT_FIELDS = [
    "best_moment",
    "worst_moment",
    "one_sentence_impression",
]

EPISODE_RATING_FIELDS = [
    "continuity_across_sessions",
    "emotional_stability",
    "trust",
    "repair_ability",
    "overall_companionship_quality",
]

EPISODE_FREE_TEXT_FIELDS = [
    "summary_impression",
    "main_strength",
    "main_weakness",
]


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def write_csv(path: Path, fieldnames: List[str], rows: Iterable[Dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
            count += 1
    return count


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


def compact_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.replace("\r\n", "\n").strip()
    return json.dumps(value, ensure_ascii=False)


def conversation_to_text(conversation: List[Dict[str, Any]]) -> str:
    lines = []
    for item in conversation:
        role = "User" if item.get("role") == "user" else "Assistant"
        content = compact_text(item.get("content", ""))
        turn_index = item.get("turn_index", "")
        prefix = f"Turn {turn_index} {role}" if turn_index != "" else role
        lines.append(f"{prefix}: {content}")
    return "\n\n".join(lines)


def session_log_to_row(path: Path, payload: Dict[str, Any]) -> Dict[str, Any]:
    conversation = payload.get("conversation") or []
    user_turns = sum(1 for item in conversation if item.get("role") == "user")
    return {
        "source_file": str(path),
        "tester_id": payload.get("tester_id", ""),
        "episode_id": payload.get("episode_id", ""),
        "session_id": payload.get("session_id", ""),
        "part_type": payload.get("part_type", ""),
        "model_blind_id": payload.get("model_blind_id", ""),
        "started_at": payload.get("started_at", ""),
        "ended_at": payload.get("ended_at", ""),
        "max_turns": payload.get("max_turns", ""),
        "turn_count": user_turns,
        "message_count": len(conversation),
        "history_summary_rendered": compact_text(payload.get("history_summary_rendered", "")),
        "conversation_text": conversation_to_text(conversation),
    }


def session_rating_to_row(path: Path, payload: Dict[str, Any]) -> Dict[str, Any]:
    row = {
        "source_file": str(path),
        "tester_id": payload.get("tester_id", ""),
        "episode_id": payload.get("episode_id", ""),
        "session_id": payload.get("session_id", ""),
        "part_type": payload.get("part_type", ""),
        "model_blind_id": payload.get("model_blind_id", ""),
    }
    ratings = payload.get("ratings") or {}
    for field in SESSION_RATING_FIELDS:
        row[field] = ratings.get(field, "")
    free_text = payload.get("free_text") or {}
    for field in SESSION_FREE_TEXT_FIELDS:
        row[field] = compact_text(free_text.get(field, ""))
    return row


def episode_rating_is_filled(payload: Dict[str, Any]) -> bool:
    ratings = payload.get("ratings") or {}
    free_text = payload.get("free_text") or {}
    preference = payload.get("paired_preference") or {}
    return any(value is not None for value in ratings.values()) or any(
        compact_text(value) for value in free_text.values()
    ) or any(compact_text(value) for value in preference.values())


def episode_rating_to_row(path: Path, payload: Dict[str, Any]) -> Dict[str, Any]:
    row = {
        "source_file": str(path),
        "tester_id": payload.get("tester_id", ""),
        "episode_id": payload.get("episode_id", ""),
        "part_type": payload.get("part_type", ""),
        "model_blind_id": payload.get("model_blind_id", ""),
    }
    ratings = payload.get("ratings") or {}
    for field in EPISODE_RATING_FIELDS:
        row[field] = ratings.get(field, "")
    free_text = payload.get("free_text") or {}
    for field in EPISODE_FREE_TEXT_FIELDS:
        row[field] = compact_text(free_text.get(field, ""))
    preference = payload.get("paired_preference") or {}
    row["preferred_model_blind_id"] = preference.get("preferred_model_blind_id", "")
    row["preference_reason"] = compact_text(preference.get("reason", ""))
    return row


def collect_session_logs(log_dir: Path) -> List[Dict[str, Any]]:
    rows = []
    for path in sorted(log_dir.rglob("session_log.json")):
        rows.append(session_log_to_row(path, load_json(path)))
    return rows


def collect_session_ratings(log_dir: Path) -> List[Dict[str, Any]]:
    rows = []
    for path in sorted(log_dir.rglob("session_rating.json")):
        rows.append(session_rating_to_row(path, load_json(path)))
    return rows


def collect_episode_ratings(log_dir: Path) -> List[Dict[str, Any]]:
    rows = []
    seen = set()
    for path in sorted(log_dir.rglob("episode_rating*.json")):
        payload = load_json(path)
        if path.name == "episode_rating.json" and not episode_rating_is_filled(payload):
            continue
        key = (
            payload.get("tester_id", ""),
            payload.get("episode_id", ""),
            payload.get("model_blind_id", ""),
            str(path),
        )
        if key in seen:
            continue
        seen.add(key)
        rows.append(episode_rating_to_row(path, payload))
    return rows


def export_results(log_dir: Path, output_dir: Path) -> Dict[str, int]:
    log_dir = log_dir.resolve()
    output_dir = output_dir.resolve()

    session_rating_rows = collect_session_ratings(log_dir)
    episode_rating_rows = collect_episode_ratings(log_dir)
    session_log_rows = collect_session_logs(log_dir)
    session_log_payloads = [
        {"source_file": str(path), **load_json(path)}
        for path in sorted(log_dir.rglob("session_log.json"))
    ]

    counts = {
        "all_session_ratings.csv": write_csv(
            output_dir / "all_session_ratings.csv",
            [
                "source_file",
                "tester_id",
                "episode_id",
                "session_id",
                "part_type",
                "model_blind_id",
                *SESSION_RATING_FIELDS,
                *SESSION_FREE_TEXT_FIELDS,
            ],
            session_rating_rows,
        ),
        "all_episode_ratings.csv": write_csv(
            output_dir / "all_episode_ratings.csv",
            [
                "source_file",
                "tester_id",
                "episode_id",
                "part_type",
                "model_blind_id",
                *EPISODE_RATING_FIELDS,
                *EPISODE_FREE_TEXT_FIELDS,
                "preferred_model_blind_id",
                "preference_reason",
            ],
            episode_rating_rows,
        ),
        "all_session_logs.csv": write_csv(
            output_dir / "all_session_logs.csv",
            [
                "source_file",
                "tester_id",
                "episode_id",
                "session_id",
                "part_type",
                "model_blind_id",
                "started_at",
                "ended_at",
                "max_turns",
                "turn_count",
                "message_count",
                "history_summary_rendered",
                "conversation_text",
            ],
            session_log_rows,
        ),
        "all_session_logs.jsonl": write_jsonl(
            output_dir / "all_session_logs.jsonl",
            session_log_payloads,
        ),
    }
    return counts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export longterm companion experiment logs into CSV and JSONL files."
    )
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    counts = export_results(args.log_dir, args.output_dir)
    print(f"Log dir: {args.log_dir.resolve()}")
    print(f"Output dir: {args.output_dir.resolve()}")
    for filename, count in counts.items():
        print(f"Wrote {filename}: {count} rows")


if __name__ == "__main__":
    main()

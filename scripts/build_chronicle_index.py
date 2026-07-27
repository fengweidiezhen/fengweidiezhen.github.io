#!/usr/bin/env python3
"""
从 Chronicle 本地数据目录生成 search-index.json，供静态搜索页使用。
数据格式见项目根目录 格式.md。

用法:
  python scripts/build_chronicle_index.py
  python scripts/build_chronicle_index.py --root database/ch7k2m9p4
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

SHANGHAI = timezone(timedelta(hours=8))
INDEX_VERSION = 1


def load_json(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def user_lookup(id_list: list) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for u in id_list:
        uid = u.get("id")
        if not uid:
            continue
        out[uid] = u
    return out


def display_name(user: dict | None, fallback: str = "") -> str:
    if not user:
        return fallback
    return user.get("display_name") or user.get("name") or fallback


def index_records(records_dir: Path, root: Path, users: dict[str, dict]) -> list[dict]:
    entries: list[dict] = []
    if not records_dir.is_dir():
        return entries

    for user_dir in sorted(records_dir.iterdir()):
        if not user_dir.is_dir():
            continue
        user_id = user_dir.name
        user = users.get(user_id, {})
        user_name = display_name(user, user_id)

        for day_file in sorted(user_dir.glob("*.json")):
            rel = day_file.relative_to(root).as_posix()
            try:
                doc = load_json(day_file)
            except (json.JSONDecodeError, OSError) as e:
                print(f"skip {day_file}: {e}", file=sys.stderr)
                continue

            date = doc.get("date") or day_file.stem
            for i, item in enumerate(doc.get("items") or []):
                speaker = item.get("speaker", "")
                text = (item.get("text") or "").strip()
                if not text or speaker == "marker":
                    continue
                entries.append(
                    {
                        "id": f"rec:{user_id}:{date}:{i}",
                        "type": "record",
                        "user_id": user_id,
                        "user_name": user_name,
                        "date": date,
                        "speaker": speaker,
                        "timestamp": item.get("timestamp", ""),
                        "text": text,
                        "snippet": text[:240],
                        "path": rel,
                        "item_index": i,
                    }
                )
    return entries


def _join_parts(*parts: str) -> str:
    return " ".join(p.strip() for p in parts if p and p.strip())


def index_summaries(summaries_dir: Path, root: Path, users: dict[str, dict]) -> list[dict]:
    entries: list[dict] = []
    if not summaries_dir.is_dir():
        return entries

    for user_dir in sorted(summaries_dir.iterdir()):
        if not user_dir.is_dir():
            continue
        user_id = user_dir.name
        user = users.get(user_id, {})
        user_name = display_name(user, user_id)

        for day_file in sorted(user_dir.glob("*.json")):
            rel = day_file.relative_to(root).as_posix()
            try:
                doc = load_json(day_file)
            except (json.JSONDecodeError, OSError) as e:
                print(f"skip {day_file}: {e}", file=sys.stderr)
                continue

            date = doc.get("date") or day_file.stem
            name = doc.get("user_name") or user_name
            summary = doc.get("summary") or {}
            base = {
                "user_id": user_id,
                "user_name": name,
                "date": date,
                "path": rel,
            }

            if title := (summary.get("title") or "").strip():
                entries.append(
                    {
                        **base,
                        "id": f"sum:{user_id}:{date}:title",
                        "type": "summary",
                        "category": "title",
                        "text": title,
                        "snippet": title,
                    }
                )

            if overview := (summary.get("overview") or "").strip():
                entries.append(
                    {
                        **base,
                        "id": f"sum:{user_id}:{date}:overview",
                        "type": "summary",
                        "category": "overview",
                        "text": overview,
                        "snippet": overview[:240],
                    }
                )

            for ki, kw in enumerate(summary.get("keywords") or []):
                kw = (kw or "").strip()
                if not kw:
                    continue
                entries.append(
                    {
                        **base,
                        "id": f"sum:{user_id}:{date}:kw:{ki}",
                        "type": "summary",
                        "category": "keyword",
                        "text": kw,
                        "snippet": kw,
                    }
                )

            for ei, ev in enumerate(summary.get("events") or []):
                text = _join_parts(
                    ev.get("time", ""),
                    ev.get("what_happened", ""),
                    ev.get("outcome", ""),
                )
                if not text:
                    continue
                entries.append(
                    {
                        **base,
                        "id": f"sum:{user_id}:{date}:ev:{ei}",
                        "type": "summary",
                        "category": "event",
                        "text": text,
                        "snippet": text[:240],
                        "timestamp": ev.get("time", ""),
                    }
                )

            for di, disc in enumerate(summary.get("discussions") or []):
                text = _join_parts(
                    disc.get("topic", ""),
                    disc.get("summary", ""),
                    ", ".join(disc.get("participants_mentioned") or []),
                    "; ".join(disc.get("decisions_or_todos") or []),
                )
                if not text:
                    continue
                entries.append(
                    {
                        **base,
                        "id": f"sum:{user_id}:{date}:disc:{di}",
                        "type": "summary",
                        "category": "discussion",
                        "text": text,
                        "snippet": text[:240],
                    }
                )

            for section, key in (
                ("company", "plans_and_arrangements"),
                ("company", "projects_or_business"),
                ("company", "risks_or_blockers"),
            ):
                block = summary.get(section) or {}
                for ii, line in enumerate(block.get(key) or []):
                    line = (line or "").strip()
                    if not line:
                        continue
                    entries.append(
                        {
                            **base,
                            "id": f"sum:{user_id}:{date}:{section}:{key}:{ii}",
                            "type": "summary",
                            "category": key,
                            "text": line,
                            "snippet": line[:240],
                        }
                    )

            for fin in (summary.get("finance") or {}).get("items") or []:
                if isinstance(fin, str):
                    text = fin.strip()
                elif isinstance(fin, dict):
                    text = _join_parts(
                        fin.get("category", ""),
                        fin.get("detail", ""),
                        fin.get("amount_or_terms", ""),
                    )
                else:
                    continue
                if text:
                    entries.append(
                        {
                            **base,
                            "id": f"sum:{user_id}:{date}:fin:{len(entries)}",
                            "type": "summary",
                            "category": "finance",
                            "text": text,
                            "snippet": text[:240],
                        }
                    )

            for per in (summary.get("personnel") or {}).get("items") or []:
                if isinstance(per, str):
                    text = per.strip()
                elif isinstance(per, dict):
                    text = _join_parts(per.get("category", ""), per.get("detail", ""))
                else:
                    continue
                if text:
                    entries.append(
                        {
                            **base,
                            "id": f"sum:{user_id}:{date}:per:{len(entries)}",
                            "type": "summary",
                            "category": "personnel",
                            "text": text,
                            "snippet": text[:240],
                        }
                    )

            for qi, q in enumerate(summary.get("open_questions") or []):
                q = (q or "").strip()
                if not q:
                    continue
                entries.append(
                    {
                        **base,
                        "id": f"sum:{user_id}:{date}:oq:{qi}",
                        "type": "summary",
                        "category": "open_question",
                        "text": q,
                        "snippet": q[:240],
                    }
                )

    return entries


def build(root: Path) -> tuple[dict, dict[str, list[dict]]]:
    id_list_path = root / "id_list.json"
    id_list = load_json(id_list_path) if id_list_path.is_file() else []
    users = user_lookup(id_list)

    data_dir = root / "data"
    record_entries = index_records(data_dir / "records", root, users)
    summary_entries = index_summaries(data_dir / "summaries", root, users)

    entries = record_entries + summary_entries
    dates = sorted({e["date"] for e in entries if e.get("date")})

    by_user: dict[str, list[dict]] = {}
    for e in entries:
        uid = e.get("user_id")
        if not uid:
            continue
        by_user.setdefault(uid, []).append(e)

    user_meta = []
    for uid in sorted(by_user):
        user_entries = by_user[uid]
        u = users.get(uid, {})
        user_dates = sorted({e["date"] for e in user_entries if e.get("date")})
        user_meta.append(
            {
                "user_id": uid,
                "user_name": display_name(u, uid),
                "entries": len(user_entries),
                "records": sum(1 for e in user_entries if e.get("type") == "record"),
                "summaries": sum(1 for e in user_entries if e.get("type") == "summary"),
                "dates": user_dates,
            }
        )

    meta = {
        "version": INDEX_VERSION,
        "built_at": datetime.now(SHANGHAI).isoformat(timespec="seconds"),
        "stats": {
            "entries": len(entries),
            "records": len(record_entries),
            "summaries": len(summary_entries),
            "users": len(by_user),
            "dates": len(dates),
        },
        "dates": dates,
        "users": user_meta,
    }
    return meta, by_user


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Chronicle search indexes")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("database/ch7k2m9p4"),
        help="Chronicle 数据根目录（含 id_list.json 与 data/）",
    )
    parser.add_argument(
        "--legacy-monolith",
        action="store_true",
        help="同时生成完整 search-index.json（体积大，一般不需要）",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    if not root.is_dir():
        print(f"error: root not found: {root}", file=sys.stderr)
        return 1

    meta, by_user = build(root)

    meta_path = root / "search-meta.json"
    with meta_path.open("w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"wrote {meta_path}")

    shard_dir = root / "search-index"
    shard_dir.mkdir(parents=True, exist_ok=True)
    for uid, user_entries in by_user.items():
        shard_path = shard_dir / f"{uid}.json"
        with shard_path.open("w", encoding="utf-8") as f:
            json.dump({"user_id": uid, "entries": user_entries}, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"  shard {uid}: {len(user_entries)} entries")

    if args.legacy_monolith:
        all_entries = [e for es in by_user.values() for e in es]
        monolith = {**meta, "entries": all_entries}
        out = root / "search-index.json"
        with out.open("w", encoding="utf-8") as f:
            json.dump(monolith, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"wrote {out}")

    s = meta["stats"]
    print(
        f"done: entries={s['entries']} users={s['users']} dates={s['dates']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

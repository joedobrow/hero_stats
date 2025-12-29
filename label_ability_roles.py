#!/usr/bin/env python3
"""
Label Ability Roles (carry / support / both) from HS cache.

- Reads:  cache/ability_high_skill.json
- Writes: cache/ability_roles.json
  {
    "meta": {"source":"...", "cached_at":"..."},
    "labels": {
      "Fury Swipes": "carry",
      "Hex": "support",
      "Shukuchi": "both",
      ...
    }
  }

Controls:
  c = carry, s = support, b = both
  k = skip,  u = undo last,  q = save & quit,  ? = help
"""

import json
import sys
import time
import random
import shutil
from pathlib import Path
from typing import Dict, List, Tuple, Optional

CACHE_DIR = Path("cache")
HS_FILE   = CACHE_DIR / "ability_high_skill.json"
OUT_FILE  = CACHE_DIR / "ability_roles.json"
BACKUP_DIR = CACHE_DIR / "backups"

AUTOSAVE_EVERY = 10  # write file every N labels, plus on quit

def load_hs() -> Tuple[Dict, Dict[str, dict]]:
    if not HS_FILE.exists():
        raise SystemExit(f"Missing {HS_FILE}. Run the scraper first.")
    with HS_FILE.open("r", encoding="utf-8") as f:
        doc = json.load(f)
    data = doc.get("data", {})
    abilities = {}
    for name, row in data.items():
        if not isinstance(row, dict):
            continue
        # hero models: have hero_img or abilities list
        if "pick_num" in row or "hero_img" in row or "abilities" in row:
            abilities[name] = row
    return doc, abilities

def load_labels() -> Dict:
    if OUT_FILE.exists():
        with OUT_FILE.open("r", encoding="utf-8") as f:
            try:
                doc = json.load(f)
                if isinstance(doc, dict) and "labels" in doc:
                    return doc
            except Exception:
                pass
    return {"meta": {}, "labels": {}}

def save_labels(payload: Dict, do_backup: bool = True):
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT_FILE.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    tmp.replace(OUT_FILE)

    if do_backup:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d-%H%M%S", time.localtime())
        bpath = BACKUP_DIR / f"ability_roles_{ts}.json"
        shutil.copy2(OUT_FILE, bpath)

def fmt_pct(v):
    return f"{v:.2f}%" if isinstance(v, (int, float)) else "—"

def fmt_num(v):
    return f"{v:.2f}" if isinstance(v, (int, float)) else "—"

def print_header(done: int, total: int):
    print("=" * 72)
    pct = (done / total * 100.0) if total else 100.0
    print(f"Ability Role Labeler — {done}/{total} labeled ({pct:.1f}%)")
    print("Keys: [c]=carry  [s]=support  [b]=both  [k]=skip  [u]=undo  [q]=save&quit  [?]=help")
    print("=" * 72)

def print_card(name: str, row: dict, existing: Optional[str]):
    hero = row.get("hero") or "—"
    win_pct = fmt_pct(row.get("win_pct"))
    pick_num = fmt_num(row.get("pick_num"))
    img = row.get("img") or "—"
    print(f"\nAbility: {name}")
    print(f"  Hero: {hero}")
    print(f"  HS Win%: {win_pct}    HS Pick #: {pick_num}")
    print(f"  Icon: {img}")
    if existing:
        print(f"  Current label: {existing} (overwrite to change)")
    print()

def help_text():
    print("\nHelp:")
    print("  c = mark as carry")
    print("  s = mark as support")
    print("  b = mark as both (flex)")
    print("  k = skip without changing current label")
    print("  u = undo last labeled ability (revert the last change this session)")
    print("  q = save & quit")
    print()

def build_queue(abilities: Dict[str, dict], labels: Dict[str, str]) -> List[str]:
    unlabeled = [a for a in abilities.keys() if a not in labels]
    labeled   = [a for a in abilities.keys() if a in labels]
    # No shuffle for labeled ones — this keeps order deterministic
    random.seed(0xAD2025)
    random.shuffle(unlabeled)
    return unlabeled + labeled

def main():
    hs_meta, abilities = load_hs()
    payload = load_labels()
    labels = payload.setdefault("labels", {})
    payload["meta"] = {
        "source": hs_meta.get("source"),
        "hs_cached_at": hs_meta.get("cached_at"),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "roles": ["carry", "support", "both"],
    }

    queue = build_queue(abilities, labels)
    total = len(abilities)
    if total == 0:
        print("No abilities found in HS cache.")
        return

    history: List[Tuple[str, Optional[str]]] = []  # (ability, previous_label or None)
    made = 0

    idx = 0
    while idx < len(queue):
        name = queue[idx]
        row = abilities[name]
        existing = labels.get(name)

        done = len(labels)
        print_header(done, total)
        print_card(name, row, existing)

        try:
            key = input("Label [c/s/b], skip [k], undo [u], quit [q], help [?]: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            key = "q"

        if key in ("?", "h"):
            help_text()
            continue
        if key == "q":
            save_labels(payload)
            print(f"\nSaved to {OUT_FILE}. Bye!")
            return
        if key == "k" or key == "":
            idx += 1
            continue
        if key == "u":
            if history:
                last_name, prev = history.pop()
                if prev is None:
                    labels.pop(last_name, None)
                else:
                    labels[last_name] = prev
                payload["meta"]["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                print(f"Undid: {last_name} -> {prev}")
            else:
                print("Nothing to undo.")
            continue

        new_label: Optional[str] = None
        if key == "c":
            new_label = "carry"
        elif key == "s":
            new_label = "support"
        elif key == "b":
            new_label = "both"
        else:
            print("Unrecognized key. Press ? for help.")
            continue

        prev = labels.get(name)
        if prev != new_label:
            history.append((name, prev))
            labels[name] = new_label  # type: ignore[assignment]
            payload["meta"]["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            made += 1
            if made % AUTOSAVE_EVERY == 0:
                save_labels(payload, do_backup=True)
                print(f"(autosaved after {made} changes)")
        idx += 1

    # Finished the queue
    save_labels(payload)
    print(f"\nAll done. Labeled {len(labels)}/{total} abilities. Saved → {OUT_FILE}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)


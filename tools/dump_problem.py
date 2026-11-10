#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Print one or more PTA problems from ref/PTA_bank.json by label (e.g. 7-42, 6-17) or title keyword."""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANK = os.path.join(ROOT, "ref", "PTA_bank.json")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("用法: python tools/dump_problem.py 7-42 [6-17 ...]")
        return 1
    data = json.load(open(BANK, encoding="utf-8"))
    for key in sys.argv[1:]:
        hits = [p for p in data if p.get("label") == key or key in p.get("title", "")]
        if not hits:
            print(f"### 未找到: {key}\n")
            continue
        for p in hits:
            print("=" * 78)
            print(f"label={p['label']}  type={p['type']}  title={p['title']}")
            print("-" * 78)
            print(p["desc"])
            print()


if __name__ == "__main__":
    sys.exit(main())

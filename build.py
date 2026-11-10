#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 content/*.json + app/{template.html,style.css,app.js} 合成为单文件离线网页。

用法:
    python build.py
    python build.py --content content --out 计导期中复习.html
"""
import argparse
import datetime
import glob
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.abspath(__file__))
CATS = {"basic", "select", "loop", "array1", "array2", "mix"}
REQ = ["id", "cat", "title", "difficulty", "tags", "source", "desc", "samples", "hint", "solution"]


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def check_problems(problems, where):
    errors, warnings = [], []
    seen = {}
    for q in problems:
        pid = q.get("id", "<无id>")
        for k in REQ:
            if k not in q or q[k] in (None, "", []):
                errors.append(f"{where} {pid}: 缺少字段 {k}")
        if q.get("cat") not in CATS:
            errors.append(f"{where} {pid}: cat 非法 {q.get('cat')!r}")
        if not isinstance(q.get("difficulty"), int) or not 1 <= q["difficulty"] <= 5:
            errors.append(f"{where} {pid}: difficulty 非法")
        if not isinstance(q.get("samples"), list) or not q["samples"]:
            errors.append(f"{where} {pid}: 没有样例")
        for s in q.get("samples") or []:
            if not isinstance(s, dict) or not isinstance(s.get("in"), str) or not isinstance(s.get("out"), str):
                errors.append(f"{where} {pid}: 样例格式错误（需要 in/out 字符串）")
        sol = q.get("solution") or ""
        if "main" not in sol:
            errors.append(f"{where} {pid}: solution 不是完整程序")
        if re.search(r"(?<![A-Za-z_])gets\s*\(", sol) or "conio.h" in sol:
            errors.append(f"{where} {pid}: solution 使用了 gets/conio.h")
        if pid in seen:
            errors.append(f"{where} {pid}: ID 重复")
        seen[pid] = True
        if not q.get("tags"):
            warnings.append(f"{where} {pid}: 没有标签")
        if len(str(q.get("title", ""))) > 40:
            warnings.append(f"{where} {pid}: 标题过长")
    return errors, warnings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--content", default=os.path.join(ROOT, "content"))
    ap.add_argument("--out", default=os.path.join(ROOT, "计导期中复习.html"))
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.content, "*.json")))
    if not files:
        print("[FATAL] content/ 下没有 JSON 文件")
        return 2
    problems, exams, sections = [], [], []
    for f in files:
        data = load_json(f)
        name = os.path.basename(f)
        if "problems" in data:
            problems.extend(data["problems"])
        elif "exams" in data:
            exams.extend(data["exams"])
        elif "sections" in data:
            sections = data["sections"]
        else:
            print(f"[FATAL] {name}: 顶层缺少 problems/exams/sections")
            return 2

    errors, warnings = check_problems(problems, "题库")
    exam_problems = []
    for e in exams:
        eid = e.get("id", "<无id>")
        ps = e.get("problems") or []
        if len(ps) != 5:
            errors.append(f"卷 {eid}: 必须正好 5 题，当前 {len(ps)}")
        for i, q in enumerate(ps, 1):
            q["_exam"] = eid
            q["_examTitle"] = e.get("title", eid)
        ee, ww = check_problems(ps, f"卷{eid}")
        errors.extend(ee)
        warnings.extend(ww)
        exam_problems.extend(ps)
        if not isinstance(e.get("duration"), int):
            errors.append(f"卷 {eid}: duration 必须是整数")
        if not e.get("title"):
            errors.append(f"卷 {eid}: 缺少 title")
    if len(exams) != 6:
        warnings.append(f"模拟卷数量为 {len(exams)}（预期 6）")

    allp = problems + exam_problems
    ids = {}
    for q in allp:
        ids.setdefault(q.get("id"), 0)
        ids[q["id"]] += 1
    for pid, n in ids.items():
        if n > 1:
            errors.append(f"题目 ID 重复：{pid}（{n} 次）")

    for s in sections:
        if not s.get("title") or not s.get("body"):
            errors.append("速查手册：每节必须有 title 与 body")
    if not sections:
        warnings.append("速查手册为空")

    # 统计
    by_cat = {}
    for q in problems:
        by_cat[q["cat"]] = by_cat.get(q["cat"], 0) + 1
    if errors:
        print(f"[FATAL] 数据校验失败（{len(errors)} 个错误）：")
        for e in errors[:100]:
            print("  -", e)
        return 1
    for w in warnings:
        print("[WARN]", w)

    built = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    payload = {
        "meta": {
            "builtAt": built,
            "counts": {"problems": len(problems), "exams": len(exams),
                       "examProblems": len(exam_problems), "byCat": by_cat},
        },
        "problems": problems,
        "exams": exams,
        "cheatsheet": {"sections": sections},
    }
    data_js = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    template = open(os.path.join(ROOT, "app", "template.html"), encoding="utf-8").read()
    css = open(os.path.join(ROOT, "app", "style.css"), encoding="utf-8").read()
    js = open(os.path.join(ROOT, "app", "app.js"), encoding="utf-8").read()
    html = (template.replace("%%CSS%%", css)
                    .replace("%%JS%%", js)
                    .replace("%%DATA%%", data_js)
                    .replace("%%BUILT%%", built))
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    size = os.path.getsize(args.out) / 1024
    print(f"[OK] 已生成 {args.out}  ({size:.0f} KB)")
    print(f"     精选题 {len(problems)} 道 / 模拟卷 {len(exams)} 套 / 卷内题 {len(exam_problems)} 道 / 速查 {len(sections)} 节")
    print("     分类:", {k: by_cat.get(k, 0) for k in ["basic", "select", "loop", "array1", "array2", "mix"]})
    return 0


if __name__ == "__main__":
    sys.exit(main())

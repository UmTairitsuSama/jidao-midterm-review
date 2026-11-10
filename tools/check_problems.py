#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate problem JSON files, compile solutions with gcc, run samples and compare output.

Usage:
    python tools/check_problems.py content/01_basic_select.json [more.json ...]
    python tools/check_problems.py --all
    python tools/check_problems.py --schema-only content/04_array2.json
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GCC = os.environ.get("GCC", "gcc")
CATS = {"basic", "select", "loop", "array1", "array2", "mix"}
REQUIRED = ["id", "cat", "title", "difficulty", "tags", "source", "desc",
            "samples", "hint", "solution"]
COMPILE_TIMEOUT = 60
RUN_TIMEOUT = 10


def norm(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.rstrip() for ln in text.split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def collect(paths):
    problems = []
    for p in paths:
        try:
            data = json.load(open(p, encoding="utf-8"))
        except Exception as e:
            print(f"[FATAL] {p}: 无法解析 JSON: {e}")
            raise SystemExit(2)
        if isinstance(data, dict) and "problems" in data:
            for q in data["problems"]:
                q["_file"] = p
                problems.append(q)
        if isinstance(data, dict) and "exams" in data:
            for e in data["exams"]:
                for q in e.get("problems", []):
                    q["_file"] = p
                    q["_exam"] = e.get("id")
                    problems.append(q)
        if isinstance(data, dict) and "sections" in data:
            print(f"[INFO] {p}: 速查手册 {len(data['sections'])} 节，跳过题目校验")
        if not isinstance(data, dict) or not ({"problems", "exams", "sections"} & set(data)):
            print(f"[FATAL] {p}: 顶层缺少 problems/exams/sections")
            raise SystemExit(2)
    return problems


def validate(problems):
    errors = []
    seen = {}
    for q in problems:
        where = f"{q.get('_file','?')} / {q.get('id','<无id>')}"
        for k in REQUIRED:
            if k not in q or q[k] in (None, "", []):
                errors.append(f"{where}: 缺少字段 {k}")
        if q.get("cat") not in CATS:
            errors.append(f"{where}: cat 非法: {q.get('cat')!r}")
        if not isinstance(q.get("difficulty"), int) or not 1 <= q["difficulty"] <= 5:
            errors.append(f"{where}: difficulty 必须是 1..5 的整数")
        if not isinstance(q.get("tags"), list) or not 1 <= len(q["tags"]) <= 6:
            errors.append(f"{where}: tags 必须是 1..6 个字符串的数组")
        for s in q.get("samples") or []:
            if not isinstance(s, dict) or "in" not in s or "out" not in s:
                errors.append(f"{where}: samples 每项必须有 in/out")
        sol = q.get("solution") or ""
        if "main" not in sol:
            errors.append(f"{where}: solution 必须是完整程序（含 main）")
        if re.search(r"#include\s*<conio\.h>", sol) or re.search(r"\bgets\s*\(", sol):
            errors.append(f"{where}: solution 不能使用 conio.h / gets")
        dest = q.get("_exam") and f"{q.get('_exam')}-{q.get('id')}" or q.get("id")
        if q.get("id") in seen:
            errors.append(f"{where}: ID 重复（另见 {seen[q['id']]}）")
        seen[q.get("id")] = where
    if errors:
        print(f"\n[SCHEMA] {len(errors)} 个结构错误：")
        for e in errors[:200]:
            print("  -", e)
    else:
        print(f"[SCHEMA] OK: {len(problems)} 题结构校验通过")
    return errors


def compile_solution(workdir, q):
    src = os.path.join(workdir, "main.c")
    exe = os.path.join(workdir, "main.exe")
    open(src, "w", encoding="utf-8").write(q["solution"])
    try:
        r = subprocess.run([GCC, "-std=c11", "-O2", "-o", exe, src],
                           capture_output=True, timeout=COMPILE_TIMEOUT)
    except subprocess.TimeoutExpired:
        return None, "编译超时"
    if r.returncode != 0:
        return None, r.stderr.decode("utf-8", "replace")[:1500]
    return exe, None


def run_case(exe, workdir, sample):
    try:
        r = subprocess.run([exe], input=sample["in"].encode("utf-8"),
                           capture_output=True, timeout=RUN_TIMEOUT, cwd=workdir)
    except subprocess.TimeoutExpired:
        return None, "运行超时"
    out = r.stdout.decode("utf-8", "replace")
    err = r.stderr.decode("utf-8", "replace")
    return out, err


def check(problems):
    fails = 0
    total_cases = 0
    for i, q in enumerate(problems, 1):
        tag = f"{q.get('id','?')} {q.get('title','')[:22]}"
        tmp = tempfile.mkdtemp(prefix="chk_")
        try:
            exe, err = compile_solution(tmp, q)
            if exe is None:
                fails += 1
                print(f"[FAIL] {tag} 编译失败")
                print("       " + (err or "").replace("\n", "\n       ")[:1200])
                continue
            bad = []
            for j, s in enumerate(q.get("samples") or [], 1):
                total_cases += 1
                out, err = run_case(exe, tmp, s)
                if out is None:
                    bad.append((j, "运行超时", ""))
                elif norm(out) != norm(s["out"]):
                    bad.append((j, norm(s["out"]), norm(out)))
            if bad:
                fails += 1
                print(f"[FAIL] {tag} 样例不匹配 {len(bad)} 组")
                for idx, exp, got in bad[:2]:
                    print(f"       样例 {idx} 期望:\n{'-'*8}\n{exp}\n{'-'*8}\n       实际:\n{'-'*8}\n{got}\n{'-'*8}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n[RESULT] 题目 {len(problems)} 道，样例 {total_cases} 组，失败 {fails} 道")
    return fails


def main():
    args = sys.argv[1:]
    schema_only = "--schema-only" in args
    args = [a for a in args if not a.startswith("--") and a != "--all"]
    if "--all" in sys.argv:
        args = sorted(os.path.join("content", f) for f in os.listdir(os.path.join(ROOT, "content"))
                      if f.endswith(".json"))
    if not args:
        print(__doc__)
        return 1
    paths = [a if os.path.isabs(a) else os.path.join(ROOT, a) for a in args]
    problems = collect(paths)
    errors = validate(problems)
    if schema_only:
        return 1 if errors else 0
    if errors:
        print("\n结构错误未修复，跳过编译/运行。")
        return 1
    return 1 if check(problems) else 0


if __name__ == "__main__":
    sys.exit(main())

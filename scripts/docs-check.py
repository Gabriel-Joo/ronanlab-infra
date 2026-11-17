#!/usr/bin/env python3
"""문서 점검 — notion/ 원고와 docs/NN_*.md 개발자 문서를 기계로 본다.

    python3 scripts/docs-check.py            # 틀린 것만
    python3 scripts/docs-check.py -v         # 근거 없는 숫자 줄(의심)까지

보는 것
  1. 머리 주석: 편마다 맨 위 HTML 주석에 「다루는 곳」과 「읽은 커밋」이 있고, 읽은 커밋이 모든 편에서 같다
  2. 다루는 곳: 적힌 파일, 폴더(끝이 /), 글롭이 읽은 커밋에 실제로 있다
  3. 근거 표시: [code:경로] [docs:경로] [c:커밋], 경로 뒤 :줄 또는 :줄-줄. 읽은 커밋 기준으로 파일이 있고 줄 범위가 맞다
  4. 범위: 읽은 커밋의 추적 파일(docs/, notion/, portfolio/ 밖) 하나하나가 notion/ 어느 편의 다루는 곳에 든다
  5. 편 사이 참조: → 「제목」의 제목이 notion/ 어느 편의 첫 # 줄과 같다
  6. 원고 금지어(notion/만): IP 주소, 도메인, 홈 경로, 토큰 꼴 문자열, 포트 번호
  7. 포트폴리오(portfolio/*.md, 2026-11-17): 1~3과 같은 머리 주석, 근거 점검. 읽은 커밋은 포트폴리오 편끼리 하나다
     (기술문서와는 따로). 금지어는 6과 같되 도메인은 ronanlab.dev만 된다. 그림 ![…](img/…)은 파일이 있어야 한다.
     → 「제목」은 포트폴리오 편의 첫 # 줄을 본다

근거 표시 문법은 FOREMAN 게시기(bridge/evidence.py)와 같다. 게시기가 노션 판에서 머리 주석과 근거 표시를 뗀다.
틀린 것이 하나라도 있으면 1로 끝난다.
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARK = re.compile(r"\[(?P<k>c|t|log|docs|code):(?P<v>[^\]\s]+)\]")
EVIDENCE = re.compile(r"\s*\[(?:c|t|log|docs|code):[^\]\s]+\]")
XREF = re.compile(r"→\s*「(?P<t>[^」]*)」")
CLAIM = re.compile(r"\d|“|”")
SKIP_LINE = re.compile(r"^\s*(#|>|\||```|---|!\[|\s*$)")
FIELD = re.compile(r"^\s*(?P<k>다루는 곳|읽은 커밋)\s*:\s*(?P<v>.*?)\s*$")
OUTSIDE = ("docs/", "notion/", "portfolio/")

BANNED = [
    ("IP 주소", re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")),
    ("도메인", re.compile(r"\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:dev|com|kr|io|net|org|local|ai|app|cloud)\b", re.I)),
    ("홈 경로", re.compile(r"(?:/home/|~/)")),
    ("토큰 꼴", re.compile(r"\b(?:[0-9a-f]{32,}|[A-Za-z0-9_-]{40,})\b")),
    ("포트 번호", re.compile(r"(?::\d{2,5}\b|포트\s*\d{2,5}|\d{2,5}\s*번?\s*포트)")),
]


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=False).stdout


def head(md: str) -> dict[str, list[str]]:
    """맨 앞 HTML 주석의 필드. 없으면 빈 dict."""
    m = re.match(r"\s*<!--(.*?)-->", md, re.S)
    out: dict[str, list[str]] = {}
    if not m:
        return out
    for line in m.group(1).splitlines():
        f = FIELD.match(line)
        if f:
            vals = [v.strip() for v in f["v"].split(",") if v.strip()]
            out.setdefault(f["k"], []).extend(vals)
    return out


def body_lines(md: str) -> list[tuple[int, str, bool]]:
    """(줄 번호, 줄, 코드 울타리 안인가). HTML 주석 안 줄은 뺀다."""
    out, fence, comment = [], False, False
    for i, line in enumerate(md.splitlines(), 1):
        s = line.strip()
        if comment:
            comment = "-->" not in s
            continue
        if s.startswith("<!--"):
            comment = "-->" not in s
            continue
        if s.startswith("```"):
            fence = not fence
            out.append((i, line, True))
            continue
        out.append((i, line, fence))
    return out


def matches(pattern: str, files: list[str]) -> list[str]:
    if pattern.endswith("/"):
        return [f for f in files if f.startswith(pattern)]
    if any(ch in pattern for ch in "*?["):
        return [f for f in files if fnmatch.fnmatchcase(f, pattern)]
    return [f for f in files if f == pattern]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()

    manus = sorted(p for p in (ROOT / "notion").rglob("*.md")) if (ROOT / "notion").is_dir() else []
    devs = sorted((ROOT / "docs").glob("[0-9][0-9]_*.md"))
    targets = manus + devs
    errors: list[str] = []
    warns: list[str] = []
    if not manus:
        errors.append("notion/ 원고가 없다")
    folio = sorted((ROOT / "portfolio").glob("[0-9][0-9]_*.md"))
    folio_errors: list[str] = []
    folio_marks = check_portfolio(folio, folio_errors) if folio else 0

    reads: dict[str, str] = {}
    heads: dict[Path, dict[str, list[str]]] = {}
    for p in targets:
        h = head(p.read_text(encoding="utf-8"))
        heads[p] = h
        rel = p.relative_to(ROOT).as_posix()
        if "다루는 곳" not in h or "읽은 커밋" not in h:
            errors.append(f"{rel}: 머리 주석에 다루는 곳 또는 읽은 커밋이 없다")
            continue
        reads[rel] = h["읽은 커밋"][0]
    commits = sorted(set(reads.values()))
    if len(commits) != 1:
        errors.append(f"읽은 커밋이 하나가 아니다: {commits}")
        return report(errors, warns, len(targets))
    read = commits[0]
    if subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", f"{read}^{{commit}}"], capture_output=True).returncode:
        errors.append(f"읽은 커밋 {read}이 저장소에 없다")
        return report(errors, warns, len(targets))
    tracked = git("ls-tree", "-r", "--name-only", read).split()
    tracked_set = set(tracked)
    line_cache: dict[str, int] = {}

    def n_lines(path: str) -> int:
        if path not in line_cache:
            line_cache[path] = len(git("show", f"{read}:{path}").splitlines())
        return line_cache[path]

    titles = {}
    for p in manus:
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                # H1 앞 번호(「00 」, 「02-01 」)는 노션 제목용이다. 참조는 번호 없이 쓴다(2026-11-17)
                titles[re.sub(r"^\d{2}(-\d{2})? ", "", line[2:].strip())] = p
                break

    covered: set[str] = set()
    marks_total = 0
    for p in targets:
        rel = p.relative_to(ROOT).as_posix()
        h = heads[p]
        for pat in h.get("다루는 곳", []):
            got = matches(pat, tracked)
            if not got:
                errors.append(f"{rel}: 다루는 곳 「{pat}」이 읽은 커밋에 없다")
            if p in manus:
                covered.update(got)
        is_manu = p in manus
        for i, line, fenced in body_lines(p.read_text(encoding="utf-8")):
            for m in MARK.finditer(line):
                marks_total += 1
                k, v = m["k"], m["v"]
                why = check_mark(k, v, tracked_set, n_lines, read)
                if why:
                    errors.append(f"{rel}:{i}: {m.group(0)} {why}")
            for x in XREF.finditer(line):
                if x["t"] not in titles:
                    errors.append(f"{rel}:{i}: → 「{x['t']}」 제목을 가진 편이 없다")
            if is_manu:
                plain = EVIDENCE.sub("", line)
                for name, rx in BANNED:
                    hit = rx.search(plain)
                    if hit:
                        errors.append(f"{rel}:{i}: 원고 금지어({name}) 「{hit.group(0)}」")
            if not fenced and not SKIP_LINE.match(line) and CLAIM.search(EVIDENCE.sub("", line)) and not MARK.search(line):
                warns.append(f"{rel}:{i}: 숫자나 인용이 있는데 근거 표시가 없다")

    outside = [f for f in tracked if not f.startswith(OUTSIDE)]
    for f in outside:
        if f not in covered:
            errors.append(f"범위 밖: {f} 가 notion/ 어느 편에도 들지 않는다")

    print(f"읽은 커밋 {read}, 편 {len(targets)}(원고 {len(manus)}, 개발자 {len(devs)}), 근거 표시 {marks_total}, "
          f"범위 대상 파일 {len(outside)} 중 {len([f for f in outside if f in covered])} 덮음")
    if folio:
        print(f"포트폴리오 편 {len(folio)}, 근거 표시 {folio_marks}")
    return report(errors + folio_errors, warns if a.verbose else [], len(targets), len(warns))


def check_portfolio(folio: list[Path], errors: list[str]) -> int:
    """포트폴리오 편 — 읽은 커밋은 포트폴리오끼리 하나, 금지어에서 ronanlab.dev는 뺀다, 그림 파일이 있어야 한다."""
    heads = {p: head(p.read_text(encoding="utf-8")) for p in folio}
    reads = set()
    for p, h in heads.items():
        if "다루는 곳" not in h or "읽은 커밋" not in h:
            errors.append(f"{p.relative_to(ROOT).as_posix()}: 머리 주석에 다루는 곳 또는 읽은 커밋이 없다")
            continue
        reads.add(h["읽은 커밋"][0])
    if len(reads) != 1:
        errors.append(f"포트폴리오 읽은 커밋이 하나가 아니다: {sorted(reads)}")
        return 0
    read = reads.pop()
    if subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", f"{read}^{{commit}}"], capture_output=True).returncode:
        errors.append(f"포트폴리오 읽은 커밋 {read}이 저장소에 없다")
        return 0
    tracked = git("ls-tree", "-r", "--name-only", read).split()
    tracked_set = set(tracked)
    cache: dict[str, int] = {}

    def n_lines(path: str) -> int:
        if path not in cache:
            cache[path] = len(git("show", f"{read}:{path}").splitlines())
        return cache[path]

    titles = set()
    for p in folio:
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                titles.add(line[2:].strip())
                break
    img = re.compile(r"!\[[^\]]*\]\((?P<src>[^)\s]+)\)")
    marks = 0
    for p in folio:
        rel = p.relative_to(ROOT).as_posix()
        for pat in heads[p].get("다루는 곳", []):
            if not matches(pat, tracked):
                errors.append(f"{rel}: 다루는 곳 「{pat}」이 읽은 커밋에 없다")
        for i, line, fenced in body_lines(p.read_text(encoding="utf-8")):
            for m in MARK.finditer(line):
                marks += 1
                why = check_mark(m["k"], m["v"], tracked_set, n_lines, read)
                if why:
                    errors.append(f"{rel}:{i}: {m.group(0)} {why}")
            for x in XREF.finditer(line):
                if x["t"] not in titles:
                    errors.append(f"{rel}:{i}: → 「{x['t']}」 제목을 가진 포트폴리오 편이 없다")
            for g in img.finditer(line):
                if not re.match(r"https?://", g["src"]) and not (p.parent / g["src"]).is_file():
                    errors.append(f"{rel}:{i}: 그림 파일이 없다 {g['src']}")
            plain = img.sub("", EVIDENCE.sub("", line))
            for name, rx in BANNED:
                for hit in rx.finditer(plain):
                    if name == "도메인" and hit.group(0).lower().endswith("ronanlab.dev"):
                        continue
                    errors.append(f"{rel}:{i}: 원고 금지어({name}) 「{hit.group(0)}」")
                    break
    return marks


def check_mark(k: str, v: str, tracked: set[str], n_lines, read: str) -> str | None:
    if k in ("t", "log"):
        return "이 저장소에서 쓰지 않는 종류다"
    if k == "c":
        ok = subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", f"{v}^{{commit}}"], capture_output=True).returncode == 0
        return None if ok else "커밋이 없다"
    m = re.match(r"^(?P<f>[^:#]+?)(?::(?P<a>\d+)(?:-(?P<b>\d+))?)?$", v)
    if not m:
        return "모양을 알아보지 못했다"
    path = m["f"] if k == "code" else f"docs/{m['f']}"
    if path.endswith("/"):
        return None if any(t.startswith(path) for t in tracked) else f"{path} 폴더가 읽은 커밋에 없다"
    if path not in tracked:
        if k == "code" and any(t.startswith(path + "/") for t in tracked) and not m["a"]:
            return None
        return f"{path} 파일이 읽은 커밋 {read}에 없다"
    if m["a"]:
        n = n_lines(path)
        x, y = int(m["a"]), int(m["b"] or m["a"])
        if x < 1 or y > n or y < x:
            return f"줄 범위가 맞지 않는다(파일은 {n}줄)"
    return None


def report(errors: list[str], warns: list[str], n: int, n_warn: int = 0) -> int:
    for e in errors:
        print("틀림  " + e)
    for w in warns:
        print("의심  " + w)
    print(f"틀린 것 {len(errors)}, 의심 {n_warn}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

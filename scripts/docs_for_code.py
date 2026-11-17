#!/usr/bin/env python3
"""거꾸로 찾기 — 코드 파일을 주면 그 코드를 가리키는 문서(docs, 노션 원고, 포트폴리오)와 줄, 문단을 보인다.

    python3 scripts/docs_for_code.py apps/cloudflared/configmap.yaml       # 이 파일을 가리키는 문서
    python3 scripts/docs_for_code.py platform/metallb/ cluster/Vagrantfile:10-20   # 폴더(끝이 /), 줄 범위
    python3 scripts/docs_for_code.py --range main...HEAD                  # 이 브랜치가 바꾼 것으로, 고침 / 안 고침까지
    python3 scripts/docs_for_code.py --range main...HEAD --unfixed        # 안 고친 문서만
    python3 scripts/docs_for_code.py --range 6290346..origin/main --brief # 문서와 줄 번호만
    python3 scripts/docs_for_code.py --range main...HEAD --json           # 기계가 읽을 때
    python3 scripts/docs_for_code.py --self-test                          # 가짜 저장소로 자기 점검

읽기만 한다. 저장소를 바꾸지 않는다(git은 ls-tree, ls-files, cat-file, diff, merge-base, rev-parse만 부른다).
FOREMAN 저장소의 bridge/docrefs.py, tools/docrefs.py를 이 저장소 문서 구조에 맞게 옮겼다(2026-11-17).

문서 묶음(셋 다 *.md만)
  docs       docs/ 아래(runbooks/, README.md, style_guide.md, NN_*.md 등). docs/history/는 기록이라 뺀다
  notion     .foreman/notion.toml의 src(없으면 notion/)
  portfolio  portfolio/
  docs/history/는 문서 묶음도, 코드도 아니다(어디에서도 보지 않는다)

걸게 하는 것(트리거)
  코드      문서 묶음 폴더(docs/, 원고 폴더, portfolio/) 밖의 추적 파일 가운데 *.md가 아닌 것
            (platform/, cluster/, apps/, bootstrap/, scripts/, .foreman/, 맨 위 설정)
  문서      docs/ 아래 문서(history 빼고)와 문서 묶음 밖의 *.md(CLAUDE.md, README.md, apps/*/README.md 등).
            근거 표시와 다루는 곳으로 가리킬 때만 걸린다(경로를 글에 적은 것만으로는 걸지 않는다)
  번호 짝   docs/NN_*.md가 바뀌면 같은 번호의 원고 notion/NN_*.md와 notion/NN_*/ 아래 글도 걸린다

가리키는 꼴(how)
  mark    근거 표시 [code:경로], [code:경로:줄-줄], [docs:경로](docs/ 아래 경로), 폴더(끝이 /)
  covers  머리 주석 「다루는 곳」(파일, 끝이 /인 폴더, *가 든 글롭)
  path    백틱 안이나 맨글의 저장소 경로(코드만)
  name    백틱 안의 파일 이름이나 경로 끝. 저장소에서 그 끝을 가진 파일이 하나뿐일 때만(코드만)
  pair    번호 짝

줄 범위: 근거 표시에 줄 범위가 있고 바뀐 줄을 알 때(--range, 또는 경로:줄-줄 인자)는 겹칠 때만 걸린 것으로 친다.
바뀐 줄은 범위의 옛 쪽 줄 번호다(근거 표시는 쓸 때 읽은 판의 줄을 가리킨다). 줄 범위 없는 표시, 다루는 곳, 경로는 늘 걸린다.

--range를 주면 문서는 범위 끝 판을 읽고, 그 문서가 같은 범위에서 바뀌었으면 「고침」, 아니면 「안 고침」이다.
파일만 주면 작업 트리(또는 --rev 판)를 읽고 고쳤는지는 「모름」이다.

출력에는 저장소 글에 있는 것만 낸다(문단 발췌). 이 도구가 스스로 주소, 홈 경로 같은 것을 덧붙이지 않는다(공개 저장소).
종료 코드: 0(찾음, 없어도 0), 2(인자나 git 문제). --self-test는 통과 0, 실패 1.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = "docs/"
HISTORY_DIR = "docs/history/"
PORTFOLIO_DIR = "portfolio/"
DEFAULT_SRC = "notion/"

MARK = re.compile(r"\[(?P<k>code|docs):(?P<v>[^\]\s]+)\]")
ANY_MARK = re.compile(r"\[(?:c|t|log|code|docs):[^\]\s]+\]")
TICK = re.compile(r"`([^`\n]+)`")
TOKEN = re.compile(r"[A-Za-z0-9_./*-]+(?::\d+(?:-\d+)?)?")
# 맨글 경로: 슬래시가 있고 확장자로 끝나는 것만(URL의 // 뒤, 다른 경로 가운데는 빼려고 앞 글자를 본다)
PLAIN = re.compile(r"(?<![\w./:-])((?:[\w.-]+/)+[\w.-]+\.[A-Za-z0-9]{1,6})(?::(\d+)(?:-(\d+))?)?(?![\w/-])")
RANGE = re.compile(r"^(?P<p>.+?):(?P<a>\d+)(?:-(?P<b>\d+))?$")
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s|^\s*\|")
EXT = re.compile(r"\.[A-Za-z0-9]{1,6}$")
FIELD = re.compile(r"^\s*(?P<k>다루는 곳|읽은 커밋)\s*:\s*(?P<v>.*?)\s*$")
DEV_NN = re.compile(r"^docs/(\d{2})_[^/]*\.md$")

KIND_KO = {"docs": "docs", "notion": "노션 원고", "portfolio": "포트폴리오"}
HOW_KO = {"mark": "근거 표시", "path": "경로", "name": "파일 이름", "covers": "다루는 곳", "pair": "번호 짝"}


class DocrefsError(RuntimeError):
    """git을 읽지 못함, 범위를 모름 등. 화면에 이 글을 그대로 보인다."""


def _git(repo: str, *a: str, input_: bytes | None = None) -> bytes:
    try:
        r = subprocess.run(["git", "-C", repo, *a], capture_output=True, timeout=60, input=input_)
    except (OSError, subprocess.SubprocessError) as e:
        raise DocrefsError(f"git을 부르지 못했다({type(e).__name__})") from e
    if r.returncode:
        raise DocrefsError(f"git {a[0]} 실패: {r.stderr.decode(errors='replace').strip()[:200]}")
    return r.stdout


def _gits(repo: str, *a: str) -> str:
    return _git(repo, *a).decode(errors="replace")


# ── 문서 묶음 ───────────────────────────────────────────────
def manuscript_src(repo: str) -> str:
    """원고 폴더(끝이 /). `.foreman/notion.toml`의 src, 없거나 깨졌으면 notion/."""
    try:
        text = (Path(repo) / ".foreman" / "notion.toml").read_text(encoding="utf-8")
    except OSError:
        return DEFAULT_SRC
    v = None
    try:
        import tomllib
        v = tomllib.loads(text).get("src")
    except Exception:  # tomllib가 없거나(옛 파이썬) 깨진 파일
        m = re.search(r'^\s*src\s*=\s*"([^"]*)"', text, re.M)
        v = m.group(1) if m else None
    ok = isinstance(v, str) and v.endswith("/") and ".." not in v and not v.startswith("/") and v != DOCS_DIR
    return v if ok else DEFAULT_SRC


def doc_sets(src: str) -> dict[str, str]:
    return {"docs": DOCS_DIR, "notion": src, "portfolio": PORTFOLIO_DIR}


def kind_of(path: str, sets: dict[str, str]) -> str | None:
    """문서 묶음 이름. 문서가 아니면(또는 docs/history/면) None."""
    if not path.endswith(".md") or path.startswith(HISTORY_DIR):
        return None
    for k, d in sorted(sets.items(), key=lambda x: -len(x[1])):
        if path.startswith(d):
            return k
    return None


def trigger_kind(path: str, sets: dict[str, str]) -> str | None:
    """걸게 하는 파일의 종류: code, doc, 또는 None(원고, 포트폴리오, docs/history/, docs/ 아래 *.md가 아닌 것)."""
    if path.startswith(HISTORY_DIR):
        return None
    inside = any(path.startswith(d) for d in sets.values())
    if path.endswith(".md"):
        return "doc" if (not inside or kind_of(path, sets) == "docs") else None
    return None if inside else "code"


# ── 문서 읽기 ───────────────────────────────────────────────
def _tree(repo: str, rev: str | None, dirs: list[str] | None = None) -> list[str]:
    if rev:
        out = _gits(repo, "ls-tree", "-r", "--name-only", rev, "--", *(dirs or []))
    else:
        out = _gits(repo, "ls-files", "--", *(dirs or []))
    return [x for x in out.splitlines() if x]


def _read_many(repo: str, rev: str | None, paths: list[str]) -> dict[str, str]:
    """여러 문서를 한 번에. rev면 `git cat-file --batch`, 아니면 작업 트리."""
    if not paths:
        return {}
    out: dict[str, str] = {}
    if not rev:
        for p in paths:
            try:
                out[p] = (Path(repo) / p).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
        return out
    raw = _git(repo, "cat-file", "--batch", input_="".join(f"{rev}:{p}\n" for p in paths).encode())
    i = 0
    for p in paths:
        nl = raw.index(b"\n", i)
        head = raw[i:nl].decode(errors="replace").split()
        i = nl + 1
        if len(head) < 3 or head[1] == "missing":
            continue
        size = int(head[2])
        out[p] = raw[i:i + size].decode(errors="replace")
        i += size + 1
    return out


# ── 머리 주석(FOREMAN bridge/manuscript.py의 _comments, parse_head) ──
def _comments(md: str) -> list[tuple[int, int, str]]:
    """코드 울타리 밖 HTML 주석 (시작 줄, 끝 줄, 안 글). 줄 번호는 0부터."""
    lines = md.replace("\r\n", "\n").split("\n")
    out = []
    fence = None
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if fence:
            if s.startswith(fence):
                fence = None
        elif (m := re.match(r"^(`{3,}|~{3,})", s)):
            fence = m.group(1)
        elif s.startswith("<!--"):
            j = i
            while j < len(lines) and "-->" not in lines[j]:
                j += 1
            j = min(j, len(lines) - 1)
            body = "\n".join(lines[i:j + 1])
            out.append((i, j, body.split("<!--", 1)[1].rsplit("-->", 1)[0]))
            i = j
        i += 1
    return out


def parse_head(md: str) -> dict[str, Any] | None:
    """머리 주석 → {covers, read, line(1부터)}. 「다루는 곳」, 「읽은 커밋」이 든 첫 주석. 없으면 None."""
    for a, _, body in _comments(md):
        covers: list[str] = []
        read = None
        found = False
        for ln in body.split("\n"):
            m = FIELD.match(ln)
            if not m:
                continue
            found = True
            if m["k"] == "다루는 곳":
                covers += [c.strip().strip("`") for c in m["v"].split(",") if c.strip().strip("`")]
            else:
                read = m["v"].strip().strip("`") or None
        if found:
            return {"covers": covers, "read": read, "line": a + 1}
    return None


# ── 문서 안의 가리킴 ────────────────────────────────────────
def _split_range(tok: str) -> tuple[str, tuple[int, int] | None]:
    m = RANGE.match(tok)
    if not m:
        return tok, None
    a = int(m["a"])
    return m["p"], (a, int(m["b"] or a))


def _clean(tok: str) -> str:
    tok = tok.strip().strip(".,;")
    return tok[2:] if tok.startswith("./") else tok


def _pathlike(tok: str) -> bool:
    if not tok or tok.startswith(("-", "/", "~")) or ".." in tok.split("/") or not re.search(r"[A-Za-z]", tok):
        return False
    if not ("/" in tok or EXT.search(tok)):
        return False
    # 백틱과 맨글의 폴더, 글롭은 두 단계 이상만. `apps/`, `scripts/*`는 「그 폴더 전체」라는 말이라 헛걸림만 는다(FOREMAN에서 겪음)
    fixed = re.split(r"[*?\[]", tok, maxsplit=1)[0]
    if (tok.endswith("/") or fixed != tok or not EXT.search(tok)) and len([s for s in fixed.split("/") if s]) < 2:
        return False
    return True


def refs_in(md: str) -> list[dict[str, Any]]:
    """한 문서의 가리킴 [{line, target, range, how, ref}]. 코드 울타리와 HTML 주석 안은 보지 않는다(머리 주석은 covers로)."""
    out: list[dict[str, Any]] = []
    head = parse_head(md)
    if head:
        for c in head["covers"]:
            out.append({"line": head["line"], "target": _clean(c), "range": None, "how": "covers", "ref": f"다루는 곳: {c}"})
    fence = None
    in_comment = False
    for i, ln in enumerate(md.splitlines(), 1):
        m = FENCE.match(ln)
        if fence:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
                fence = None
            continue
        if m:
            fence = m.group(1)
            continue
        if in_comment or ln.lstrip().startswith("<!--"):
            in_comment = "-->" not in ln
            continue
        seen: set[tuple[str, Any, str]] = set()

        def add(target: str, rng: tuple[int, int] | None, how: str, ref: str) -> None:
            if (target, rng, how) in seen:
                return
            seen.add((target, rng, how))
            out.append({"line": i, "target": target, "range": rng, "how": how, "ref": ref})

        for mk in MARK.finditer(ln):
            p, rng = _split_range(_clean(mk["v"]))
            add(p if mk["k"] == "code" else DOCS_DIR + p, rng, "mark", mk.group(0))
        rest = ANY_MARK.sub(" ", ln)
        for tk in TICK.finditer(rest):
            for t in TOKEN.findall(tk.group(1)):
                p, rng = _split_range(_clean(t))
                if _pathlike(p):
                    add(p, rng, "path" if "/" in p else "name", f"`{tk.group(1)[:80]}`")
        for pm in PLAIN.finditer(TICK.sub(" ", rest)):
            rng = (int(pm[2]), int(pm[3] or pm[2])) if pm[2] else None
            add(_clean(pm[1]), rng, "path", pm.group(0))
    return out


def _headings(lines: list[str]) -> list[str]:
    """줄마다 그 줄이 든 제목(울타리 안 #은 제목이 아니다)."""
    cur = ""
    fence = None
    out = []
    for ln in lines:
        m = FENCE.match(ln)
        if fence:
            if m and m.group(1)[0] == fence[0]:
                fence = None
        elif m:
            fence = m.group(1)
        elif re.match(r"^#{1,6}\s", ln):
            cur = ln.lstrip("#").strip()
        out.append(cur)
    return out


def paragraph(lines: list[str], line: int, cap: int = 400) -> tuple[int, int, str]:
    """걸린 줄의 문단. 목록 항목과 표 줄은 그 줄(들여 쓴 이어지는 줄까지), 아니면 빈 줄로 나뉜 덩어리. (시작, 끝, 글)."""
    i = line - 1
    if i < 0 or i >= len(lines):
        return line, line, ""
    if LIST_ITEM.match(lines[i]) or re.match(r"^\s*#{1,6}\s", lines[i]):
        a = b = i
        ind = len(lines[i]) - len(lines[i].lstrip())
        while b + 1 < len(lines) and lines[b + 1].strip() and not LIST_ITEM.match(lines[b + 1]) \
                and len(lines[b + 1]) - len(lines[b + 1].lstrip()) > ind:
            b += 1
    else:
        a = b = i
        while a > 0 and lines[a - 1].strip() and not LIST_ITEM.match(lines[a - 1]) and not lines[a - 1].lstrip().startswith("#"):
            a -= 1
        while b + 1 < len(lines) and lines[b + 1].strip() and not LIST_ITEM.match(lines[b + 1]):
            b += 1
    txt = " ".join(x.strip() for x in lines[a:b + 1])
    return a + 1, b + 1, txt if len(txt) <= cap else txt[: cap - 1] + "…"


# ── 맞대기 ──────────────────────────────────────────────────
def _glob(p: str) -> bool:
    return any(ch in p for ch in "*?[")


def matches(target: str, how: str, path: str, kind: str, names: dict[str, list[str]]) -> bool:
    """가리킴 하나가 걸게 하는 파일 하나를 덮나. 폴더(끝이 /)는 그 아래 모두, 글롭은 fnmatch(*가 /도 넘는다),
    `name`은 저장소에서 그 끝을 가진 파일이 하나뿐일 때 그 파일만. 문서(kind doc)는 근거 표시와 다루는 곳만 본다."""
    if kind == "doc" and how not in ("mark", "covers"):
        return False
    if target.endswith("/"):
        return path.startswith(target)
    if _glob(target):
        return fnmatch.fnmatchcase(path, target)
    if target == path:
        return True
    if how == "name" or (how == "path" and not path.startswith(target)):
        cands = names.get(PurePosixPath(target).name, [])
        hits = [c for c in cands if c == target or c.endswith("/" + target)]
        return len(hits) == 1 and hits[0] == path
    return path.startswith(target + "/")     # 폴더를 / 없이 적은 것(`apps/monitoring`)


def _names(paths: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for p in paths:
        out.setdefault(PurePosixPath(p).name, []).append(p)
    return out


def changed_lines(repo: str, a: str, b: str, files: list[str]) -> dict[str, list[tuple[int, int]]]:
    """범위의 바뀐 줄(옛 쪽 a 판 줄 번호). 근거 표시의 줄 번호는 그 글을 쓸 때 읽은 판을 가리키므로 옛 쪽과 맞댄다."""
    if not files:
        return {}
    out: dict[str, list[tuple[int, int]]] = {}
    cur = None
    for ln in _gits(repo, "diff", "-U0", "--no-renames", a, b, "--", *files).splitlines():
        if ln.startswith("--- "):
            cur = ln[6:] if ln.startswith("--- a/") else None
        elif ln.startswith("+++ ") and cur is None and ln.startswith("+++ b/"):
            cur = ln[6:]
        elif ln.startswith("@@") and cur:
            m = re.match(r"^@@ -(\d+)(?:,(\d+))? ", ln)
            if m:
                s, n = int(m[1]), int(m[2] if m[2] is not None else 1)
                # 줄을 넣기만 한 덩어리(-s,0)는 옛 줄을 바꾸지 않는다. s와 s+1 사이로 적어(s+1, s), 근거 범위 안쪽에
                # 끼어들 때만 겹치게 한다(2026-11-17 고장: CLAUDE.md 34줄 뒤에 넣은 줄이 34줄을 건 근거를 헛걸었다)
                out.setdefault(cur, []).append((s + 1, s) if n == 0 else (s, s + n - 1))
    return out


def parse_range(repo: str, rng: str) -> tuple[str, str]:
    """`A..B`, `A...B`(갈라진 곳부터), `A`(A..HEAD)를 (옛 쪽 커밋, 새 쪽 커밋)으로."""
    if "..." in rng:
        a, b = rng.split("...", 1)
        b = b or "HEAD"
        a = _gits(repo, "merge-base", a or "HEAD", b).strip()
    elif ".." in rng:
        a, b = rng.split("..", 1)
        a, b = a or "HEAD", b or "HEAD"
    else:
        a, b = rng, "HEAD"
    try:
        a2 = _gits(repo, "rev-parse", "--verify", "--quiet", a + "^{commit}").strip()
        b2 = _gits(repo, "rev-parse", "--verify", "--quiet", b + "^{commit}").strip()
    except DocrefsError as e:
        raise DocrefsError(f"커밋 범위를 알아보지 못했다: {rng}") from e
    return a2, b2


def _pair_hits(trigger: str, doc_paths: list[str], sets: dict[str, str]) -> list[str]:
    """docs/NN_*.md → 같은 번호 원고 notion/NN_*.md, notion/NN_*/ 아래 글."""
    m = DEV_NN.match(trigger)
    if not m:
        return []
    src = sets["notion"]
    return [p for p in doc_paths if kind_of(p, sets) == "notion" and re.match(rf"^{m.group(1)}_", p[len(src):])]


def scan(repo: str | Path, files: list[str] | None = None, rng: str | None = None, rev: str | None = None,
         para_cap: int = 400) -> dict[str, Any]:
    """거꾸로 찾기 한 번. files(`경로`, `폴더/`, `경로:시작-끝`) 또는 rng 중 하나는 있어야 한다. 둘 다 주면 범위의 파일 중 files만.

    돌려주는 것: {range, rev, sets, code, triggers, docs: [{doc, kind, fixed, files, hits: [{line, heading, para_from,
    para_to, para, how, ref, code, range, overlap}]}], total, unfixed, warnings}. docs는 안 고친 것, 걸린 수가 많은 것 먼저."""
    repo = str(Path(repo).resolve())
    if not files and not rng:
        raise DocrefsError("코드 파일이나 커밋 범위를 주어야 한다")
    sets = doc_sets(manuscript_src(repo))
    warnings: list[str] = []
    given: dict[str, list[tuple[int, int]]] = {}
    for f in files or []:
        p, r = _split_range(_clean(f))
        given.setdefault(p, [])
        if r:
            given[p].append(r)
    changed: set[str] = set()
    lines_of: dict[str, list[tuple[int, int]]] = {}
    a = b = None
    if rng:
        a, b = parse_range(repo, rng)
        changed = set(_gits(repo, "diff", "--name-only", "--no-renames", a, b).splitlines())
        trig = sorted(p for p in changed if trigger_kind(p, sets))
        if given:
            trig = [p for p in trig if p in given or any(matches(g, "path", p, "code", {}) for g in given)]
        rev = b
        tracked = _tree(repo, rev)
    else:
        tracked = _tree(repo, rev)
        trig = []
        for g, r in given.items():
            if g.endswith("/") or _glob(g):
                under = [p for p in tracked if matches(g, "covers", p, "code", {}) and trigger_kind(p, sets)]
                if not under:
                    warnings.append(f"{g}: 아래에 걸게 하는 파일이 없다")
                trig += under
            elif trigger_kind(g, sets):
                trig.append(g)
                if r:
                    lines_of[g] = r
            else:
                warnings.append(f"{g}: 코드도 docs 문서도 아니라 찾지 않는다(원고, 포트폴리오, docs/history/는 대상이 아니다)")
        trig = sorted(set(trig))
    kinds = {p: trigger_kind(p, sets) for p in trig}
    code = [p for p in trig if kinds[p] == "code"]
    empty = {"range": rng, "rev": rev, "sets": sets, "code": code, "triggers": trig, "docs": [], "total": 0,
             "unfixed": 0, "warnings": warnings}
    if not trig:
        return empty
    names = _names(sorted(set(tracked) | set(trig)))
    doc_paths = [p for p in _tree(repo, rev, list(sets.values())) if kind_of(p, sets)]
    bodies = _read_many(repo, rev, doc_paths)
    raw_hits: dict[str, list[dict[str, Any]]] = {}
    for path in doc_paths:
        body = bodies.get(path)
        if body is None:
            continue
        refs = refs_in(body)
        lines = body.splitlines()
        heads = None
        for r in refs:
            hit = [t for t in trig if t != path and matches(r["target"], r["how"], t, kinds[t], names)]
            if not hit:
                continue
            if heads is None:
                heads = _headings(lines)
            if r["how"] == "covers":
                pa, pb, ptxt = r["line"], r["line"], r["ref"]
            else:
                pa, pb, ptxt = paragraph(lines, r["line"], para_cap)
            for t in hit:
                raw_hits.setdefault(path, []).append({
                    "line": r["line"], "heading": "(머리 주석)" if r["how"] == "covers" else heads[r["line"] - 1],
                    "para_from": pa, "para_to": pb, "para": ptxt, "how": r["how"], "ref": r["ref"], "code": t,
                    "range": list(r["range"]) if r["range"] else None, "overlap": None})
    for t in trig:
        for p in _pair_hits(t, doc_paths, sets):
            raw_hits.setdefault(p, []).append({
                "line": 1, "heading": "(번호 짝)", "para_from": 1, "para_to": 1, "para": "", "how": "pair",
                "ref": f"번호 짝 {t}", "code": t, "range": None, "overlap": None})
    # 줄 범위가 있는 근거 표시만 바뀐 줄과 맞댄다. 겹치지 않으면 걸린 것으로 치지 않는다
    want = sorted({h["code"] for hs in raw_hits.values() for h in hs if h["range"] and h["how"] == "mark"})
    if want and rng and a and b:
        try:
            lines_of = changed_lines(repo, a, b, want)
        except DocrefsError as e:
            warnings.append(f"바뀐 줄을 읽지 못해 줄 범위를 보지 않았다: {e}")
    docs = []
    for path, hs in raw_hits.items():
        keep = []
        for h in hs:
            if h["range"] and h["how"] == "mark" and h["code"] in lines_of:
                h["overlap"] = any(s <= h["range"][1] and h["range"][0] <= e for s, e in lines_of[h["code"]])
                if not h["overlap"]:
                    continue
            keep.append(h)
        if not keep:
            continue
        keep.sort(key=lambda h: (h["line"], h["code"]))
        docs.append({"doc": path, "kind": kind_of(path, sets), "fixed": (path in changed) if rng else None,
                     "files": sorted({h["code"] for h in keep}), "hits": keep})
    docs.sort(key=lambda d: (d["fixed"] is True, -len(d["hits"]), d["doc"]))
    return {**empty, "docs": docs, "total": len(docs), "unfixed": sum(1 for d in docs if d["fixed"] is False)}


# ── 화면 ────────────────────────────────────────────────────
def fixed_ko(v: bool | None) -> str:
    return "고침" if v is True else "안 고침" if v is False else "모름"


def render(res: dict[str, Any], brief: bool = False, unfixed: bool = False) -> str:
    out = []
    n_doc = len(res["triggers"]) - len(res["code"])
    what = f"코드 파일 {len(res['code'])}개" + (f", 문서 {n_doc}개" if n_doc else "")
    head = f"걸리는 문서 {res['total']}"
    if res["range"]:
        head += f", 안 고침 {res['unfixed']} (범위 {res['range']}, 바뀐 {what})"
    else:
        head += f" ({what}, 고쳤는지는 --range를 주어야 안다)"
    out.append(head)
    for w in res.get("warnings") or []:
        out.append(f"주의: {w}")
    for d in res["docs"]:
        if unfixed and d["fixed"] is not False:
            continue
        lines = sorted({h["line"] for h in d["hits"]})
        out.append(f"\n[{fixed_ko(d['fixed'])}] {d['doc']} ({KIND_KO.get(d['kind'], d['kind'])}) 줄 "
                   f"{', '.join(map(str, lines[:12]))}" + (" …" if len(lines) > 12 else "") + f" ← {', '.join(d['files'])}")
        if brief:
            continue
        last = None
        for h in d["hits"]:
            key = (h["para_from"], h["code"], h["how"] == "pair")
            if key == last:
                continue
            last = key
            rng = ""
            if h["range"]:
                rng = f" 줄 {h['range'][0]}-{h['range'][1]}" + (" (바뀐 줄과 겹침)" if h["overlap"] else "")
            out.append(f"  {h['line']}: 「{h['heading'] or '(제목 없음)'}」 {HOW_KO.get(h['how'], h['how'])} {h['ref']} → {h['code']}{rng}")
            if h["how"] not in ("covers", "pair"):
                span = f"{h['para_from']}-{h['para_to']}" if h["para_to"] != h["para_from"] else str(h["para_from"])
                out.append(f"     ({span}) {h['para']}")
    return "\n".join(out)


# ── 자기 점검 ───────────────────────────────────────────────
def self_test() -> int:
    """가짜 저장소(임시 폴더)를 만들어 판정을 본다. 이 저장소는 건드리지 않는다."""
    results: list[tuple[str, bool]] = []

    def check(name: str, ok: bool) -> None:
        results.append((name, bool(ok)))

    with tempfile.TemporaryDirectory(prefix="docs_for_code_") as tmp:
        env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid", "GIT_CONFIG_GLOBAL": os.devnull,
               "GIT_CONFIG_NOSYSTEM": "1"}

        def g(*a: str) -> str:
            return subprocess.run(["git", "-C", tmp, *a], capture_output=True, text=True, env=env, check=True).stdout.strip()

        def put(path: str, text: str) -> None:
            f = Path(tmp) / path
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(text, encoding="utf-8")

        def commit(msg: str) -> str:
            g("add", "-A")
            g("commit", "-q", "-m", msg)
            return g("rev-parse", "HEAD")

        def ten(tag: str, change: int | None = None) -> str:
            return "".join(f"{tag} {i}{' 바꿈' if i == change else ''}\n" for i in range(1, 11))

        def docs_of(res: dict[str, Any]) -> dict[str, dict[str, Any]]:
            return {d["doc"]: d for d in res["docs"]}

        g("init", "-q", "-b", "main")
        put(".foreman/notion.toml", 'src = "notion/"\n')
        put("cluster/Vagrantfile", ten("vm"))
        put("apps/a/deploy.yaml", ten("deploy"))
        put("scripts/tool.sh", ten("echo"))
        put("docs/history/data.txt", "기록\n")
        put("docs/history/old.md", "# 옛 기록\n\n`apps/a/deploy.yaml`를 바꿨다. [code:apps/a/deploy.yaml]\n")
        put("docs/style_guide.md", "# 쓰는 법\n규칙 둘\n규칙 셋\n규칙 넷\n규칙 다섯\n")
        put("docs/03_kube.md", "<!--\n다루는 곳: apps/a/\n읽은 커밋: 0000000\n-->\n# 쿠버네티스\n\n"
            "VM 앞 줄. [code:cluster/Vagrantfile:2-3]\n\nVM 뒤 줄. [code:cluster/Vagrantfile:8-9]\n")
        put("notion/03_kube.md", "# 03 쿠버네티스\n\n쓰는 법을 따른다. [docs:style_guide.md:2-3]\n")
        put("notion/03_kube/01_sub.md", "# 03-01 아래 편\n\n본문.\n")
        put("notion/04_other.md", "# 04 다른 편\n\n규칙 다섯. [docs:style_guide.md:5]\n\n옛 기록. [docs:history/old.md]\n")
        put("portfolio/00_x.md", "# 한눈에\n\n도구를 씁니다. [code:scripts/tool.sh]\n")
        c0 = commit("base")

        # 1. 파일 모드
        r = scan(tmp, files=["scripts/tool.sh"])
        d = docs_of(r)
        check("파일 모드: 포트폴리오가 근거 표시로 걸림", "portfolio/00_x.md" in d and d["portfolio/00_x.md"]["fixed"] is None)
        r = scan(tmp, files=["apps/a/deploy.yaml"])
        d = docs_of(r)
        check("파일 모드: 다루는 곳 폴더로 걸림", "docs/03_kube.md" in d and d["docs/03_kube.md"]["hits"][0]["how"] == "covers")
        check("파일 모드: docs/history/는 문서로 보지 않음", not any(k.startswith("docs/history/") for k in d))
        r = scan(tmp, files=["docs/history/data.txt"])
        check("파일 모드: docs/history/ 파일은 코드가 아님", not r["triggers"] and not r["docs"])

        # 2. 줄 범위 인자
        r = scan(tmp, files=["cluster/Vagrantfile:2-2"])
        lines = [h["line"] for h in docs_of(r).get("docs/03_kube.md", {}).get("hits", [])]
        check("줄 범위 인자: 겹치는 표시만 걸림", lines == [7])

        # 3. 범위 모드: 안 고침, history 파일은 코드가 아님
        put("apps/a/deploy.yaml", ten("deploy", 4))
        put("docs/history/data.txt", "기록 바꿈\n")
        c1 = commit("code only")
        r = scan(tmp, rng=f"{c0}..{c1}")
        d = docs_of(r)
        check("범위 모드: 안 고침", d.get("docs/03_kube.md", {}).get("fixed") is False and r["unfixed"] == 1)
        check("범위 모드: docs/history/ 파일은 코드에서 빠짐", r["code"] == ["apps/a/deploy.yaml"])

        # 4. 범위 모드: 고침, 번호 짝
        put("apps/a/deploy.yaml", ten("deploy", 5))
        put("docs/03_kube.md", (Path(tmp) / "docs/03_kube.md").read_text(encoding="utf-8") + "\n덧붙임.\n")
        c2 = commit("code and doc")
        r = scan(tmp, rng=f"{c1}..{c2}")
        d = docs_of(r)
        check("범위 모드: 고침", d.get("docs/03_kube.md", {}).get("fixed") is True)
        pair = d.get("notion/03_kube.md", {})
        check("번호 짝: docs/03 → notion/03 (안 고침)", pair.get("fixed") is False and pair["hits"][0]["how"] == "pair")
        check("번호 짝: notion/03_kube/ 아래 글도", "notion/03_kube/01_sub.md" in d)
        check("번호 짝: 다른 번호는 안 걸림", "notion/04_other.md" not in d)

        # 5. 줄 범위 겹침(범위 모드)
        put("cluster/Vagrantfile", ten("vm", 9))
        c3 = commit("vm line 9")
        r = scan(tmp, rng=f"{c2}..{c3}")
        lines = [h["line"] for h in docs_of(r).get("docs/03_kube.md", {}).get("hits", [])]
        check("줄 범위: 겹치는 표시는 걸림, 안 겹치는 표시는 안 걸림", lines == [9])
        put("cluster/Vagrantfile", (Path(tmp) / "cluster/Vagrantfile").read_text(encoding="utf-8").replace("vm 5\n", "vm 5 바꿈\n"))
        c4 = commit("vm line 5")
        r = scan(tmp, rng=f"{c3}..{c4}")
        check("줄 범위: 어느 표시와도 안 겹치면 문서가 안 걸림", r["code"] == ["cluster/Vagrantfile"] and not r["docs"])

        # 6. 문서 사슬 [docs:style_guide.md:2-3], docs/history는 트리거가 아님
        put("docs/style_guide.md", "# 쓰는 법\n규칙 둘 바꿈\n규칙 셋\n규칙 넷\n규칙 다섯\n")
        put("docs/history/old.md", "# 옛 기록\n\n바꿈.\n")
        c5 = commit("style guide line 2")
        r = scan(tmp, rng=f"{c4}..{c5}")
        d = docs_of(r)
        hit = d.get("notion/03_kube.md", {})
        check("문서 사슬: [docs:style_guide.md:2-3]가 걸림", hit.get("fixed") is False and hit["hits"][0]["code"] == "docs/style_guide.md")
        check("문서 사슬: 안 겹치는 줄과 docs/history/는 안 걸림", "notion/04_other.md" not in d)
        check("문서 사슬: docs/history/는 트리거가 아님", r["triggers"] == ["docs/style_guide.md"])
        r = scan(tmp, rng=f"{c4}...{c5}")
        check("세 점 범위도 같음", docs_of(r).keys() == d.keys())

    bad = [n for n, ok in results if not ok]
    for n in bad:
        print(f"실패  {n}")
    print(f"자기 점검 통과 {len(results) - len(bad)}/{len(results)}")
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="코드를 가리키는 문서를 거꾸로 찾는다(읽기만)")
    ap.add_argument("files", nargs="*", help="코드 파일(경로, 끝이 /인 폴더, 경로:시작-끝). docs/ 아래 문서도 된다")
    ap.add_argument("--range", dest="rng", help="커밋 범위 A..B 또는 A...B(갈라진 곳부터). 바뀐 파일로 찾고 고침 / 안 고침을 보인다")
    ap.add_argument("--rev", help="범위 없이 찾을 때 문서를 읽을 커밋(기본 작업 트리)")
    ap.add_argument("--repo", default=str(ROOT), help="저장소 경로(기본: 이 스크립트가 든 저장소)")
    ap.add_argument("--unfixed", action="store_true", help="안 고친 문서만")
    ap.add_argument("--brief", action="store_true", help="문서와 줄 번호만")
    ap.add_argument("--json", action="store_true", help="JSON으로")
    ap.add_argument("--self-test", action="store_true", help="임시 가짜 저장소로 자기 점검")
    a = ap.parse_args(argv)
    if a.self_test:
        try:
            return self_test()
        except (DocrefsError, subprocess.CalledProcessError, OSError) as e:
            print(f"자기 점검 실패: {e}", file=sys.stderr)
            return 1
    if not a.files and not a.rng:
        ap.error("코드 파일이나 --range 중 하나는 주어야 한다")
    try:
        res = scan(a.repo, files=a.files or None, rng=a.rng, rev=a.rev)
    except DocrefsError as e:
        print(f"거꾸로 찾기 실패: {e}", file=sys.stderr)
        return 2
    if a.json:
        if a.unfixed:
            res = {**res, "docs": [d for d in res["docs"] if d["fixed"] is False]}
        print(json.dumps(res, ensure_ascii=False, indent=1))
    else:
        print(render(res, a.brief, a.unfixed))
    return 0


if __name__ == "__main__":
    sys.exit(main())

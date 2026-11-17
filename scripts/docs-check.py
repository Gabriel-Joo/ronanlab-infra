#!/usr/bin/env python3
"""문서 점검은 FOREMAN 문서 도구로 옮겼다(2026-11-17 문서 도구 합치기 3단계). 이 파일은 그 명령을 부르는 껍데기다.

    FOREMAN_DIR=<FOREMAN 저장소> python3 scripts/docs-check.py [-v]

규칙은 FOREMAN bridge/doctext/check.py, 이 저장소만의 값은 .foreman/docs.toml [check].
틀린 것이 있으면 1, FOREMAN을 못 찾거나 도구가 실패하면 2로 끝난다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from foreman_tool import run  # noqa: E402

run("check", sys.argv[1:])

#!/usr/bin/env python3
"""거꾸로 찾기는 FOREMAN 문서 도구로 옮겼다(2026-11-17 문서 도구 합치기 2, 3단계). 이 파일은 그 명령을 부르는 껍데기다.

    FOREMAN_DIR=<FOREMAN 저장소> python3 scripts/docs_for_code.py --range main...HEAD --unfixed

인자는 옛 것과 같다(파일, --range, --rev, --unfixed, --brief, --json). 이 저장소만의 값은 .foreman/docs.toml.
3단계부터 머리 주석 「다루는 곳」은 읽지 않는다(덮기 검사 몫). FOREMAN을 못 찾거나 도구가 실패하면 2로 끝난다.
옛 --self-test 장면은 FOREMAN 시험 tests/test_docrefs_config.py로 옮겼다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from foreman_tool import run  # noqa: E402

if "--self-test" in sys.argv[1:]:
    print("자기 점검은 FOREMAN 시험 tests/test_docrefs_config.py로 옮겼습니다", file=sys.stderr)
    sys.exit(2)
run("refs", sys.argv[1:])

import json, sys

P = {"type": "prometheus", "uid": "prometheus"}
M = {"type": "mysql", "uid": "petmint-mysql"}
L = {"type": "loki", "uid": "loki"}
panels, pid, y = [], 0, 0

def nid():
    global pid
    pid += 1
    return pid

def row(title):
    global y
    panels.append({"type": "row", "title": title, "id": nid(), "collapsed": False,
                   "gridPos": {"h": 1, "w": 24, "x": 0, "y": y}, "panels": []})
    y += 1

def add(p, w, h, x):
    p["id"] = nid()
    p["gridPos"] = {"h": h, "w": w, "x": x, "y": y}
    panels.append(p)

def prom(expr, legend=""):
    return {"datasource": P, "expr": expr, "legendFormat": legend, "refId": chr(65 + 0)}

def sql(q, fmt="time_series", ref="A"):
    return {"datasource": M, "rawSql": q, "format": fmt, "rawQuery": True, "editorMode": "code", "refId": ref}

def ts(title, targets, unit="short", desc="", bars=False, stack=False):
    for i, t in enumerate(targets):
        t["refId"] = chr(65 + i)
    return {"type": "timeseries", "title": title, "description": desc, "targets": targets,
            "fieldConfig": {"defaults": {"unit": unit, "custom": {
                "drawStyle": "bars" if bars else "line", "fillOpacity": 60 if bars else 10,
                "stacking": {"mode": "normal" if stack else "none"}}}, "overrides": []},
            "options": {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "multi"}}}

def stat(title, targets, unit="short", desc=""):
    for i, t in enumerate(targets):
        t["refId"] = chr(65 + i)
    return {"type": "stat", "title": title, "description": desc, "targets": targets,
            "fieldConfig": {"defaults": {"unit": unit}, "overrides": []},
            "options": {"reduceOptions": {"calcs": ["lastNotNull"]}, "colorMode": "value", "graphMode": "none"}}

def bar(title, q, desc=""):
    return {"type": "barchart", "title": title, "description": desc, "targets": [sql(q, "table")],
            "options": {"orientation": "auto", "showValue": "auto", "legend": {"showLegend": False}},
            "fieldConfig": {"defaults": {}, "overrides": []}}

def pie(title, q, desc=""):
    return {"type": "piechart", "title": title, "description": desc, "targets": [sql(q, "table")],
            "options": {"reduceOptions": {"values": True, "calcs": ["lastNotNull"]},
                        "pieType": "donut", "displayLabels": ["name", "value", "percent"],
                        "legend": {"displayMode": "list", "placement": "right"}},
            "fieldConfig": {"defaults": {}, "overrides": []}}

def text(title, md):
    return {"type": "text", "title": title, "options": {"mode": "markdown", "content": md}}

H = 'host="petmint.ronanlab.dev"'

row("상단 — 파드 · 트래픽")
add(stat("앱 Pod Ready", [prom('sum(kube_pod_status_ready{namespace="petmint",condition="true",pod=~"petmint-app-.*"})')],
         desc="petmint-app Pod 중 Ready 인 수(목표 2 — w1 · w2)"), 4, 6, 0)
add(stat("재시작(24시간)", [prom('sum(increase(kube_pod_container_status_restarts_total{namespace="petmint"}[24h]))')],
         desc="petmint 네임스페이스 컨테이너 재시작 합"), 4, 6, 4)
add(ts("요청 수(초당, 상태코드별)", [prom(f'sum by (status) (rate(nginx_ingress_controller_requests{{{H}}}[5m]))', "{{status}}")],
       unit="reqps", desc="ingress-nginx 기준 — 앱에 /metrics 가 없어 입구에서 센다. WebSocket 은 연결 한 번이 요청 하나"), 8, 6, 8)
add(ts("에러율(5xx 비율)", [prom(f'sum(rate(nginx_ingress_controller_requests{{{H},status=~"5.."}}[5m])) / clamp_min(sum(rate(nginx_ingress_controller_requests{{{H}}}[5m])), 1e-9)', "5xx")],
       unit="percentunit", desc="ingress-nginx 기준 5xx / 전체"), 8, 6, 16)
y += 6

row("중간 — 질문(턴 로그, DB Replica)")
add(ts("모드별 질문 수(시간당)", [sql(
    "SELECT $__timeGroupAlias(t.created_at, '1h'), s.mode AS metric, COUNT(*) AS value\n"
    "FROM turns t JOIN sessions s ON s.session_id = t.session_id\n"
    "WHERE $__timeFilter(t.created_at)\nGROUP BY 1, 2 ORDER BY 1")], bars=True, stack=True,
    desc="일반 · 사내규정 · 업무특화. 턴 = 질문 하나"), 14, 8, 0)
add(bar("시간대별 질문 수(KST)",
    "SELECT LPAD(HOUR(DATE_ADD(created_at, INTERVAL 9 HOUR)), 2, '0') AS `시(KST)`, COUNT(*) AS `질문`\n"
    "FROM turns WHERE $__timeFilter(created_at)\nGROUP BY 1 ORDER BY 1",
    desc="고른 기간 전체를 시(0~23)별로 합친 것. DB 는 UTC 라 +9시간"), 10, 8, 14)
y += 8

row("하단 — 답")
add(ts("거절률(일별)", [sql(
    "SELECT $__timeGroupAlias(t.created_at, '1d'), s.mode AS metric, AVG(t.refused) AS value\n"
    "FROM turns t JOIN sessions s ON s.session_id = t.session_id\n"
    "WHERE t.refused IS NOT NULL AND $__timeFilter(t.created_at)\nGROUP BY 1, 2 ORDER BY 1")],
    unit="percentunit",
    desc="turns.refused(2026-11-11~) — 답이 거절 문구인 턴 / status=ok 턴. 판정은 평가와 같은 함수(앱 data/refusal.py). "
         "코드 답 턴도 들어간다(코드 답은 거절 문구를 쓰지 않는다). 그 전 턴은 NULL이라 빠진다"), 6, 8, 0)
add(bar("규칙별 발동 수(code_rule)",
    "SELECT code_rule AS `규칙`, COUNT(*) AS `발동`\nFROM turns\n"
    "WHERE code_rule IS NOT NULL AND $__timeFilter(created_at)\nGROUP BY 1 ORDER BY 2 DESC",
    desc="코드가 약관 기준으로 직접 답한 턴의 규칙 이름"), 9, 8, 6)
add(pie("코드 답 vs 모델 답",
    "SELECT CASE WHEN code_rule IS NULL THEN '모델 답' ELSE '코드 답' END AS `종류`, COUNT(*) AS `턴`\n"
    "FROM turns WHERE $__timeFilter(created_at)\nGROUP BY 1",
    desc="code_rule 이 있으면 코드 답"), 9, 8, 15)
y += 8
add(pie("👍👎",
    "SELECT CASE rating WHEN 'up' THEN '👍' ELSE '👎' END AS `평가`, COUNT(*) AS `수`\n"
    "FROM feedback WHERE $__timeFilter(created_at)\nGROUP BY 1",
    desc="상담원 평가(feedback.rating). 코멘트는 읽지 않는다"), 6, 8, 0)
PCT = ("SELECT TIMESTAMP(d) AS time,\n"
       "  MAX(CASE WHEN pr <= 0.5 THEN v END) / 1000 AS `{n} p50`,\n"
       "  MAX(CASE WHEN pr <= 0.9 THEN v END) / 1000 AS `{n} p90`\n"
       "FROM (SELECT DATE(created_at) AS d, {c} AS v,\n"
       "        PERCENT_RANK() OVER (PARTITION BY DATE(created_at) ORDER BY {c}) AS pr\n"
       "      FROM turns WHERE status = 'ok' AND {c} IS NOT NULL AND $__timeFilter(created_at)) x\n"
       "GROUP BY d ORDER BY d")
add(ts("응답 시간 p50 / p90(일별)", [sql(PCT.format(n="전체", c="latency_ms"), ref="A"),
                                       sql(PCT.format(n="첫 토큰", c="first_token_ms"), ref="B")],
       unit="s", desc="turns.latency_ms(답 끝까지) · first_token_ms(첫 토큰까지), status=ok 만. MySQL 에 분위수 함수가 없어 PERCENT_RANK 로"), 12, 8, 6)
add(ts("검색 지연 p50 / p90(일별)", [sql(PCT.format(n="검색", c="search_ms"), ref="A")], unit="s",
       desc="turns.search_ms(2026-11-11~) — 한 턴에서 search-service(/search · /embed)를 기다린 시간 합, status=ok 만. "
            "검색하지 않은 턴(일반 · 사내규정 개인화)은 NULL이라 빠진다. 업무특화 코드 답 턴은 검색 뒤에 답하므로 들어간다"), 6, 8, 18)
y += 8

row("별도 — GPU · Ollama")
add(ts("GPU 사용률", [prom('nvidia_smi_utilization_gpu_ratio * 100', "GPU {{uuid}}")], unit="percent",
       desc="호스트 nvidia-gpu-exporter(scripts/host-gpu-exporter.sh) — 띄우기 전에는 비어 있다"), 8, 7, 0)
add(ts("VRAM", [prom('nvidia_smi_memory_used_bytes', "사용"), prom('nvidia_smi_memory_total_bytes', "전체")], unit="bytes",
       desc="호스트 nvidia-gpu-exporter"), 8, 7, 8)
add(ts("Ollama 에 올라간 모델(VRAM)", [prom('ollama_loaded_model_vram_bytes', "{{model}}")], unit="bytes",
       desc="/api/ps(json-exporter). 선이 바뀌면 모델이 교체된 것. 아무것도 없으면 모델이 내려가 있다(유휴 5분 뒤 언로드)"), 8, 7, 16)
y += 7
add(ts("턴이 쓴 모델(시간당)", [sql(
    "SELECT $__timeGroupAlias(created_at, '1h'), model AS metric, COUNT(*) AS value\n"
    "FROM turns WHERE $__timeFilter(created_at) AND model IS NOT NULL\nGROUP BY 1, 2 ORDER BY 1")],
    bars=True, stack=True, desc="turns.model — 베이스(tri-7b) · RAG 어댑터 교대"), 12, 7, 0)
add({"type": "logs", "title": "서버 로그(petmint 앱)", "datasource": L,
     "targets": [{"datasource": L, "expr": '{namespace="petmint", container="app"}', "refId": "A"}],
     "options": {"showTime": True, "wrapLogMessage": True, "sortOrder": "Descending"},
     "description": "Loki 7일. 대화 본문은 없다(서버 로그만)"}, 12, 7, 12)

dash = {"uid": "petmint-overview", "title": "petmint — 운영", "tags": ["petmint"], "timezone": "browser",
        "schemaVersion": 39, "version": 1, "editable": False, "refresh": "1m",
        "time": {"from": "now-30d", "to": "now"}, "panels": panels, "templating": {"list": []}, "annotations": {"list": []}}
json.dump(dash, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
print(len(panels), "panels")

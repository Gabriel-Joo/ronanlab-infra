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
# 보는 사람은 비개발자다(2026-11-11 사용자) — 이름은 무엇을 세는지 바로 알게, 설명(호버)은 무엇이 섞였나 · 높거나 낮으면 무슨 뜻인가 ·
# 언제부터 있나를 쉬운 말로. 칸 · 도구 이름은 설명 끝 「출처」 한 줄에만 남긴다
SRC = "\n\n출처: "

# 코드 답 규칙 이름(앱 petmint-rag-chatbot app/services/code_rules.RULES의 key → 이름, docs 16번 등록부). 규칙을 더하면 여기도 더한다 —
# 모르는 key는 그대로(영문) 나온다
RULE_NAMES = [
    ("reply_turn", "되물은 질문에 이어 답"), ("not_enrolled", "미가입 특약 안내"), ("annual", "올해 받은·남은 보험금"),
    ("needs_amount", "금액 되묻기"), ("hypothetical", "가정 등급 한도"), ("legal", "법률비용 계산"),
    ("question_turn", "치료비 계산"), ("limit", "한도표"), ("age", "가입 나이"), ("exclusion", "부담보 안내"),
    ("proviso", "면책 단서"), ("named_cover", "병명 보장 대조"), ("injury_followup", "상해 후속 안내"),
    ("disease_ask", "병명 되묻기"), ("hr_personal", "직원 본인 인사 정보(연차·퇴직금 등)"),
]
RULE_CASE = "CASE code_rule " + " ".join(f"WHEN '{k}' THEN '{v}'" for k, v in RULE_NAMES) + " ELSE code_rule END"

row("서비스 상태 · 접속량")
add(stat("응답 가능한 서버 수 (정상 2)",
         [prom('sum(kube_pod_status_ready{namespace="petmint",condition="true",pod=~"petmint-app-.*"})')],
         desc="챗봇 서버 2대 중 지금 요청을 받을 수 있는 수. 2가 정상, 1이면 한 대가 재시작 중이거나 고장, 0이면 서비스가 멈춘 것."
              " 배포 중에는 잠깐 1이 될 수 있다." + SRC + "kube-state-metrics, petmint-app Pod Ready"), 4, 6, 0)
add(stat("서버 재시작 횟수 (최근 24시간)",
         [prom('sum(increase(kube_pod_container_status_restarts_total{namespace="petmint"}[24h]))')],
         desc="챗봇 서버 · DB · 백업 작업이 오류로 꺼졌다가 스스로 다시 켜진 횟수. 0이 정상. 배포로 서버를 새것으로 바꾸는 것은 세지 않는다."
              + SRC + "kube-state-metrics, petmint 네임스페이스 컨테이너 재시작 합"), 4, 6, 4)
add(ts("접속 요청량 (초당, 결과별)",
       [prom(f'sum by (status) (rate(nginx_ingress_controller_requests{{{H}}}[5m]))', "{{status}}")], unit="reqps",
       desc="바깥(상담원 브라우저)에서 들어온 요청 수를 결과 번호별로. 200번대 = 정상, 300번대 = 다른 주소로 안내, "
            "400번대 = 로그인 안 됨 · 없는 주소 등 요청 쪽 문제, 500번대 = 서버 오류. 대화창 연결은 질문 수가 아니라 연결 한 번이 1건이다"
            ". 질문 수는 아래 「모드별 질문 수」에 있다." + SRC + "ingress-nginx(앱에 자체 지표가 없어 입구에서 센다)"), 8, 6, 8)
add(ts("서버 오류 비율",
       # 500번대가 한 번도 없으면 그 줄 자체가 없어 나눗셈 전체가 비므로(No data) or vector(0)으로 0을 채운다.
       # 요청이 아예 없을 때(분모가 없음)는 그대로 비어 있다
       [prom(f'(sum(rate(nginx_ingress_controller_requests{{{H},status=~"5.."}}[5m])) or vector(0)) / clamp_min(sum(rate(nginx_ingress_controller_requests{{{H}}}[5m])), 1e-9)', "서버 오류")],
       unit="percentunit",
       desc="전체 요청 중 서버 오류(500번대)의 비율. 0%가 정상. 화면이 안 열리거나 고객 조회가 안 되는 경우가 여기 잡힌다."
            " 대화창에서 답을 만들다 실패한 것은 여기 안 잡히고 아래 「답변 실패 · 중단 비율」에 나온다." + SRC + "ingress-nginx 5xx / 전체"),
    8, 6, 16)
y += 6

row("질문량")
add(ts("모드별 질문 수 (시간당)", [sql(
    "SELECT $__timeGroupAlias(t.created_at, '1h'), s.mode AS metric, COUNT(*) AS value\n"
    "FROM turns t JOIN sessions s ON s.session_id = t.session_id\n"
    "WHERE $__timeFilter(t.created_at)\nGROUP BY 1, 2 ORDER BY 1")], bars=True, stack=True,
    desc="상담원이 보낸 질문 수. 일반 = 일반 대화, 사내규정 = 인사규정 질문, 업무특화 = 고객 약관 상담."
         " 되묻기에 답한 것도 질문 하나로 센다." + SRC + "턴 로그(turns) · 세션 모드(sessions.mode), DB 복제본"), 14, 8, 0)
add(bar("시간대별 질문 수 (한국 시간)",
    "SELECT LPAD(HOUR(DATE_ADD(created_at, INTERVAL 9 HOUR)), 2, '0') AS `시`, COUNT(*) AS `질문`\n"
    "FROM turns WHERE $__timeFilter(created_at)\nGROUP BY 1 ORDER BY 1",
    desc="고른 기간 전체를 0~23시로 합친 분포. 어느 시간대에 질문이 몰리는지 본다." + SRC + "turns.created_at(UTC) + 9시간"), 10, 8, 14)
y += 8

row("답변 품질 · 속도")
add(ts("확인 불가 응답 비율 (일별)", [sql(
    "SELECT $__timeGroupAlias(t.created_at, '1d'), s.mode AS metric, AVG(t.refused) AS value\n"
    "FROM turns t JOIN sessions s ON s.session_id = t.session_id\n"
    "WHERE t.refused IS NOT NULL AND $__timeFilter(t.created_at)\nGROUP BY 1, 2 ORDER BY 1")],
    unit="percentunit",
    desc="모델 답이 \"확인되지 않습니다\" · \"명시되어 있지 않습니다\"처럼 확인 불가로 답한 비율(모드별). 세 가지가 섞여 있어 이 숫자만으로는 가를 수 없다:\n"
         "① 정상, 약관 · 규정에 원래 없는 질문(예: 보험료)\n"
         "② 검색이 맞는 조항을 못 찾아 확인 불가로 답한 것, 개선 대상\n"
         "③ 조항은 찾았는데 모델이 지나치게 조심한 것, 개선 대상\n"
         "검색 서비스가 멈춰 답을 못 한 경우는 여기 들어가지 않고 「답변 실패 · 중단 비율」에 나온다. 정상으로 끝난 답만 센다."
         " 2026-11-11부터 집계(그 전 질문은 빠진다). 판정은 문구 기준이라, 확인 불가 문구 없이 얼버무린 답은 세지 못하고 일부만 확인 불가라고 한 부분 답은 센다."
         " 2026-11-12 판정을 고쳤다 — 코드 답 · 코드가 덧붙인 참고 줄 · 다 답한 뒤의 \"인사부서에 확인\" 맺음말은 세지 않는다. 그 전 턴은 예전 판정 그대로라 조금 높게 적혀 있다(앱 docs 15번 4-1절)."
         + SRC + "turns.refused, 평가와 같은 판정(앱 data/refusal.py)"), 6, 8, 0)
add(ts("답변 실패 · 중단 비율 (일별)", [sql(
    "SELECT $__timeGroupAlias(created_at, '1d'),\n"
    "  AVG(status = 'error') AS `실패(오류)`,\n"
    "  AVG(status = 'cancelled') AS `중단`\n"
    "FROM turns WHERE $__timeFilter(created_at)\nGROUP BY 1 ORDER BY 1")], unit="percentunit",
    desc="질문 중 답을 끝까지 주지 못한 비율. 상담원이 막힌 질문이다.\n"
         "· 실패(오류), 검색 서비스나 AI 모델에 닿지 않거나 서버 오류로 답을 만들지 못했다. 상담원은 \"잠시 뒤 다시 물어 주세요\"를 봤다. 0%가 정상\n"
         "· 중단, 답이 끝나기 전에 상담원이 새 질문을 보냈거나 창을 닫았다. 되묻기에 답하지 않고 넘어간 것도 들어간다."
         " 늘 조금은 있고, 갑자기 늘면 답이 너무 느린지 본다" + SRC + "turns.status(error · cancelled) / 전체 질문"), 6, 8, 6)
add(bar("정해진 규칙으로 답한 횟수 (규칙별)",
    f"SELECT {RULE_CASE} AS `규칙`, COUNT(*) AS `횟수`\nFROM turns\n"
    "WHERE code_rule IS NOT NULL AND $__timeFilter(created_at)\nGROUP BY 1 ORDER BY 2 DESC",
    desc="AI 모델이 글을 짓지 않고 프로그램이 약관 · 인사 원장 기준으로 바로 답한 질문을 규칙별로 센다"
         "(보험금 계산, 미가입 특약, 병명 되묻기, 직원 본인 연차 등). 숫자 · 조항이 정확해야 하는 질문을 맡는다."
         + SRC + "turns.code_rule(규칙 이름은 앱 code_rules.RULES · docs 16번)"), 6, 8, 12)
add(pie("답한 방식: 규칙 / AI 모델",
    "SELECT CASE WHEN code_rule IS NULL THEN 'AI 모델' ELSE '정해진 규칙' END AS `방식`, COUNT(*) AS `질문`\n"
    "FROM turns WHERE $__timeFilter(created_at)\nGROUP BY 1",
    desc="정해진 규칙으로 답한 질문과 AI 모델이 글을 지어 답한 질문의 비율. 규칙 답은 숫자 · 조항이 정확하고 1초 안에 나온다."
         + SRC + "turns.code_rule 있음 = 규칙"), 6, 8, 18)
y += 8
add(pie("상담원 평가 (👍 / 👎)",
    "SELECT CASE rating WHEN 'up' THEN '👍' ELSE '👎' END AS `평가`, COUNT(*) AS `수`\n"
    "FROM feedback WHERE $__timeFilter(created_at)\nGROUP BY 1",
    desc="상담원이 답에 남긴 좋아요 · 싫어요 수. 평가를 남기지 않은 답은 세지 않는다. 코멘트 내용은 이 화면에서 읽지 않는다."
         + SRC + "feedback.rating"), 6, 8, 0)
PCT = ("SELECT TIMESTAMP(d) AS time,\n"
       "  MAX(CASE WHEN pr <= 0.5 THEN v END) / 1000 AS `{n} · 보통`,\n"
       "  MAX(CASE WHEN pr <= 0.9 THEN v END) / 1000 AS `{n} · 느린 편`\n"
       "FROM (SELECT DATE(created_at) AS d, {c} AS v,\n"
       "        PERCENT_RANK() OVER (PARTITION BY DATE(created_at) ORDER BY {c}) AS pr\n"
       "      FROM turns WHERE status = 'ok' AND {c} IS NOT NULL AND $__timeFilter(created_at)) x\n"
       "GROUP BY d ORDER BY d")
SLOW = ("「보통」은 그날 질문의 절반이 이보다 빨랐던 값, 「느린 편」은 10번 중 9번이 이보다 빨랐던 값(중앙값 · 90번째 백분위)."
        " 끝까지 답한 질문만 센다.")
add(ts("답변 걸린 시간 (보통 / 느린 편, 일별)", [sql(PCT.format(n="답 끝까지", c="latency_ms"), ref="A"),
                                              sql(PCT.format(n="첫 글자까지", c="first_token_ms"), ref="B")],
       unit="s",
       desc="질문을 보낸 뒤 첫 글자가 나올 때까지, 답이 끝날 때까지 걸린 시간. " + SLOW +
            " 정해진 규칙 답(1초 미만)과 AI 모델 답(수 초)이 섞여 있다. 모드를 바꾼 직후 첫 답은 모델을 바꿔 올리느라 더 걸린다."
            + SRC + "turns.latency_ms · first_token_ms"), 12, 8, 6)
add(ts("조항 검색 걸린 시간 (보통 / 느린 편, 일별)", [sql(PCT.format(n="검색", c="search_ms"), ref="A")], unit="s",
       desc="답을 만들기 전에 약관 · 인사규정에서 관련 조항을 찾는 데 걸린 시간. " + SLOW +
            " 일반 대화와 직원 본인 질문(연차 · 퇴직금 등)은 검색하지 않아 빠진다. 업무특화는 규칙으로 답한 질문도 먼저 검색하므로 들어간다."
            " 2026-11-11부터." + SRC + "turns.search_ms(search-service 호출 시간 합)"), 6, 8, 18)
y += 8

row("AI 서버 (GPU)")
add(ts("GPU 사용률", [prom('nvidia_smi_utilization_gpu_ratio * 100', "GPU {{uuid}}")], unit="percent",
       desc="AI 모델을 돌리는 그래픽카드가 일하는 비율. 답을 만드는 동안 올라가고 쉬면 0에 가깝다. 수집기를 띄우기 전에는 비어 있다."
            + SRC + "호스트 nvidia-gpu-exporter(scripts/host-gpu-exporter.sh)"), 6, 7, 0)
add(ts("GPU 메모리 사용량", [prom('nvidia_smi_memory_used_bytes', "사용"), prom('nvidia_smi_memory_total_bytes', "전체")], unit="bytes",
       desc="그래픽카드 메모리 사용량과 전체 용량. AI 모델 · 검색 모델이 여기 올라간다. 가득 차면 모델을 내리고 다시 올리느라 답이 느려진다."
            + SRC + "호스트 nvidia-gpu-exporter"), 6, 7, 6)
# 모델은 답한 뒤 5분쯤만 올라가 있다. 대시보드 기간(기본 30일)으로 그리면 한 점이 한 시간이라 막대가 뭉개지므로
# 이 패널만 최근 24시간으로 고정한다(timeFrom). max_over_time은 점 사이에 있던 짧은 적재도 빠뜨리지 않게 한다
_p = {"type": "state-timeline", "title": "메모리에 올라간 AI 모델 (최근 24시간)", "timeFrom": "24h",
      "description": "AI 모델마다 한 줄. 색 막대가 그 모델이 그래픽카드에 올라가 있던 시간이다. 오른쪽 끝까지 색이 닿아 있으면"
                     " 지금 올라가 있는 것이다. 위 기간과 상관없이 늘 최근 24시간을 보여 준다. petmint 말고 다른 클라이언트"
                     "(학교 PC 터널 등)가 올린 모델도 함께 나온다. 5분 동안 질문이 없으면 내려가고, 그 뒤 첫 답은 다시 올리느라"
                     " 몇 초 더 걸린다. 막대에 마우스를 올리면 크기가 나온다." + SRC + "Ollama /api/ps(json-exporter, 30초마다)",
      "targets": [prom('max_over_time(ollama_loaded_model_vram_bytes[$__rate_interval])', "{{model}}")],
      "fieldConfig": {"defaults": {"unit": "bytes", "color": {"mode": "palette-classic"},
                                   "custom": {"fillOpacity": 80, "lineWidth": 0}}, "overrides": []},
      "options": {"showValue": "never", "mergeValues": True, "rowHeight": 0.8, "alignValue": "left",
                  "legend": {"showLegend": False}, "tooltip": {"mode": "single"}}}
# 제목 옆에 「Last 24 hours」 표시가 붙어 제목이 잘리므로 감춘다(제목에 이미 기간이 있다). 모델 이름이 길어 이 칸을 넓힌다
_p["hideTimeOverride"] = True
add(_p, 12, 7, 12)
y += 7
add(ts("질문별로 쓴 AI 모델 (시간당)", [sql(
    "SELECT $__timeGroupAlias(created_at, '1h'), model AS metric, COUNT(*) AS value\n"
    "FROM turns WHERE $__timeFilter(created_at) AND model IS NOT NULL\nGROUP BY 1, 2 ORDER BY 1")],
    bars=True, stack=True,
    desc="일반 · 사내규정은 기본 모델(tri-7b), 업무특화는 약관으로 학습한 모델(kabyul-…)이 답한다. 모드가 섞여 들어오면 두 모델을"
         " 번갈아 올리므로 그때 답이 느려질 수 있다." + SRC + "turns.model"), 12, 7, 0)
add({"type": "logs", "title": "서버 기록 (최근 7일)", "datasource": L,
     "targets": [{"datasource": L, "expr": '{namespace="petmint", container="app"}', "refId": "A"}],
     "options": {"showTime": True, "wrapLogMessage": True, "sortOrder": "Descending"},
     "description": "챗봇 서버가 남긴 동작 기록. 오류가 났을 때 무슨 일이 있었는지 찾는 데 쓴다. 대화 내용(질문 · 답)은 들어 있지 않다."
                    + SRC + "Loki, petmint 앱 컨테이너 로그 7일 보존"}, 12, 7, 12)

dash = {"uid": "petmint-overview", "title": "petmint 운영", "tags": ["petmint"], "timezone": "browser",
        "schemaVersion": 39, "version": 1, "editable": False, "refresh": "1m",
        "time": {"from": "now-30d", "to": "now"}, "panels": panels, "templating": {"list": []}, "annotations": {"list": []}}
json.dump(dash, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
print(len(panels), "panels")

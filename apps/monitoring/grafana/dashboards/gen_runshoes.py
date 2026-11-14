# runshoes 운영 대시보드 — python3 gen_runshoes.py runshoes.json 으로 JSON 을 만든다(gen_petmint.py 와 같은 꼴).
# 2026-11-14 런슈즈 작업 세션이 쓰고 런슈즈 관리자 부탁으로 인프라가 넣었다. 데이터소스 셋: Prometheus(prometheus) · Loki(loki) ·
# 런슈즈 MySQL 복제본(runshoes-mysql, ../datasource.yaml — 읽기 계정 grafana_ro 는 앱 리포 docs/07_database.md 1-6절).
# 고칠 때는 이 파일을 고쳐 다시 만든다(python3 gen_runshoes.py runshoes.json). 아래 글쓰기 규칙을 지킨다.
# 2026-11-14 패널 폭 — 런슈즈 관리자(제목이 잘리지 않게 폭과 줄 나눔만 바꿈, 제목 · 쿼리 · 설명은 그대로)
#
# 역할 가르기(사용자 2026-11-14): Grafana 는 추세를 본다(세는 곳), 관리자 화면은 개별 건을 본다(손대는 곳).
# 숫자와 그래프는 관리자 화면에 다시 그리지 않는다.
#
# 글쓰기 규칙(사용자): 처음 보는 사람도 알게. 제목에 지표 · 칸 이름을 쓰지 않는다. 설명은 무엇을 재나 · 높거나 낮으면 무슨 뜻 ·
# 무엇이 섞였나 · 언제부터 · 출처. 「사용자 수」라는 말을 쓰지 않는다 — 「계정 수」 · 「연결 수」(체험 계정을 여럿이 함께 쓴다).
import json, sys

P = {"type": "prometheus", "uid": "prometheus"}
M = {"type": "mysql", "uid": "runshoes-mysql"}
L = {"type": "loki", "uid": "loki"}
panels, pid, y = [], 0, 0

# 비교 조합 순위 — activity_logs.meta 의 신발 번호만 꺼낸 뷰 grafana_compare_views(앱 V21, 사용자 2026-11-14 (가)).
# V21 이 운영에 오르고 grafana_ro 에 뷰 GRANT 를 준 뒤에 패널이 값을 낸다(앱 리포 docs/07_database.md 1-6절)
COMPARE_VIEW = True


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
    return {"datasource": P, "expr": expr, "legendFormat": legend, "refId": "A"}


def sql(q, fmt="time_series", ref="A"):
    return {"datasource": M, "rawSql": q, "format": fmt, "rawQuery": True, "editorMode": "code", "refId": ref}


def ts(title, targets, unit="short", desc="", bars=False, stack=False, minv=None):
    for i, t in enumerate(targets):
        t["refId"] = chr(65 + i)
    d = {"unit": unit, "custom": {"drawStyle": "bars" if bars else "line", "fillOpacity": 60 if bars else 10,
                                  "stacking": {"mode": "normal" if stack else "none"}}}
    if minv is not None:
        d["min"] = minv
    return {"type": "timeseries", "title": title, "description": desc, "targets": targets,
            "fieldConfig": {"defaults": d, "overrides": []},
            "options": {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "multi"}}}


def stat(title, targets, unit="short", desc=""):
    for i, t in enumerate(targets):
        t["refId"] = chr(65 + i)
    return {"type": "stat", "title": title, "description": desc, "targets": targets,
            "fieldConfig": {"defaults": {"unit": unit}, "overrides": []},
            "options": {"reduceOptions": {"calcs": ["lastNotNull"]}, "colorMode": "value", "graphMode": "none"}}


def bar(title, q, desc="", horizontal=False):
    return {"type": "barchart", "title": title, "description": desc, "targets": [sql(q, "table")],
            "options": {"orientation": "horizontal" if horizontal else "auto", "showValue": "auto",
                        "legend": {"showLegend": False}},
            "fieldConfig": {"defaults": {}, "overrides": []}}


def pie(title, q, desc=""):
    return {"type": "piechart", "title": title, "description": desc, "targets": [sql(q, "table")],
            "options": {"reduceOptions": {"values": True, "calcs": ["lastNotNull"]},
                        "pieType": "donut", "displayLabels": ["name", "value", "percent"],
                        "legend": {"displayMode": "list", "placement": "right"}},
            "fieldConfig": {"defaults": {}, "overrides": []}}


def logs(title, expr, desc):
    return {"type": "logs", "title": title, "datasource": L, "description": desc,
            "targets": [{"datasource": L, "expr": expr, "refId": "A"}],
            "options": {"showTime": True, "wrapLogMessage": True, "sortOrder": "Descending"}}


SRC = "\n\n출처: "
H = 'host="runshoes.ronanlab.dev"'
NS = 'namespace="runshoes"'
# 앱 Pod(Deployment runshoes)만 — DB(runshoes-mysql-0 · runshoes-mysql-replica-0)와 요약 배치(runshoes-summary-…)를 뺀다
APP_POD = 'pod=~"runshoes-.*", pod!~"runshoes-(mysql|summary).*"'
# Spring 지표(관리 포트 9000, A-2 3단계) — 프로브가 5초 · 20초마다 부르는 상태 주소는 요청 수에서 뺀다
SPRING = f'{NS}, job="kubernetes-pods"'
NOPROBE = 'uri!~"/livez|/readyz|/actuator.*"'

# 챗봇 갈래(chatbot router.BRANCHES 와 Reply(branch=…), 앱 리포 docs/09_chatbot_rag.md 18절). 모르는 값은 그대로 나온다
BRANCH_NAMES = [
    ("term", "용어"), ("spec", "스펙"), ("compare", "비교"), ("recommend", "추천"), ("explain", "특성 설명"),
    ("experience", "경험·후기"), ("out_of_scope", "범위 밖"), ("greeting", "인사"),
    ("choose", "어느 신발인지 되물음"), ("no_shoe", "등록 안 된 신발"), ("error", "오류로 끝남"),
]
BRANCH_CASE = "CASE branch " + " ".join(f"WHEN '{k}' THEN '{v}'" for k, v in BRANCH_NAMES) + " ELSE branch END"
TURNS_FROM = "2026년 11월 14일(턴 기록이 운영에 오른 날)부터 집계"
# 체험 계정 — 시드 사용자 30(id 1~30, V3 가 id 를 정해 넣는다)과 데모 관리자(role DEMO_ADMIN). 이메일은 보지 않는다(권한도 없다)
DEMO = "(a.user_id BETWEEN 1 AND 30 OR u.role = 'DEMO_ADMIN')"
ACT_NOTE = (" 활동 기록은 지우지 않고 쌓이기만 한다(정리 작업이 Pod 두 대에서 겹치지 않게 2026-11-10부터 꺼 두었다)."
            " 로그인 기능이 들어간 2026-10-21부터 있다.")

# ───────────────────────── 1. 서비스 상태 ─────────────────────────
row("서비스 상태")
add(stat("응답 가능한 앱 서버 수 (정상 2)",
         [prom(f'sum(kube_pod_status_ready{{{NS},condition="true",{APP_POD}}})')],
         desc="웹 화면 · API · 챗봇을 함께 돌리는 앱 서버 2대 중 지금 요청을 받을 수 있는 수. 2가 정상, 1이면 한 대가 재시작 중이거나"
              " 고장, 0이면 사이트가 멈춘 것. 배포 중에는 한 대씩 바꾸므로 잠깐 1이 된다(그동안 남은 한 대가 받는다)."
              " DB가 멈춰도 0이 된다 — 앱 서버는 DB까지 붙어야 준비된 것으로 친다." + SRC + "kube-state-metrics, 앱 Pod Ready"), 7, 6, 0)
add(stat("서버 재시작 횟수 (최근 24시간)",
         [prom(f'sum(increase(kube_pod_container_status_restarts_total{{{NS}}}[24h]))')],
         desc="앱 · 챗봇 · DB · 요약 배치가 오류나 메모리 초과로 꺼졌다가 스스로 다시 켜진 횟수. 0이 정상."
              " 배포로 서버를 새것으로 바꾸는 것은 세지 않는다." + SRC + "kube-state-metrics, runshoes 네임스페이스 컨테이너 재시작 합"), 7, 6, 7)
add(ts("접속 요청량 (초당, 결과별)",
       [prom(f'sum(rate(nginx_ingress_controller_requests{{{H},status=~"[123].."}}[5m]))', "정상(100 · 200 · 300번대)"),
        prom(f'sum(rate(nginx_ingress_controller_requests{{{H},status="404"}}[5m]))', "없는 주소(404)"),
        prom(f'sum(rate(nginx_ingress_controller_requests{{{H},status=~"4..",status!="404"}}[5m]))', "그 밖 요청 쪽 문제(400번대)"),
        prom(f'sum(rate(nginx_ingress_controller_requests{{{H},status=~"5.."}}[5m]))', "서버 오류(500번대)")],
       unit="reqps", stack=True,
       desc="바깥(브라우저)에서 들어온 요청 수를 결과별로. 400번대에는 로그인하지 않고 쓰기를 누른 것(401)이 섞인다."
            " 챗봇 대화창은 질문 수가 아니라 연결 한 번이 1건이다(연결이 끝날 때 101로 센다) — 질문 수는 아래 「챗봇」 묶음."
            + SRC + "ingress-nginx(입구에서 센다 — 사이트 안 지표는 「API」 묶음)"), 10, 6, 14)
y += 6   # 제목이 잘리지 않게 줄을 나눔(2026-11-14 사용자)
add(ts("서버 오류 비율",
       # 500번대가 없으면 그 줄이 없어 나눗셈이 비므로 or vector(0)
       [prom(f'(sum(rate(nginx_ingress_controller_requests{{{H},status=~"5.."}}[5m])) or vector(0))'
             f' / clamp_min(sum(rate(nginx_ingress_controller_requests{{{H}}}[5m])), 1e-9)', "서버 오류")],
       unit="percentunit", minv=0,
       desc="전체 요청 중 서버 오류(500번대)의 비율. 0%가 정상. 배포 중 잠깐, 또는 DB가 멈췄을 때 올라간다."
            " 챗봇이 답을 못 만든 것은 여기 안 잡히고 「챗봇」 묶음의 「오류로 끝남」 갈래에 나온다." + SRC + "ingress-nginx 5xx / 전체"),
    12, 7, 0)
add(ts("CPU 사용량 (컨테이너별)",
       [prom(f'sum by (pod, container) (rate(container_cpu_usage_seconds_total{{{NS},container=~"runshoes|chatbot|mysql"}}[5m]))',
             "{{container}} · {{pod}}")],
       unit="none",
       desc="CPU 몇 개만큼 쓰고 있나(1 = 코어 하나를 꽉 채움). runshoes = 웹 화면 · API(Spring), chatbot = 챗봇,"
            " mysql = DB(runshoes-mysql-0이 원본, replica가 대시보드가 읽는 복제본). 챗봇은 답 글을 GPU 서버의 AI 모델이 만들어"
            " 여기서는 적게 나온다. 요약 배치(하루 한 번)는 빠져 있다." + SRC + "kubelet cAdvisor"), 12, 7, 12)
y += 7   # 제목이 잘리지 않게 줄을 나눔(2026-11-14 사용자)
add(ts("메모리 사용량 (상한 대비)",
       [prom(f'max by (pod, container) (container_memory_working_set_bytes{{{NS},container=~"runshoes|chatbot|mysql"}})'
             f' / on (pod, container) max by (pod, container) (kube_pod_container_resource_limits{{{NS},resource="memory"}})',
             "{{container}} · {{pod}}")],
       unit="percentunit", minv=0,
       desc="컨테이너마다 쓰는 메모리를 상한으로 나눈 값. 100%에 닿으면 그 컨테이너는 강제로 꺼지고 다시 켜진다(재시작 횟수에 잡힌다)."
            " 상한: 앱 1GiB · 챗봇 256MiB · DB 1GiB. 앱(Java)은 처음부터 일정량을 잡고 쓰므로 50~60%대가 보통이다."
            + SRC + "kubelet cAdvisor(쓰는 메모리) / kube-state-metrics(상한)"), 12, 7, 0)
add(ts("챗봇 메모리 (상한 256MiB)",
       [prom(f'max by (pod) (container_memory_working_set_bytes{{{NS},container="chatbot"}})', "{{pod}}"),
        prom(f'max(kube_pod_container_resource_limits{{{NS},container="chatbot",resource="memory"}})', "상한")],
       unit="bytes", minv=0,
       desc="챗봇이 쓰는 메모리. 2026-11-14까지 잰 가장 큰 값은 83MiB였다. 배포 사이에 계속 오르기만 하면 어딘가 쌓이고 있는 것이다"
            "(카탈로그 · 검색 색인을 메모리에 들고 있다). 배포하면 처음부터 다시 잰다." + SRC + "kubelet cAdvisor"), 12, 7, 12)
y += 7

# ───────────────────────── 2. API(Spring) ─────────────────────────
row("API (웹 화면 · 챗봇이 부르는 서버)")
add(ts("주소별 요청 수 (초당)",
       [prom(f'sum by (method, uri) (rate(http_server_requests_seconds_count{{{SPRING},{NOPROBE}}}[5m]))', "{{method}} {{uri}}")],
       unit="reqps", stack=True,
       desc="API 주소별 요청 수(두 서버 합). /api/{name}은 신발 · 리뷰 · 용어 목록처럼 같은 꼴의 주소를 묶은 것이고,"
            " /**는 화면 파일(index.html 등)이다. 챗봇이 서버 안에서 부르는 것(카탈로그 · 비교 · 추천 · 리뷰)도 여기 들어간다."
            " 서버 상태 확인(/livez · /readyz)은 뺐다." + SRC + "Spring Boot 지표(관리 포트 9000, 2026-11-14 배포부터)"), 8, 8, 0)
HQ = "histogram_quantile({q}, sum by (le) (rate(http_server_requests_seconds_bucket{{" + SPRING + "," + NOPROBE + "}}[5m])))"
add(ts("응답 시간 (보통 / 느린 편, 어림값)",
       [prom(HQ.format(q=0.5), "보통(절반이 이보다 빠름)"), prom(HQ.format(q=0.95), "느린 편(20번 중 19번이 이보다 빠름)")],
       unit="s", minv=0,
       desc="서버가 요청을 받아 답을 보내기까지. 시간 구간을 50ms · 100ms · 300ms · 1초 넷으로만 센다 — 그래서 이 값은 구간 사이를"
            " 직선으로 이은 어림값이다(예: 실제 120ms든 280ms든 100~300ms 사이 어딘가로 나온다). 1초가 넘는 요청은 1초 이상이라는 것만 안다 — 오른쪽 패널."
            " 구간을 더 잘게 나누면 시계열이 크게 늘어 넷만 두었다." + SRC + "http_server_requests 버킷(Spring, 9000)"), 8, 8, 8)
add(ts("1초 넘게 걸린 요청 비율",
       [prom(f'1 - sum(rate(http_server_requests_seconds_bucket{{{SPRING},{NOPROBE},le="1.0"}}[5m]))'
             f' / clamp_min(sum(rate(http_server_requests_seconds_count{{{SPRING},{NOPROBE}}}[5m])), 1e-9)', "1초 넘음")],
       unit="percentunit", minv=0,
       desc="API 요청 중 1초보다 오래 걸린 비율. 어림값이 아니라 센 값이다. 0%에 가까워야 한다." + SRC + "http_server_requests 버킷 le=1.0"), 8, 8, 16)
y += 8
add(ts("API 오류 비율 (요청 쪽 / 서버 쪽)",
       [prom(f'(sum(rate(http_server_requests_seconds_count{{{SPRING},{NOPROBE},status=~"4.."}}[5m])) or vector(0))'
             f' / clamp_min(sum(rate(http_server_requests_seconds_count{{{SPRING},{NOPROBE}}}[5m])), 1e-9)', "요청 쪽(400번대)"),
        prom(f'(sum(rate(http_server_requests_seconds_count{{{SPRING},{NOPROBE},status=~"5.."}}[5m])) or vector(0))'
             f' / clamp_min(sum(rate(http_server_requests_seconds_count{{{SPRING},{NOPROBE}}}[5m])), 1e-9)', "서버 쪽(500번대)")],
       unit="percentunit", minv=0,
       desc="API 요청 중 오류로 끝난 비율. 400번대(요청 쪽)에는 로그인 없이 쓰기를 누른 것 · 없는 신발 주소 · 로그인 실패가 섞여 늘 조금 있다."
            " 500번대(서버 쪽)는 0%가 정상." + SRC + "http_server_requests status(Spring, 9000)"), 8, 7, 0)
add(ts("DB 연결 (쓰는 중 / 쉬는 중 / 기다리는 요청)",
       [prom(f'sum by (pod) (hikaricp_connections_active{{{SPRING}}})', "쓰는 중 · {{pod}}"),
        prom(f'sum by (pod) (hikaricp_connections_idle{{{SPRING}}})', "쉬는 중 · {{pod}}"),
        prom(f'sum by (pod) (hikaricp_connections_pending{{{SPRING}}})', "연결을 기다리는 요청 · {{pod}}")],
       unit="short", minv=0,
       desc="앱 서버 한 대가 DB에 미리 열어 둔 연결(한 대에 최대 5개). 「쓰는 중」이 5에 붙고 「기다리는 요청」이 0보다 크면"
            " DB 연결이 모자라 요청이 줄을 서는 것이다." + SRC + "HikariCP 지표(Spring, 9000)"), 8, 7, 8)
add(ts("자바 메모리 (힙, 서버별)",
       [prom(f'sum by (pod) (jvm_memory_used_bytes{{{SPRING},area="heap"}})', "쓰는 중 · {{pod}}"),
        prom(f'sum by (pod) (clamp_min(jvm_memory_max_bytes{{{SPRING},area="heap"}}, 0))', "최대 · {{pod}}")],
       unit="bytes", minv=0,
       desc="앱 서버(Java)가 데이터를 담는 메모리. 톱니 모양(오르다 뚝 떨어짐)이 정상이다 — 떨어지는 곳이 쓰레기 정리(GC)."
            " 떨어진 바닥이 계속 올라가면 무언가 쌓이고 있는 것이다." + SRC + "JVM 지표(Spring, 9000)"), 8, 7, 16)
y += 7

# ───────────────────────── 3. 챗봇 ─────────────────────────
row("챗봇")
add(ts("갈래별 질문 수 (시간당)", [sql(
    f"SELECT $__timeGroupAlias(created_at, '1h'), {BRANCH_CASE} AS metric, COUNT(*) AS value\n"
    "FROM chatbot_turns\nWHERE $__timeFilter(created_at)\nGROUP BY 1, 2 ORDER BY 1")], bars=True, stack=True,
    desc="챗봇이 받은 질문을 무엇을 묻는 질문으로 보았나(갈래)별로 센다. 되물음에 「네」로 답한 것도 질문 하나다."
         " 체험 계정을 여럿이 함께 쓰므로 질문한 사람 수는 알 수 없다. " + TURNS_FROM + "." + SRC + "chatbot_turns.branch"), 8, 8, 0)
add(ts("대화 연결 수와 질문한 계정 수 (일별)", [sql(
    "SELECT $__timeGroupAlias(created_at, '1d'), COUNT(DISTINCT conn_id) AS `대화 연결`, COUNT(DISTINCT user_id) AS `질문한 계정`\n"
    "FROM chatbot_turns\nWHERE $__timeFilter(created_at)\nGROUP BY 1 ORDER BY 1")], bars=True,
    desc="대화 연결 = 챗봇 창을 열어 대화한 횟수(창을 닫거나 새로 고치면 새 연결). 질문한 계정 = 그날 질문한 로그인 계정 수."
         " 체험 계정 31개를 여러 사람이 함께 쓰므로 계정 수는 사람 수가 아니다. " + TURNS_FROM + "."
         + SRC + "chatbot_turns.conn_id · user_id"), 8, 8, 8)
add(pie("갈래를 정한 방식: 규칙 / AI 판단",
    "SELECT CASE WHEN by_rule = 1 THEN '규칙(낱말로 바로)' WHEN by_rule = 0 THEN 'AI 판단(라우터)' ELSE '판단 안 함(되물음에 답)' END AS `방식`,\n"
    "  COUNT(*) AS `질문`\nFROM chatbot_turns WHERE $__timeFilter(created_at)\nGROUP BY 1",
    desc="질문이 무엇을 묻는지(갈래)를 정해진 규칙이 바로 정했나, AI 모델(라우터)이 읽고 정했나. 규칙은 1초 안에 끝나고,"
         " AI 판단은 1초쯤 더 걸린다(아래 「단계별 시간」의 라우터). 되물음에 「네」로 답한 것은 판단하지 않는다. " + TURNS_FROM + "."
         + SRC + "chatbot_turns.by_rule"), 8, 8, 16)
y += 8
add(ts("AI 판단이 틀린 형식으로 온 횟수 (일별)", [sql(
    "SELECT $__timeGroupAlias(created_at, '1d'), SUM(llm_ok = 0) AS `형식 틀림`\n"
    "FROM chatbot_turns\nWHERE llm_ok IS NOT NULL AND $__timeFilter(created_at)\nGROUP BY 1 ORDER BY 1")], bars=True,
    desc="AI 모델(라우터)에게 갈래를 물었는데 약속한 꼴(JSON)로 답하지 않은 횟수. 0이 정상. 이때 챗봇은 규칙만으로 갈래를 정한다 —"
         " 늘면 AI 모델이 바뀌었거나 GPU 서버가 바빠 답이 잘린 것일 수 있다. " + TURNS_FROM + "." + SRC + "chatbot_turns.llm_ok"), 12, 7, 0)
add(ts("코드가 대신 쓴 답 비율 · 통증 질문 비율 (일별)", [sql(
    "SELECT $__timeGroupAlias(created_at, '1d'), AVG(fallback_used) AS `코드가 대신 쓴 답`, AVG(health = 1) AS `통증 · 몸 이야기 질문`\n"
    "FROM chatbot_turns\nWHERE $__timeFilter(created_at)\nGROUP BY 1 ORDER BY 1")], unit="percentunit", minv=0,
    desc="코드가 대신 쓴 답 = AI 모델이 쓴 답이 검사(숫자가 맞나, 없는 말을 지어냈나 등)에 걸려 프로그램이 정해진 꼴로 다시 쓴 답의 비율."
         " 높아지면 AI 답의 품질이 떨어진 것이다. 통증 · 몸 이야기 질문 = 아프다 · 다쳤다는 질문의 비율(이때 전문의 안내를 붙인다)."
         " 판단하지 않은 턴(되물음에 답)은 통증 쪽 분모에 0으로 들어간다. " + TURNS_FROM + "." + SRC + "chatbot_turns.fallback_used · health"), 12, 7, 12)
y += 7   # 제목이 잘리지 않게 넷을 두 줄로(2026-11-14 사용자)
PCT = ("SELECT TIMESTAMP(d) AS time,\n"
       "  MAX(CASE WHEN pr <= 0.5 THEN v END) / 1000 AS `보통`,\n"
       "  MAX(CASE WHEN pr <= 0.95 THEN v END) / 1000 AS `느린 편`\n"
       "FROM (SELECT DATE(created_at) AS d, latency_ms AS v,\n"
       "        PERCENT_RANK() OVER (PARTITION BY DATE(created_at) ORDER BY latency_ms) AS pr\n"
       "      FROM chatbot_turns WHERE branch <> 'error' AND $__timeFilter(created_at)) x\n"
       "GROUP BY d ORDER BY d")
add(ts("챗봇 답 걸린 시간 (보통 / 느린 편, 일별)", [sql(PCT)], unit="s", minv=0,
       desc="질문을 받아 답을 다 만들기까지(화면으로 보내는 시간은 빠진다). 「보통」은 그날 질문의 절반이 이보다 빨랐던 값,"
            " 「느린 편」은 20번 중 19번이 이보다 빨랐던 값. 오류로 끝난 질문은 뺐다. 인사 · 용어처럼 AI가 짧게 답하는 질문(1초 안팎)과"
            " 경험·후기처럼 리뷰를 읽는 질문(수 초)이 섞여 있다. GPU 서버에서 모델이 내려가 있었으면 첫 답이 몇 초 더 걸린다. "
            + TURNS_FROM + "." + SRC + "chatbot_turns.latency_ms"), 12, 7, 0)
add(ts("신발을 하나도 못 보여준 답 비율 (갈래별, 일별)", [sql(
    f"SELECT $__timeGroupAlias(created_at, '1d'), {BRANCH_CASE} AS metric, AVG(shoe_count = 0) AS value\n"
    "FROM chatbot_turns\nWHERE branch IN ('spec', 'compare', 'recommend', 'experience', 'no_shoe') AND $__timeFilter(created_at)\n"
    "GROUP BY 1, 2 ORDER BY 1")], unit="percentunit", minv=0,
    desc="신발을 보여 줘야 하는 갈래(스펙 · 비교 · 추천 · 경험·후기)에서 답에 신발 버튼을 하나도 붙이지 못한 비율."
         " 「등록 안 된 신발」은 늘 100%다 — 카탈로그에 없는 신발을 물은 것이라, 이 갈래의 질문 수가 늘면 카탈로그에 없는 신발을 많이 묻는다는 뜻이다."
         " 용어 · 인사 · 범위 밖은 원래 신발이 없어 뺐다. " + TURNS_FROM + "." + SRC + "chatbot_turns.shoe_count · branch"), 12, 7, 12)
y += 7
STAGES = [("router_ms", "질문 판단(라우터)"), ("search_ms", "리뷰 검색"), ("gen_ms", "답 쓰기(AI)"),
          ("catalog_ms", "API: 카탈로그"), ("compare_ms", "API: 비교"), ("recommend_ms", "API: 추천"),
          ("review_ms", "API: 리뷰"), ("summary_ms", "API: 요약")]
add(ts("답 하나에 든 시간, 단계별 평균 (일별)", [sql(
    "SELECT $__timeGroupAlias(created_at, '1d'),\n  "
    + ",\n  ".join(f"AVG({c}) / 1000 AS `{n}`" for c, n in STAGES)
    + "\nFROM chatbot_turns\nWHERE branch <> 'error' AND $__timeFilter(created_at)\nGROUP BY 1 ORDER BY 1")],
    unit="s", stack=True, bars=True, minv=0,
    desc="답 하나를 만드는 동안 어느 단계에 시간이 들었나. 쌓은 높이가 평균 답 시간과 거의 같다(단계 밖의 프로그램 시간은 몇 ms)."
         " 그 단계를 쓰지 않은 질문은 0으로 넣어 평균을 냈다 — 예: 비교 API는 비교 질문에서만 시간이 든다."
         " 「질문 판단」 · 「답 쓰기」가 GPU 서버의 AI 모델이고 「API」 다섯은 같은 서버 안의 Spring을 부른 시간이다."
         " 카탈로그는 신발 목록이 바뀌었을 때만 다시 읽는다. " + TURNS_FROM + "." + SRC + "chatbot_turns 의 단계별 시간 칸 8개"), 24, 8, 0)
y += 8

# ───────────────────────── 4. GPU ─────────────────────────
row("AI 서버 (GPU — 펫퍼민트와 나눠 쓴다)")
add(ts("GPU 사용률", [prom('nvidia_smi_utilization_gpu_ratio', "GPU")], unit="percentunit", minv=0,
       desc="AI 모델을 돌리는 그래픽카드가 일하는 비율. 답을 만드는 동안 올라가고 쉬면 0에 가깝다."
            " 런슈즈 챗봇 · 리뷰 요약과 펫퍼민트 상담이 한 장을 함께 쓴다 — 누가 쓰는지는 오른쪽 「메모리에 올라간 AI 모델」로 가른다."
            + SRC + "호스트 nvidia-gpu-exporter"), 6, 7, 0)
add(ts("GPU 메모리 (쓴 것 / 전체)", [prom('nvidia_smi_memory_used_bytes', "쓴 것"), prom('nvidia_smi_memory_total_bytes', "전체")],
       unit="bytes", minv=0,
       desc="그래픽카드 메모리(16GiB)를 얼마나 쓰고 있나. 런슈즈 챗봇 모델(gemma4:e4b) · 펫퍼민트 모델 · 리뷰 검색용 임베딩 모델이 여기 올라간다."
            " 가득 차면 한쪽 모델을 내리고 다른 쪽을 올리느라 답이 몇 초 늦어진다." + SRC + "호스트 nvidia-gpu-exporter"), 6, 7, 6)
_p = {"type": "state-timeline", "title": "메모리에 올라간 AI 모델 (최근 24시간)", "timeFrom": "24h", "hideTimeOverride": True,
      "description": "AI 모델마다 한 줄, 색 막대가 그 모델이 그래픽카드에 올라가 있던 시간이다. 런슈즈 챗봇 · 리뷰 요약은 gemma4:e4b,"
                     " 그 밖은 펫퍼민트나 다른 클라이언트가 올린 것이다. 막대가 번갈아 끊기면 두 서비스가 모델을 서로 내렸다 올린 것이고,"
                     " 그때 첫 답이 늦어진다. 5분 동안 쓰지 않으면 내려간다. 위 기간과 상관없이 최근 24시간."
                     + SRC + "Ollama /api/ps(json-exporter, 30초마다)",
      "targets": [prom('max_over_time(ollama_loaded_model_vram_bytes[$__rate_interval])', "{{model}}")],
      "fieldConfig": {"defaults": {"unit": "bytes", "color": {"mode": "palette-classic"},
                                   "custom": {"fillOpacity": 80, "lineWidth": 0}}, "overrides": []},
      "options": {"showValue": "never", "mergeValues": True, "rowHeight": 0.8, "alignValue": "left",
                  "legend": {"showLegend": False}, "tooltip": {"mode": "single"}}}
add(_p, 12, 7, 12)
y += 7

# ───────────────────────── 5. 사이트 활동 ─────────────────────────
row("사이트 활동")
ACT = "FROM activity_logs a LEFT JOIN users u ON u.id = a.user_id\n"
add(ts("리뷰 쓰기 (일별, 체험 계정 / 그 밖의 계정)", [sql(
    f"SELECT $__timeGroupAlias(a.occurred_at, '1d'), CASE WHEN {DEMO} THEN '체험 계정' ELSE '그 밖의 계정(직접 가입 · 관리자)' END AS metric, COUNT(*) AS value\n"
    + ACT + "WHERE a.event = 'review.create' AND $__timeFilter(a.occurred_at)\nGROUP BY 1, 2 ORDER BY 1")], bars=True, stack=True,
    desc="화면에서 새로 쓴 리뷰 수. 체험 계정(로그인 화면의 체험 카드 31개 — 여러 사람이 함께 쓴다)과 직접 가입한 계정을 나눈다."
         " 처음에 넣어 둔 예시 리뷰(약 1,500건)는 화면으로 쓴 것이 아니라 들어 있지 않다." + ACT_NOTE
         + SRC + "activity_logs(review.create) · users.role"), 8, 7, 0)
add(ts("찜과 「도움이 돼요」 (일별)", [sql(
    "SELECT $__timeGroupAlias(occurred_at, '1d'),\n"
    "  SUM(event = 'like.add') AS `찜`, SUM(event = 'like.remove') AS `찜 취소`,\n"
    "  SUM(event = 'review_like.add') AS `도움이 돼요`, SUM(event = 'review_like.remove') AS `도움이 돼요 취소`\n"
    "FROM activity_logs\nWHERE event IN ('like.add', 'like.remove', 'review_like.add', 'review_like.remove') AND $__timeFilter(occurred_at)\n"
    "GROUP BY 1 ORDER BY 1")], bars=True,
    desc="신발 찜과 리뷰의 「도움이 돼요」를 누른 수 · 취소한 수. 체험 계정이 누른 것이 섞여 있다." + ACT_NOTE
         + SRC + "activity_logs(like.* · review_like.*)"), 8, 7, 8)
add(ts("가입과 탈퇴 (일별)", [sql(
    "SELECT $__timeGroupAlias(occurred_at, '1d'), SUM(event = 'auth.signup') AS `가입`, SUM(event = 'user.withdraw') AS `탈퇴`\n"
    "FROM activity_logs\nWHERE event IN ('auth.signup', 'user.withdraw') AND $__timeFilter(occurred_at)\nGROUP BY 1 ORDER BY 1")], bars=True,
    desc="새로 가입한 계정 수와 탈퇴한 계정 수. 체험 계정은 탈퇴할 수 없어 들어 있지 않다." + ACT_NOTE
         + SRC + "activity_logs(auth.signup · user.withdraw)"), 8, 7, 16)
y += 7
add(ts("로그인 (일별, 성공 / 실패 / 차단)", [sql(
    "SELECT $__timeGroupAlias(occurred_at, '1d'),\n"
    "  SUM(event = 'auth.login.success') AS `성공`, SUM(event = 'auth.login.failure') AS `실패(비밀번호 틀림 등)`,\n"
    "  SUM(event = 'auth.login.blocked') AS `차단(너무 많이 틀림)`\n"
    "FROM activity_logs\nWHERE event IN ('auth.login.success', 'auth.login.failure', 'auth.login.blocked') AND $__timeFilter(occurred_at)\n"
    "GROUP BY 1 ORDER BY 1")], bars=True,
    desc="이메일 · 비밀번호로 한 로그인. 차단 = 같은 계정이 15분에 5번, 또는 같은 곳(IP)에서 15분에 20번 틀려 잠시 막힌 것."
         " 실패 · 차단이 갑자기 늘면 비밀번호를 마구 넣어 보는 시도일 수 있다. 체험 카드로 들어온 것은 오른쪽에 따로 센다." + ACT_NOTE
         + SRC + "activity_logs(auth.login.*)"), 12, 7, 0)
add(ts("체험 로그인 (일별)", [sql(
    "SELECT $__timeGroupAlias(occurred_at, '1d'), SUM(event = 'auth.demo_login') AS `체험 로그인`, SUM(event = 'auth.demo_login.blocked') AS `막힘(같은 곳에서 너무 많이)`\n"
    "FROM activity_logs\nWHERE event IN ('auth.demo_login', 'auth.demo_login.blocked') AND $__timeFilter(occurred_at)\nGROUP BY 1 ORDER BY 1")],
    bars=True,
    desc="로그인 화면의 체험 카드(시드 계정 30 · 관리자 체험 1)를 눌러 들어온 수. 비밀번호 없이 둘러보는 방문이 얼마나 되는지 본다."
         " 같은 곳(IP)에서 15분에 30번을 넘으면 막힌다." + ACT_NOTE + SRC + "activity_logs(auth.demo_login*)"), 12, 7, 12)
y += 7
# model 에 세대 숫자가 이미 들어 있다(「클리프톤 10」 — 숫자가 없는 첫 세대는 generation 1). 2026-11 카탈로그는 모두 men 이라 여성일 때만 붙인다
SHOE_NAME = "CONCAT(s.brand, ' ', s.model, IF(s.gender = 'women', ' (여성)', ''))"
add(bar("많이 본 신발 (상위 10)",
    f"SELECT {SHOE_NAME} AS `신발`, COUNT(*) AS `조회`\n"
    "FROM activity_logs a JOIN shoes s ON s.id = a.target_id\n"
    "WHERE a.event = 'shoe.view' AND $__timeFilter(a.occurred_at)\nGROUP BY s.id, 1 ORDER BY 2 DESC LIMIT 10",
    horizontal=True,
    desc="고른 기간에 상세 화면을 많이 연 신발. 로그인한 계정만 센다(로그인하지 않은 방문은 기록이 없다)."
         " 같은 계정이 같은 신발을 30분 안에 다시 연 것은 한 번으로 센다. 영구 삭제한 신발은 빠진다." + ACT_NOTE
         + SRC + "activity_logs(shoe.view) · shoes 이름"), 12 if COMPARE_VIEW else 24, 8, 0)
if COMPARE_VIEW:
    # shoe_ids 는 글("[2, 16]", 번호 오름차순)이라 JSON 으로 바꿔 펼친 뒤 이름을 붙인다. 비교 한 번 = 뷰 한 줄
    add(bar("많이 비교한 조합 (상위 10)",
        "SELECT names AS `신발 조합`, COUNT(*) AS `비교`\nFROM (\n"
        f"  SELECT v.id, GROUP_CONCAT({SHOE_NAME} ORDER BY s.id SEPARATOR ' · ') AS names\n"
        "  FROM grafana_compare_views v\n"
        "  JOIN JSON_TABLE(CAST(v.shoe_ids AS JSON), '$[*]' COLUMNS (shoe_id BIGINT PATH '$')) j\n"
        "  JOIN shoes s ON s.id = j.shoe_id\n"
        "  WHERE $__timeFilter(v.occurred_at)\n  GROUP BY v.id) x\n"
        "GROUP BY names ORDER BY 2 DESC LIMIT 10", horizontal=True,
        desc="비교하기에서 함께 본 신발 조합(2~5켤레). 로그인한 계정만 센다(로그인하지 않은 비교는 기록이 없다)."
             " 같은 계정이 같은 조합을 30분 안에 다시 본 것은 한 번으로 센다. 영구 삭제한 신발은 조합 이름에서 빠진다."
             + ACT_NOTE
             + SRC + "activity_logs(compare.view)의 신발 번호만 꺼낸 뷰 grafana_compare_views(V21) · shoes 이름"), 12, 8, 12)
y += 8

# ───────────────────────── 6. 배치 ─────────────────────────
row("리뷰 요약 배치 (하루 한 번)")
add(ts("요약 배치 걸린 시간 (회차별)", [sql(
    "SELECT started_at AS time, duration_ms / 60000 AS `걸린 시간(분)`\n"
    "FROM summary_batch_runs\nWHERE result = 'ran' AND $__timeFilter(started_at)\nORDER BY 1")], unit="m", bars=True, minv=0,
    desc="리뷰 요약(신발마다 좋은 점 · 아쉬운 점)을 AI 모델로 다시 만드는 배치가 한 번 도는 데 걸린 시간. 리뷰가 바뀐 신발만 만들므로"
         " 바뀐 신발이 많은 날 길어진다. GPU를 펫퍼민트와 나눠 써서 그쪽이 바쁘면 늘어난다. 2026-11-14 배포부터 기록." + SRC + "summary_batch_runs.duration_ms"), 8, 7, 0)
add(ts("요약 만든 켤레 · 실패한 켤레 (회차별)", [sql(
    "SELECT started_at AS time, ok AS `만든 켤레`, failed AS `실패한 켤레`, target AS `만들 대상`\n"
    "FROM summary_batch_runs\nWHERE result = 'ran' AND $__timeFilter(started_at)\nORDER BY 1")], bars=True, minv=0,
    desc="그 회차에 요약을 새로 만든 신발 수와 만들지 못한 수. 실패한 신발은 다음 회차가 다시 만든다 — 실패가 며칠 이어지면"
         " AI 서버(Ollama)에 닿지 않는지 본다(까닭은 관리자 화면 · 로그). 2026-11-14 배포부터 기록." + SRC + "summary_batch_runs.ok · failed · target"), 8, 7, 8)
add(ts("끝나지 못한 회차 (일별)", [sql(
    "SELECT $__timeGroupAlias(started_at, '1d'),\n"
    "  SUM(result = 'running' AND started_at < UTC_TIMESTAMP() - INTERVAL 3 HOUR) AS `중간에 죽음`,\n"
    "  SUM(result = 'error') AS `오류로 멈춤`, SUM(result = 'skipped') AS `건너뜀(다른 회차가 도는 중)`\n"
    "FROM summary_batch_runs\nWHERE $__timeFilter(started_at)\nGROUP BY 1 ORDER BY 1")], bars=True, minv=0,
    desc="정상으로 끝나지 않은 회차. 중간에 죽음 = 시작 기록만 있고 끝 기록이 없는 채 3시간이 지난 것(배치가 메모리 초과 등으로 강제로 꺼졌다)."
         " 오류로 멈춤 = 배치가 오류를 알고 멈춘 것. 건너뜀 = 앞 회차가 아직 돌고 있어 이번에는 하지 않은 것. 모두 0이 정상."
         " 2026-11-14 배포부터 기록." + SRC + "summary_batch_runs.result"), 8, 7, 16)
y += 7

# ───────────────────────── 7. 로그 ─────────────────────────
row("서버 기록 (최근 7일)")
add(logs("챗봇 기록", '{namespace="runshoes", container="chatbot"}',
         "챗봇이 남긴 동작 기록(검색 색인 동기화 · 오류 등). 질문 원문 줄은 수집기에서 버려 들어 있지 않다."
         + SRC + "Loki, runshoes 챗봇 컨테이너 로그 7일 보존"), 12, 8, 0)
add(logs("앱(Spring) · 요약 배치 기록", '{namespace="runshoes", container=~"runshoes|summary"}',
         "웹 화면 · API 서버와 요약 배치의 기록. 오류가 났을 때 무슨 일이 있었는지 찾는 데 쓴다." + SRC + "Loki, runshoes 앱 · summary 컨테이너 로그 7일 보존"),
    12, 8, 12)

dash = {"uid": "runshoes-overview", "title": "runshoes 운영", "tags": ["runshoes"], "timezone": "browser",
        "description": "Grafana 는 추세를 본다(세는 곳), 관리자 화면은 개별 건을 본다(손대는 곳). 숫자와 그래프는 관리자 화면에 다시 그리지 않는다.",
        "schemaVersion": 39, "version": 1, "editable": False, "refresh": "1m",
        "time": {"from": "now-7d", "to": "now"}, "panels": panels, "templating": {"list": []}, "annotations": {"list": []}}
json.dump(dash, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
print(len(panels), "panels")

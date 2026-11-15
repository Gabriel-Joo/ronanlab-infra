<!--
다루는 곳: apps/monitoring/grafana/
읽은 커밋: e8e24ea
-->
# 대시보드

대시보드는 여러 지표와 로그를 그래프와 숫자 칸으로 한 화면에 모은 것이다. 이 클러스터에서는 Grafana 한 대가 대시보드를 그린다. Grafana는 스스로 데이터를 모으지 않는다. 데이터소스(Grafana가 값을 물어보러 가는 곳)에 쿼리를 보내 받은 값을 그릴 뿐이다. Grafana도 다른 모니터링 구성처럼 w4에 뜬다. [code:apps/monitoring/grafana/deployment.yaml:17-18]

## 화면도 설정도 저장소에서 온다

Grafana는 저장 공간을 따로 갖지 않는다. 파드 안의 데이터 폴더는 파드가 사라지면 함께 사라지는 임시 볼륨이다. [code:apps/monitoring/grafana/deployment.yaml:83-85] 그 대신 데이터소스와 대시보드를 기동할 때마다 저장소의 파일에서 읽어 들인다(프로비저닝). [code:apps/monitoring/grafana/deployment.yaml:1-2] 화면에서 데이터소스나 대시보드를 고쳐도 남지 않는다. 데이터소스는 다시 시작하면 파일의 값으로 돌아가고, 대시보드는 화면에서 고치는 것 자체를 막아 두었다. [code:apps/monitoring/grafana/datasource.yaml:1] [code:apps/monitoring/grafana/dashboard-provider.yaml:11-16]

이렇게 한 것은 무엇이 어떻게 설정됐는지를 클러스터 안이 아니라 저장소에 남기기 위해서다. 화면에서 고친 것은 누가 언제 왜 바꿨는지 남지 않고, 파드를 다시 만들면 사라진다. 저장소에 두면 변경이 커밋으로 남고, 되돌리기도 쉽다. [docs:history/build_log/09_monitoring.md:31-32]

대시보드는 JSON 파일인데, 손으로 JSON을 고치지 않는다. 대시보드마다 그 JSON을 만들어 내는 파이썬 스크립트가 있어서, 스크립트를 고친 뒤 JSON을 다시 만든다. [code:apps/monitoring/grafana/dashboard-provider.yaml:1-2] 만든 JSON은 kustomize가 ConfigMap으로 묶어 Grafana 파드에 붙인다. [code:apps/monitoring/kustomization.yaml:31-37] 모니터링 Application은 자동 Sync라, 고친 것을 운영 브랜치에 올리면 따로 손대지 않아도 클러스터에 들어간다. [code:apps/monitoring/app.yaml:24-27]

## 데이터소스 넷

| 이름 | 종류 | 읽는 곳 |
| --- | --- | --- |
| Prometheus | 지표 | 클러스터의 Prometheus(기본 데이터소스) |
| Loki | 로그 | 클러스터의 Loki |
| petmint-turns | MySQL | 펫퍼민트 DB의 복제본 |
| runshoes | MySQL | 런슈즈 DB의 복제본 |

[code:apps/monitoring/grafana/datasource.yaml:10-58]

두 MySQL 데이터소스는 대시보드에 질문 수, 답 걸린 시간, 평가 같은 서비스 숫자를 그리려고 둔 것이다. 이런 숫자는 지표로 나오지 않고 각 서비스가 DB에 남기는 기록에만 있다. [docs:history/build_log/09_monitoring.md:64] 그런데 그 기록에는 질문과 답 원문도 함께 있다. 그래서 세 겹으로 막았다.

첫째, 운영 DB(Primary)가 아니라 복제본(Replica)을 읽는다. 대시보드 쿼리가 서비스의 쓰기에 부하를 주지 않게 하기 위해서다. [code:apps/monitoring/grafana/datasource.yaml:26] [code:apps/monitoring/grafana/datasource.yaml:43] 둘째, 읽기 계정은 칸 단위로만 읽기 권한을 받았다. 분류, 시간, 상태 같은 칸은 읽지만 질문, 답, 상담원 코멘트, 고객 정보 칸은 권한이 없어 쿼리를 보내도 거절된다. [code:apps/monitoring/grafana/datasource.yaml:27-28] [code:apps/monitoring/grafana/datasource.yaml:43-44] 셋째, 계정의 동시 연결 수에 상한을 두었다. [code:apps/monitoring/README.md:30]

DB 계정의 비밀번호는 저장소에 없다. 사람이 쿠버네티스 Secret으로 만들고, Grafana가 환경 변수로 받아 데이터소스에 넣는다. [code:apps/monitoring/grafana/deployment.yaml:32-40] 런슈즈 쪽 Secret이 없으면 Grafana 파드가 뜨지 않는다. [code:apps/monitoring/README.md:43]

## 대시보드 둘

대시보드는 서비스마다 하나씩, 「petmint 운영」과 「runshoes 운영」 둘이다. 둘 다 1분마다 새로 고친다. [code:apps/monitoring/grafana/dashboards/gen_petmint.py:210-212] [code:apps/monitoring/grafana/dashboards/gen_runshoes.py:401-404]

「petmint 운영」은 기본으로 최근 30일을 보여 주고, 네 묶음으로 나뉜다. 서비스 상태와 접속량(응답 가능한 서버 수, 재시작, 요청량, 오류 비율), 질문량(모드별, 시간대별), 답변 품질과 속도(확인 불가 응답, 실패, 규칙으로 답한 횟수, 평가, 답 걸린 시간, 조항 검색 시간), AI 서버(GPU 사용률과 메모리, 메모리에 올라간 모델, 질문별로 쓴 모델)다. 마지막에 최근 7일의 앱 로그 칸이 붙는다. [code:apps/monitoring/grafana/dashboards/gen_petmint.py:77] [code:apps/monitoring/grafana/dashboards/gen_petmint.py:101] [code:apps/monitoring/grafana/dashboards/gen_petmint.py:114] [code:apps/monitoring/grafana/dashboards/gen_petmint.py:175] [code:apps/monitoring/grafana/dashboards/gen_petmint.py:204-208]

「runshoes 운영」은 기본으로 최근 7일을 보여 주고, 일곱 묶음이다. 서비스 상태(서버 수, 재시작, 요청량, 컨테이너별 CPU와 메모리), API(주소별 요청, 응답 시간, 오류, DB 연결, 자바 메모리), 챗봇(갈래별 질문, 갈래를 정한 방식, 답 걸린 시간, 단계별 시간), AI 서버(GPU), 사이트 활동(리뷰, 찜, 가입, 로그인, 많이 본 신발), 하루 한 번 도는 리뷰 요약 배치, 서버 로그다. [code:apps/monitoring/grafana/dashboards/gen_runshoes.py:115] [code:apps/monitoring/grafana/dashboards/gen_runshoes.py:168] [code:apps/monitoring/grafana/dashboards/gen_runshoes.py:212] [code:apps/monitoring/grafana/dashboards/gen_runshoes.py:278] [code:apps/monitoring/grafana/dashboards/gen_runshoes.py:301] [code:apps/monitoring/grafana/dashboards/gen_runshoes.py:371] [code:apps/monitoring/grafana/dashboards/gen_runshoes.py:393] 두 서비스가 GPU 한 장을 나눠 쓰므로 GPU 묶음은 양쪽 대시보드에 다 있다. 메모리에 올라간 모델 칸을 보면 어느 서비스가 GPU를 쓰고 있는지 가를 수 있다. [code:apps/monitoring/grafana/dashboards/gen_runshoes.py:281]

대시보드를 보는 사람은 개발자가 아닐 수 있다. 그래서 칸 제목은 무엇을 세는지 바로 알 수 있는 말로 쓰고, 마우스를 올리면 나오는 설명에 무엇이 섞였는지, 높거나 낮으면 무슨 뜻인지, 언제부터 있는 값인지를 쉬운 말로 적는다. DB 칸 이름이나 도구 이름은 설명 끝의 「출처」 한 줄에만 둔다. [code:apps/monitoring/grafana/dashboards/gen_petmint.py:62-63] [code:apps/monitoring/grafana/dashboards/gen_runshoes.py:10-11] Grafana는 추세를 보는 곳이고, 한 건 한 건을 들여다보고 손대는 일은 각 서비스의 관리자 화면이 맡는다. [code:apps/monitoring/grafana/dashboards/gen_runshoes.py:7-8]

## 들어가는 문

Grafana는 바깥 주소로 열려 있고, 자체 로그인과 Cloudflare Access 두 겹으로 막는다. [code:apps/monitoring/ingress.yaml:7] 로그인하지 않은 사람에게는 아무것도 보여 주지 않으며 [code:apps/monitoring/grafana/deployment.yaml:41-42], 업데이트 확인이나 사용 통계처럼 바깥으로 나가는 호출은 껐다. [code:apps/monitoring/grafana/deployment.yaml:43-49] 관리자 계정은 사람이 Secret으로 만들어 넣는다. [code:apps/monitoring/grafana/deployment.yaml:28-31]

Grafana의 메모리 상한은 넉넉하게 잡았다. 기동만으로 상당한 메모리를 쓰고, 대시보드 목록 화면을 열 때 검색 색인을 만들며 더 쓴다. 상한이 모자라면 Grafana가 강제로 꺼지고 바깥에서는 오류 화면이 뜬다. [code:apps/monitoring/grafana/deployment.yaml:65-69]

## 알려진 한계

- 화면에서 고친 대시보드는 남지 않는다. 고치려면 생성 스크립트를 고쳐 JSON을 다시 만든다. [code:apps/monitoring/grafana/dashboard-provider.yaml:2]
- DB 칸을 읽는 패널은 복제본에 기댄다. 복제가 멈추거나 늦으면 그 패널도 멈추거나 늦는다. [docs:history/build_log/09_monitoring.md:70]
- 서비스 DB에 새 칸이 생기면 읽기 권한을 사람이 손으로 더해야 패널이 값을 낸다. [docs:history/build_log/09_monitoring.md:70]
- 펫퍼민트의 확인 불가 응답 비율은 거절 문구로 판정한다. 거절 문구 없이 얼버무린 답은 세지 않는다. [docs:history/build_log/09_monitoring.md:213]
- 대시보드는 사람이 열어야 본다. 알림은 없다. [docs:history/build_log/09_monitoring.md:145]

## 용어 풀이

- 대시보드: 여러 그래프와 숫자 칸을 한 화면에 모은 것
- 데이터소스: Grafana가 값을 물어보러 가는 곳. 지표 저장소, 로그 저장소, DB 같은 것
- 프로비저닝: 화면에서 손으로 만들지 않고, 기동할 때 파일을 읽어 설정을 미리 채워 넣는 것
- 복제본(Replica): 운영 DB의 내용을 그대로 따라 받아 두는 DB. 읽기만 한다
- 칸 단위 권한: 표 전체가 아니라 표의 특정 칸만 읽을 수 있게 주는 권한

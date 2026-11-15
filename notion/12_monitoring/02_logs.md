<!--
다루는 곳: apps/monitoring/loki/, apps/monitoring/alloy/
읽은 커밋: e8e24ea
-->
# 로그

로그는 프로그램이 돌면서 남기는 글 기록이다. 「요청을 받았다」, 「DB 연결에 실패했다」 같은 줄이 시간 순서로 쌓인다. 지표가 「얼마나」를 숫자로 알려 준다면, 로그는 그때 「무슨 일이」 있었는지를 글로 알려 준다. 오류율 그래프가 튀었을 때 원인을 찾으러 가는 곳이 로그다.

쿠버네티스에서 파드의 로그는 그 파드가 떠 있는 노드의 파일로 남는다. 파드가 지워지거나 다른 노드로 옮겨 가면 그 파일도 함께 사라진다. 그래서 로그를 한곳에 모아 두는 장치가 필요하다. 이 클러스터에서는 Alloy가 노드마다 로그 파일을 읽어 보내고, Loki가 받아 저장하며, Grafana가 Loki에 물어 화면에 보여 준다. [code:apps/monitoring/alloy/alloy.yaml:1] [code:apps/monitoring/loki/loki.yaml:1-3]

## Alloy: 노드마다 로그를 읽어 보낸다

Alloy는 DaemonSet(노드마다 파드를 하나씩 띄우는 객체)으로 돈다. 컨트롤 플레인 노드에도 뜨도록 그 노드의 taint를 견디게 했다. [code:apps/monitoring/alloy/alloy.yaml:126-129] 각 Alloy는 쿠버네티스 API에 물어 자기 노드에 뜬 파드만 골라내고, 그 파드들의 로그 파일을 읽는다. [code:apps/monitoring/alloy/alloy.yaml:39-45] 로그 파일은 노드의 관리자만 읽을 수 있어서 Alloy는 관리자 권한으로 돌되, 파일을 읽는 권한 하나만 남기고 나머지 권한을 모두 버리며 로그 폴더도 읽기 전용으로 붙인다. [code:apps/monitoring/alloy/alloy.yaml:151-158]

어디까지 읽었는지는 노드의 디렉터리에 적어 둔다. Alloy 파드를 다시 띄워도 처음부터 다시 보내지 않게 하기 위해서다. [code:apps/monitoring/alloy/alloy.yaml:165-167]

로그 줄마다 붙는 라벨(검색할 때 거르는 이름표)은 네임스페이스, 파드, 컨테이너, 노드 넷뿐이다. Loki는 라벨 조합마다 색인을 만들기 때문에, 라벨을 적게 두어야 색인이 작게 유지된다. [code:apps/monitoring/alloy/alloy.yaml:5]

## 넣지 않는 것

Loki에는 서버 로그만 넣는다. 대화 기록, 곧 사용자가 한 질문과 받은 답의 원문은 넣지 않는다. [code:apps/monitoring/loki/loki.yaml:1-2] 대화 기록은 이미 각 서비스의 DB에 있다. 로그에도 들어가면 같은 내용이 권한이 다른 곳에 한 벌 더 생긴다. DB에서는 대시보드 계정이 질문과 답 칸을 읽지 못하게 막아 두었는데, 로그로 새어 나가면 그 막음이 소용없어진다. [docs:history/build_log/09_monitoring.md:90] [code:apps/monitoring/grafana/datasource.yaml:26-28]

그런데 런슈즈 챗봇은 질문을 받을 때마다 질문 원문을 한 줄로 로그에 찍는다. 그래서 Alloy가 런슈즈 네임스페이스의 챗봇 컨테이너에서 나온 줄 가운데 「질문:」이 든 줄을 Loki로 보내기 전에 버린다. [code:apps/monitoring/alloy/alloy.yaml:2-3] [code:apps/monitoring/alloy/alloy.yaml:96-102] 펫퍼민트 앱 로그에는 대화 내용이 들어 있지 않다. [code:apps/monitoring/grafana/dashboards/gen_petmint.py:207]

Jenkins의 빌드 파드 로그도 넣지 않는다. 빌드 파드는 빌드 한 번마다 새로 떠서 빌드 출력을 길게 쏟아 내고 사라진다. jenkins 네임스페이스에서는 Jenkins 본체(컨트롤러) 파드 하나만 남기고 나머지는 수집 대상에서 뺀다. [code:apps/monitoring/alloy/alloy.yaml:4] [code:apps/monitoring/alloy/alloy.yaml:49-60]

## Loki: 받아서 7일 둔다

Loki는 한 대이고, 여러 역할을 한 프로그램 안에서 모두 맡는 단일 바이너리 방식으로 돈다. 로그 덩어리와 색인을 w4의 로컬 디스크 볼륨에 파일로 저장한다. [code:apps/monitoring/loki/loki.yaml:1] [code:apps/monitoring/loki/loki.yaml:60-61] [code:apps/monitoring/loki/loki.yaml:90-98] 보존은 7일이다. 정리 담당(compactor)이 7일이 지난 로그를 지운다. [code:apps/monitoring/loki/loki.yaml:33-41] 한꺼번에 너무 많은 로그가 쏟아질 때를 대비해 받는 속도에도 상한을 걸었다. [code:apps/monitoring/loki/loki.yaml:35-36]

Loki에는 인증이 없다. 클러스터 안에서만 닿는 주소로 열려 있고, 부르는 곳은 Grafana뿐이다. [code:apps/monitoring/loki/loki.yaml:3] 바깥 주소는 따로 열지 않았다. 로그는 Grafana 대시보드의 로그 칸이나 Grafana의 검색 화면에서 본다. → 「대시보드」

## 알려진 한계

- 대화 원문을 거르는 것은 글자 맞추기다. 앱이 로그 꼴을 바꾸면(「질문:」을 다른 말로) 거르지 못하고 들어간다. 다른 앱이 새로 원문을 찍어도 Alloy 설정을 고치기 전까지는 들어간다. [docs:history/build_log/09_monitoring.md:110]
- Loki는 한 대이고 볼륨이 w4에 묶여 있다. w4가 죽거나 정비로 비우면 그동안 로그가 빈다. [docs:history/build_log/09_monitoring.md:209]
- 7일이 지난 로그는 남지 않는다. 그보다 오래된 일을 되짚으려면 앱의 DB 기록을 봐야 한다. [code:apps/monitoring/loki/loki.yaml:34]
- 로그를 보고 알림을 보내는 장치는 없다. [docs:history/build_log/09_monitoring.md:208]

## 용어 풀이

- 로그: 프로그램이 돌면서 남기는 글 기록
- 라벨: 로그 줄에 붙는 이름표. 이 값으로 로그를 거른다
- 색인: 찾기 쉽게 따로 만들어 둔 목록. Loki는 라벨로만 색인을 만들고 본문은 색인하지 않는다
- compactor: Loki 안에서 저장된 조각을 합치고 보존 기간이 지난 것을 지우는 부분
- 단일 바이너리: 받기, 저장, 찾기 같은 여러 역할을 프로그램 하나가 모두 맡는 실행 방식
- taint: 노드가 아무 파드나 받지 않도록 붙이는 표시. 이를 견디도록 설정한 파드만 그 노드에 뜬다

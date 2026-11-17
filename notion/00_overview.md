<!--
다루는 곳: bootstrap/root-app.yaml, cluster/Vagrantfile
읽은 커밋: 736d833
-->
# 00 전체 그림

이 문서 묶음은 GPU가 든 서버 한 대 안에 쿠버네티스 클러스터를 세우고, 그 위에서 서비스 둘과 운영 도구를 돌리는 홈랩의 기술문서다. 쿠버네티스(여러 컴퓨터를 한 덩어리로 묶어 프로그램을 알아서 나눠 띄우고 지켜 주는 관리 시스템)를 모르는 사람도 처음부터 따라 읽을 수 있게 썼다. 이 편은 전체를 한 번에 내려다보는 지도이고, 자세한 것은 편마다 따로 있다.

## 한 대의 서버 안에 다섯 대의 컴퓨터

모든 것은 물리 서버 한 대 위에 있다. 이 서버에는 NVIDIA GeForce RTX 5070 Ti 그래픽카드 한 장이 꽂혀 있고, 호스트 OS는 Ubuntu 26.04.1 LTS다. [docs:history/notion_hardware_20261116.md:34-39] [docs:history/cluster_state_20261116.md:75-76] 여기서 호스트는 VM이 아닌 바깥의 진짜 서버를 말한다.

클러스터를 이루는 컴퓨터는 이 서버 안에서 도는 가상 머신(VM, 소프트웨어로 흉내 낸 컴퓨터) 다섯 대다. 한 대는 클러스터 전체를 지휘하는 control-plane인 m-k8s이고, 나머지 네 대(w1 ~ w4)는 실제로 프로그램을 돌리는 워커다. [code:cluster/Vagrantfile:3-10] [docs:history/cluster_state_20261116.md:9-15] VM은 Vagrant라는 도구가 libvirt 위에 정의 파일 하나를 보고 만든다. 서버가 한 대뿐인데 굳이 여러 대로 나눈 것은, 지휘하는 노드와 일하는 노드가 한 몸인 싱글 노드로는 파드가 여러 노드에 흩어지고 한 노드가 죽으면 다른 노드가 넘겨받는 쿠버네티스의 본래 모습을 보여 줄 수 없어서다. [docs:history/build_log/01_cluster.md:126] [docs:history/build_log/01_cluster.md:136-138]

워커 네 대는 맡은 일이 정해져 있다. w1과 w2는 서비스 앱과 그 데이터베이스를, w3는 배포와 빌드에 쓰는 도구를, w4는 모니터링을 맡는다. [code:cluster/label-nodes.sh:6-8] 이렇게 나눈 까닭은 한 노드가 죽었을 때 무엇이 멈추는지를 미리 정해 두기 위해서다. w3가 멈추면 새 배포와 빌드만 멈추고 돌고 있는 서비스는 그대로이며, w4가 멈추면 모니터링만 멈춘다. [code:cluster/label-nodes.sh:7-8] VM을 어떻게 만들고 노드를 어떻게 설치하는지는 → 「가상 머신과 노드」, 쿠버네티스를 깔고 노드끼리 파드 망을 잇는 일은 → 「쿠버네티스 설치와 파드 망」에 있다. 그 아래 물리 서버, OS, 드라이버, 원격 접속은 → 「서버와 호스트 OS」에서 다룬다.

## 클러스터 위에 올라간 것

클러스터가 바깥에 내놓는 서비스는 둘이다. petmint(펫퍼민트)는 반려동물 보험 상담을 해 주는 RAG 챗봇이고, runshoes(런슈즈)는 러닝화 스펙을 모아 보여 주는 아카이브 사이트다. [docs:history/build_log/07_project_deploy.md:16] [code:apps/runshoes/README.md:3] RAG는 질문이 오면 먼저 약관 같은 자료에서 관련 대목을 찾아 붙인 뒤 언어 모델에 답을 짓게 하는 방식이다. 두 앱 모두 앱 파드 두 개를 w1과 w2에 하나씩 띄우고, MySQL 데이터베이스는 w1에 원본(Primary)을, w2에 복제본(Replica)을 둔다. [docs:history/build_log/07_project_deploy.md:3] 앱이 클러스터에 올라가는 모양은 → 「앱이 올라가는 길」, 데이터베이스의 복제와 백업은 → 「데이터베이스 복제와 백업」, 여러 노드가 같이 읽는 공유 파일 자리는 → 「공유 저장소」에 있다.

서비스를 만들고 지키는 운영 도구도 같은 클러스터에서 돈다. ArgoCD는 저장소에 적힌 대로 클러스터를 맞추는 배포 도구이고, Harbor는 앱 이미지(프로그램을 실행할 수 있게 통째로 묶은 꾸러미)를 보관하는 사설 이미지 저장소이며, Jenkins는 앱 코드를 받아 이미지를 만드는 빌드 도구다. 이 셋이 w3에 있다. [code:cluster/label-nodes.sh:7] 모니터링은 Prometheus(지표), Loki(로그), Grafana(대시보드)로 이루어져 w4에 있다. [code:apps/monitoring/README.md:3-6] 각각은 → 「GitOps」, → 「이미지 저장소」, → 「빌드와 태그 고정」, → 「모니터링」에서 다룬다.

앱 코드가 바뀌어 서비스에 들어가기까지는 사람이 손대지 않는다. 앱 저장소에 코드가 올라오면 Jenkins가 이미지를 만들어 Harbor에 올리고, 이 저장소의 이미지 태그 줄을 새 값으로 바꿔 커밋한다. ArgoCD는 그 커밋을 보고 클러스터의 앱을 새 이미지로 차례차례 바꿔 끼운다. [docs:history/build_log/07_project_deploy.md:3] [code:apps/petmint/app.yaml:1-4]

## 저장소가 곧 운영

이 저장소의 main 브랜치에 적힌 것이 곧 클러스터의 모습이다. ArgoCD에는 맨 위에 루트 Application 하나만 사람이 넣고, 루트가 저장소의 앱 폴더마다 있는 정의 파일을 읽어 앱별 Application을 만든다. 이 방식을 App of Apps라 부른다. [code:bootstrap/root-app.yaml:1-6] 지금 앱 다섯 가운데 넷(runshoes, petmint, monitoring, harbor-backup)은 main에 커밋이 들어오면 저절로 반영되고, 바깥 공개를 맡은 cloudflared 하나만 사람이 반영 단추를 누른다. [docs:history/cluster_state_20261116.md:52-61] 반대로 클러스터의 바탕이 되는 기반(인증서 관리, 로드밸런서, 들어오는 문, Harbor, Jenkins 등)은 ArgoCD보다 먼저 깔아야 했기 때문에 ArgoCD 밖에 두고 사람이 직접 넣는다. [code:bootstrap/root-app.yaml:13] 비밀번호와 토큰은 저장소에 두지 않고 사람이 클러스터에 직접 만든다. [code:CLAUDE.md:47] 이 저장소를 누가 어떻게 고치는지는 → 「운영 규칙과 문서 게시」에 있다.

## 바깥에서 들어오는 길

서비스는 공유기의 포트포워딩으로 내놓지 않는다. 공유기에서 서버로 바로 들어오는 길은 관리용 SSH 하나뿐이다. [docs:history/notion_hardware_20261116.md:33] 서비스 공개에는 Cloudflare 터널을 쓴다. 클러스터 안의 cloudflared 파드 두 개가 Cloudflare 쪽으로 먼저 연결을 열어 두고, 바깥 사용자의 요청은 그 연결을 거꾸로 타고 들어온다. [code:apps/cloudflared/README.md:3-4] [code:apps/cloudflared/deployment.yaml:13] 연결을 여는 쪽이 서버라서, 공유기에 서비스용 문을 새로 열지 않아도 된다. 공개 주소는 두 앱과 운영 도구 화면을 합해 일곱이고, 운영 도구 앞에는 Cloudflare Access 로그인이 한 겹 더 있다. [code:apps/cloudflared/README.md:3-4] 터널에서 들어온 요청은 모두 클러스터의 들어오는 문인 ingress-nginx로 가고, ingress-nginx가 주소를 보고 알맞은 서비스로 나눠 준다. [docs:history/cluster_state_20261116.md:50] 클러스터 안쪽의 문 구조는 → 「들어오는 문」, 바깥 공개와 인증서는 → 「바깥 공개와 인증서」에서 다룬다.

## GPU 추론은 호스트에서

언어 모델을 돌리는 GPU 일은 클러스터 안이 아니라 호스트에서 한다. 호스트에는 추론 서버 Ollama, 임베딩과 리랭커를 돌리는 model-service, 벡터 검색용 Milvus가 컨테이너나 서비스로 떠 있다. [docs:history/cluster_state_20261116.md:77-78] 클러스터 안의 앱 파드는 이들을 VM과 호스트가 함께 쓰는 사설 고정망의 호스트 주소로 부른다. [docs:history/cluster_state_20261116.md:80] GPU는 한 장뿐이고, 같은 추론 서버를 학교 PC 같은 클러스터 밖의 사용자도 별도의 터널로 함께 부른다. 그래서 추론 서버는 클러스터와 따로 호스트에 하나만 두고, 모델을 GPU 메모리에 붙들어 두는 시간도 다른 사용자와 나눠 쓰는 것을 생각해 정해 둔 값을 바꾸지 않는다. [docs:history/build_log/03_cloudflare_tunnel.md:3] [code:CLAUDE.md:34] 자세한 것은 → 「GPU와 호스트 서비스」에 있다.

## 알려진 한계

- 모든 것이 물리 서버 한 대 안에 있다. 노드를 다섯으로 나눴어도 서버 자체가 꺼지면 클러스터, 운영 도구, 추론 서버가 함께 멈춘다. [code:cluster/Vagrantfile:3-10] [code:CLAUDE.md:8]
- control-plane은 m-k8s 한 대다. m-k8s가 멈추면 돌던 파드는 그대로 돌지만 새 배포와 클러스터 관리가 멈춘다. [docs:history/cluster_state_20261116.md:11] 늘리려면 셋이 필요한데, VM이 모두 같은 서버 한 대 위에 있어 셋으로 늘려도 서버가 꺼지면 함께 꺼진다. 들이는 자원만큼 얻는 것이 없다. [c:a40b111]
- 바깥 공개 주소는 모두 터널 하나를 지난다. 터널이 깨지면 서비스와 함께 ArgoCD, Grafana 같은 고칠 도구의 화면도 바깥에서 보이지 않는다. [code:apps/cloudflared/app.yaml:4-7]

## 용어 풀이

- 쿠버네티스: 여러 컴퓨터를 한 덩어리로 묶어 프로그램을 나눠 띄우고, 죽으면 다시 띄워 주는 관리 시스템
- 노드: 클러스터를 이루는 컴퓨터 한 대. 여기서는 VM 한 대가 노드 하나다
- control-plane: 클러스터 전체의 상태를 기억하고 지휘하는 노드
- 워커: 실제 프로그램(파드)을 돌리는 노드
- 파드: 쿠버네티스가 띄우는 가장 작은 실행 단위. 컨테이너 하나 또는 여럿을 묶은 것
- 이미지: 프로그램과 그 실행 환경을 통째로 묶어 어디서나 같은 모양으로 띄울 수 있게 한 꾸러미
- GitOps: 저장소에 적힌 내용을 정답으로 두고, 도구가 클러스터를 그 정답에 맞추는 운영 방식
- Cloudflare 터널: 서버가 바깥으로 먼저 연결을 열어 두고, 바깥 요청을 그 연결로 받아들이는 공개 방식
- 호스트: VM들을 품고 있는 진짜 물리 서버와 그 OS

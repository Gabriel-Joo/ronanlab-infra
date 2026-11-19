<!--
다루는 곳: cluster/label-nodes.sh, bootstrap/root-app.yaml, apps/cloudflared/app.yaml, scripts/host-gpu-exporter.sh
읽은 커밋: 40ca5f3
-->
# 15 알려진 한계

이 편은 이 홈랩이 무엇을 골랐고, 그 선택 때문에 무엇을 못 하거나 떠안는지를 모은다. 다른 편은 구성 요소로 나뉘지만 한계는 구성 요소로 나눌 수 없어서, 이 편만은 결정으로 묶었다. 묶음마다 먼저 무엇을 왜 골랐는지 한 번 말하고, 그 아래에 그 선택에서 나온 일을 적는다. 여러 편에 되풀이되는 것만 여기 두고, 한 편에만 걸리는 한계는 그 편의 「알려진 한계」에 그대로 두었다. 끝의 두 묶음은 고른 것이 아니라 바꿀 수 없는 조건이다. 아직 하지 않은 일은 한계가 아니어서 이 편에 없고, 저장소의 할 일 목록 한 곳에 있다 [docs:TODO.md].

## 1. 노드마다 역할을 하나씩 정했다

노드가 죽었을 때 무엇이 멈추는지를 노드 이름으로 말할 수 있게 하려고, 워커마다 역할을 정하고 구성 요소를 그 역할의 노드에 고정했다 [docs:history/build_log/08_scale_out.md:129]. 앱을 맡는 노드는 둘이지만, 이미지 저장소와 빌드와 배포 도구를 맡는 infra(w3)와 모니터링을 맡는 platform(w4)은 한 대씩이다 [code:cluster/label-nodes.sh:6-8]. 그래서 그 노드가 빠지면 거기 고정한 것은 다른 노드로 옮겨 뜨지 않는다. w3이 죽으면 배포와 빌드가, w4가 죽으면 모니터링이 그 노드가 돌아올 때까지 멈춘다. 목표로 받아들인 한계다 [docs:history/build_log/08_scale_out.md:434].

- ArgoCD가 w3 한 노드에만 있다. w3가 내려가면 새 배포가 멈춘다. 이미 떠 있는 앱은 그대로 돈다 [code:cluster/label-nodes.sh:7]
- Harbor가 w3 한 노드에만 있다. w3가 내려가면 이미지를 올리고 받는 일이 모두 멈춘다. 이미 떠 있는 앱 파드는 이미지를 노드에 갖고 있어 그대로 돈다 [code:cluster/label-nodes.sh:7]
- Jenkins 본체가 하나이고 w3에 묶여 있다. w3를 정비하는 동안 빌드가 멈춘다. 떠 있는 앱은 영향이 없다 [docs:history/build_log/06_jenkins.md:504]
- Prometheus와 Loki는 한 대씩이고 볼륨이 w4에 묶여 있다. w4가 죽거나 정비로 비우면 그동안의 지표와 로그가 빈다 [docs:history/build_log/09_monitoring.md:209]

## 2. 바깥 길을 좁혔다

### 웹 공개는 터널 하나로

웹 서비스는 공유기 포트포워딩 없이 Cloudflare 터널 하나로 공개하고, 터널 뒤에서 주소별로 나누는 일은 ingress-nginx가 한다. 새 앱을 더할 때 터널을 늘리지 않고 Ingress 하나와 터널 설정 한 줄만 더하면 되게 하려는 것이다 [docs:history/build_log/03_cloudflare_tunnel.md:153]. 그래서 바깥 공개 주소가 모두 한 터널을 지난다.

- 터널 하나에 공개 주소 일곱 개가 몰려 있다. 터널이 깨지면 공개 앱만이 아니라 고칠 도구(ArgoCD 화면)와 볼 도구(Grafana)도 바깥에서 한꺼번에 보이지 않고, 되돌리기는 관리 노드에서 명령으로만 된다 [code:apps/cloudflared/app.yaml:4-7]

### 관리 길은 SSH 하나로

바깥에서 서버로 바로 들어오는 길은 공유기의 포트포워딩 하나이고, 그 길은 서버의 SSH에만 닿는다. 바깥으로 여는 길이 늘수록 뚫릴 자리가 늘어서, 관리 길은 하나로 두고 그 하나만 지키기로 했다 [c:44860df]. Jupyter, 원격 데스크톱, 추론 서버 같은 다른 서비스는 바깥에 열지 않고 SSH 연결 안의 터널로 연다 [docs:history/notion_hardware_20261116.md:11]. 추론 서버 포트를 공유기에 바로 여는 길은, 그 포트를 인증 없이 인터넷에 그대로 내놓는 보안 위험이 있어 버렸다 [docs:history/cloudflare_tunnel_vcluster.md:77]. 그래서 바깥에서 하는 관리가 모두 이 한 길에 기댄다. 서버는 모니터와 키보드를 떼고 SSH와 원격 데스크톱으로만 관리한다 [docs:history/notion_hardware_20261116.md:18].

- 공유기 설정이 바뀌거나 공유기가 꺼지면 바깥에서 서버를 관리할 길이 없다
- SSH 서비스나 방화벽 설정이 잘못되면 바깥에서는 서버에 닿을 길이 없고, 서버 앞에 가서 모니터와 키보드를 꽂아야 한다

### 사설망 안쪽 길에는 Access가 없다

터널이 깨졌을 때 고칠 길로, 서버 호스트에서 터널을 거치지 않고 ingress-nginx의 사설 VIP로 운영 도구 화면을 여는 길을 남겼다. 이 길은 Cloudflare를 지나지 않으므로 Access도 거치지 않는다 [code:apps/cloudflared/README.md:24-25]. 그 사설망에는 호스트와 가상 머신만 있다 [code:apps/monitoring/ingress.yaml:6].

- 사설망 안에서는 Access 없이 운영 도구에 닿는다. 자체 로그인이 없는 Prometheus도 사설망에서는 그대로 열린다 [code:apps/monitoring/ingress.yaml:5-6]

## 3. 저장소 밖에 둔 것

### 비밀값은 저장소에 두지 않는다

비밀값은 저장소에 두지 않고, 사람이 클러스터에 Secret으로 직접 만든다 [code:CLAUDE.md:47]. 커밋되는 매니페스트에 실제 값이 박히는 것을 막으려는 것이다 [docs:history/build_log/03_cloudflare_tunnel.md:188]. 그래서 클러스터를 새로 세우면 비밀값은 저장소에서 돌아오지 않고, 사람이 다시 넣어야 한다.

- Cloudflare API 토큰이 저장소에 없다. 클러스터를 다시 만들 때 사람이 Secret을 넣지 않으면 인증서를 받지 못한다 [code:platform/cert-manager/cluster-issuer.yaml:1]
- ArgoCD의 웹훅 시크릿과 알림 토큰도 저장소에 없어, 클러스터를 새로 세우면 사람이 다시 넣어야 한다 [docs:history/build_log/04_argocd.md:56-59]
- Harbor 관리자 비밀번호는 Helm 릴리스 값에만 있다. 업그레이드 때 빠뜨리면 차트의 기본값이 들어간다 [docs:history/build_log/05_harbor.md:485]
- 앱의 비밀값은 클러스터에만 있다. 클러스터를 다시 만들면 스크립트가 새 무작위 값을 만들고, 남아 있는 MySQL 데이터의 관리자 비밀번호와 어긋날 수 있다 [code:apps/petmint/scripts/create-secrets.sh:3]

### 자동 Sync 스위치는 클러스터에 둔다

자동 반영(자동 Sync)을 켜고 끄는 실제 스위치는 저장소의 앱 정의 파일이 아니라 클러스터에 있다. 루트 Application이 앱의 Sync 설정까지 저장소대로 맞추면, Jenkins의 태그 커밋 하나에 루트가 다시 Sync하면서 스키마 배포 동안 잠시 꺼 둔 자동 Sync를 도로 켜기 때문이다 [code:bootstrap/root-app.yaml:8-10]. 끄고 켜는 일도 사람이 한다. 배포를 막는 장치라 사람이 직접 끈다 [code:apps/runshoes/runbooks/catalog-v4-v5.md:37].

- 앱 정의 파일의 자동 Sync 값과 클러스터의 실제 값이 다를 수 있다. 저장소만 보고는 지금 반영 방식을 단정할 수 없고, 클러스터에서 확인해야 한다 [code:CLAUDE.md:11]
- 스키마를 바꾸는 배포에서 끄기를 잊고 push하면 덤프 없이 스키마가 바뀔 수 있다 [code:apps/runshoes/runbooks/v22-v23-review-hide-miss-status.md:158]

### GPU를 쓰는 서비스는 호스트에 둔다

GPU는 호스트에 그대로 두고, 파드는 호스트의 추론 서버를 망으로 부르기만 한다. GPU를 가상 머신에 넘기는 일은 처음 해 보는 작업이라 위험이 컸고, 호스트에서 이미 추론 서버를 계속 쓰고 있었다 [docs:history/human_answers_20261117.md:7]. 그래서 추론 서버, 벡터 DB, model-service 같은 호스트 서비스와 GPU 지표 수집기는 클러스터 밖, ArgoCD 밖에 있다(→ 「GPU와 호스트 서비스」).

- 호스트 서비스는 저장소로 상태를 되돌릴 수 없다 [docs:history/cluster_state_20261116.md:76-77]
- GPU 수집기는 컨테이너가 사라지면 사람이 스크립트를 다시 돌려 띄운다. 바깥 이미지를 GPU 권한으로 물리 서버에 띄우는 일이라 사람이 돌리기로 했다 [docs:history/build_log/09_monitoring.md:122] [docs:history/build_log/09_monitoring.md:124] [code:scripts/host-gpu-exporter.sh:11]

## 4. 서버 한 대 안에서는 겹을 늘리지 않았다

가상 머신이 모두 같은 물리 서버 한 대 위에 있다(끝의 조건 묶음). 그래서 여러 벌을 두어 장애를 견디는 장치 가운데, 서버가 꺼지면 함께 꺼지는 것은 들이지 않았다. 아래 두 줄은 기록이 적은 까닭이 「같은 서버 위라서」인 것이다.

- 컨트롤 플레인이 m-k8s 한 대다. m-k8s가 멈추면 이미 뜬 파드는 계속 돌지만 새 배치와 복구, 사람의 명령이 멈춘다 [docs:history/build_log/01_cluster.md:700]. 늘리려면 etcd가 과반으로 결정하는 방식 때문에 셋이 필요한데, 셋으로 늘려도 서버가 꺼지면 함께 꺼져 들이는 자원만큼 얻는 것이 없다 [docs:history/human_answers_20261117.md:29]
- 분산 저장소가 없다. 저장 공간은 local-path라 노드의 디스크에 묶이고, 그 노드가 멈추면 그 저장 공간을 쓰는 파드는 다른 노드로 옮겨 뜨지 못한다. Harbor의 데이터도 w3의 디스크에만 있다 [code:platform/harbor/pvc-w3.yaml:4] [code:apps/monitoring/prometheus/statefulset.yaml:2]. 노드 사이에 복제하는 분산 저장소는 클러스터를 하나 더 얹는 무게이고, 복제해도 서버가 꺼지면 함께 꺼져 실익이 없다 [docs:history/build_log/05_harbor.md:234-235]

## 5. 조건: 물리 서버 한 대

이것은 고른 것이 아니라 가진 자원이다. 사무실 서버 PC 가운데 이 프로젝트가 쓰는 것은 한 대이고 [docs:history/notion_hardware_20261116.md:12], 쿠버네티스 가상 머신 다섯 대와 호스트의 추론 서버, 벡터 DB, model-service, NFS가 모두 그 한 대, 같은 디스크 위에 있다 [docs:history/build_log/01_cluster.md:699] [docs:history/build_log/kubernetes_install.md:198]. 노드를 나눈 것은 가상 머신 하나나 노드 프로그램 하나가 죽는 장애만 막는다 [docs:history/build_log/08_scale_out.md:436].

- 서버가 꺼지면 클러스터, 운영 도구, 추론 서버, 벡터 DB, model-service가 함께 멈춘다 [code:cluster/Vagrantfile:3-10] [docs:history/build_log/kubernetes_install.md:198]
- 앱을 맡는 노드가 둘뿐이다. 하나가 빠지면 각 앱이 파드 하나로 버틴다 [docs:history/build_log/08_scale_out.md:433] [c:44860df]
- NFS 공유도 호스트 하나에 있다. 호스트가 멈추면 약관을 읽는 앱과 백업이 멈추지만, 그때는 가상 머신도 같은 호스트에서 돌므로 클러스터 전체가 함께 멈춘다 [code:apps/petmint/data/nfs.yaml:1-2]

## 6. 조건: GPU 한 장

GPU는 한 장이다 [docs:history/notion_hardware_20261116.md:16]. 호스트의 추론과 학습, 클러스터가 부르는 추론이 모두 같은 GPU 메모리를 나눠 쓴다. 나누는 방식은 → 「GPU와 호스트 서비스」에서 다룬다.

- 바깥에서 터널로 긴 생성을 돌리면 펫퍼민트 서빙이 멈출 수 있다. 그래서 추론 서버로 가는 바깥 터널은 늘 Access 뒤에 둔다 [docs:history/build_log/03_cloudflare_tunnel.md:701]

## 용어 풀이

- 역할 라벨: 노드에 붙이는 이름표. 구성 요소의 설정이 「이 이름표가 붙은 노드에만 뜬다」는 조건으로 이 이름표를 본다
- 포트포워딩: 공유기의 바깥쪽 포트로 들어온 연결을 안쪽의 특정 주소로 넘겨 주는 규칙
- Access: Cloudflare가 터널 앞에서 로그인을 먼저 받게 하는 관문
- VIP: 노드 한 대가 아니라 서비스 하나에 붙인 사설 고정 주소. 여기서는 MetalLB가 ingress-nginx에 붙인 주소
- Secret: 쿠버네티스가 비밀번호나 토큰을 담아 두는 객체. 파드는 값 대신 이 객체를 가리킨다
- 자동 Sync: ArgoCD가 저장소에 새 커밋이 오면 사람 손 없이 클러스터에 반영하는 설정
- 컨트롤 플레인: 클러스터 전체를 관리하고 파드를 어느 노드에 둘지 정하는 노드
- etcd: 클러스터의 상태를 저장하는 데이터베이스. 여러 벌이면 과반이 동의해야 값을 정한다
- local-path: 노드의 디스크 한 칸을 떼어 파드에 붙여 주는 저장 방식. 그 칸은 처음 만든 노드에 묶인다
- 분산 저장소: 데이터를 여러 노드에 나눠 복제해, 노드 하나가 죽어도 다른 노드에서 읽게 하는 저장 방식

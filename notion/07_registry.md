<!--
다루는 곳: platform/harbor/, apps/harbor-backup/, scripts/host-nfs-harbor-backup-setup.sh
읽은 커밋: e8e24ea
-->
# 이미지 저장소

빌드 서버가 앱을 컨테이너 이미지로 만들면, 그 이미지를 어딘가에 올려 두어야 클러스터의 노드가 받아 갈 수 있다. 이 클러스터는 그 자리로 클러스터 안에 직접 세운 사설 이미지 저장소를 쓴다. 저장소 소프트웨어는 Harbor이고, Helm 차트 1.19.2로 Harbor 2.15.2를 깔았다. [code:platform/versions.yaml:44-48]

## 왜 직접 세웠나

공개 이미지 저장소인 Docker Hub를 쓰면 따로 세울 것이 없다. 그러나 공개 저장소에는 앱 코드가 든 이미지를 올릴 수 없고, 무료 계정은 내려받는 횟수에 제한이 있어 파드가 자주 다시 뜨는 환경에서는 막힐 수 있다. 학교에 있는 Harbor를 함께 쓰는 길도 보았지만, 그 저장소는 학교 안 망에서만 열려 있어 서버에서 닿지 않았다. [docs:history/build_log/05_harbor.md:170-172]

여러 저장소 소프트웨어 가운데 Harbor를 고른 것은 이미지를 담는 일 말고도 필요한 것이 이미 들어 있어서다. 프로젝트마다 권한을 나눌 수 있고, 사람 계정 대신 기계가 쓰는 로봇 계정을 따로 만들 수 있으며, 올라온 이미지의 알려진 취약점을 검사하는 Trivy가 딸려 온다. 로봇 계정 덕분에 빌드 서버에 관리자 비밀번호를 넣지 않아도 된다. [docs:history/build_log/05_harbor.md:174] [docs:history/build_log/05_harbor.md:224] 지금 저장소에는 library, petmint, runshoes 세 프로젝트가 있다. [code:apps/harbor-backup/README.md:55]

Harbor는 구성 요소가 일곱이고 그중 다섯이 저장 공간을 쓴다. 이것을 매니페스트로 하나하나 쓰면 설정 파일이 수십 개가 되고 그 안에 주소와 비밀번호가 흩어진다. Helm(여러 매니페스트를 묶은 차트에 값만 넣어 설치하게 해 주는 도구)을 쓰면 바꿀 값을 `platform/harbor/values.yaml` 한 곳에 모을 수 있다. [docs:history/build_log/05_harbor.md:180] Harbor는 ArgoCD 밖에 있어서, 이 파일을 고쳐 `main`에 올려도 클러스터는 바뀌지 않고 사람이 Helm으로 다시 넣는다. [code:bootstrap/root-app.yaml:13] 이렇게 저장소 밖에서 넣은 것은 판을 `platform/versions.yaml`에 따로 적어 둔다. [code:platform/versions.yaml:1-6] 빌드 서버가 이미지를 올리고 태그를 고정하는 과정은 → 「빌드와 태그 고정」에서 다룬다.

## 노드가 이미지를 받아 가는 길

Harbor는 바깥에서 터널을 거쳐 들어오는 공개 주소를 하나 갖고 있지만, 노드는 그 길로 이미지를 받지 않는다. 공개 주소 앞에는 사람만 통과시키는 접근 제한이 걸려 있어 노드가 막히기 때문이다. [code:apps/cloudflared/configmap.yaml:35] [docs:history/build_log/05_harbor.md:208]

대신 노드는 클러스터의 들어오는 문이 쓰는 사설 고정 대역의 주소 하나로 바로 간다. 노드마다 Harbor의 이름을 그 주소로 풀도록 VM을 만들 때 적어 두었다. [code:cluster/Vagrantfile:32-36] 이때도 연결은 암호화되고 인증서를 검증한다. Harbor가 내려받을 때 쓰는 토큰 주소를 HTTPS 공개 주소로 알려 주기 때문에, 노드도 그 이름과 맞는 인증서를 확인해야 한다. [code:platform/harbor/values.yaml:3-4]

처음에는 Harbor가 스스로 만든 인증서를 쓰는 길도 있었다. 그러면 그 인증서를 믿도록 모든 노드에 따로 심어야 하고, 노드를 늘릴 때마다 그 일을 되풀이해야 한다. 그래서 공인 인증 기관에서 받은 인증서를 클러스터의 인증서 관리 도구가 자동으로 받고 갱신하게 했다. 공인 인증서는 노드가 이미 믿고 있으니 노드에 심을 것이 없다. [docs:history/build_log/05_harbor.md:190] [docs:history/build_log/05_harbor.md:208] [code:platform/cert-manager/harbor-certificate.yaml:1] 인증서가 어디서 끝나는지는 → 「바깥 공개와 인증서」에서 다룬다.

들어오는 문에는 올리는 크기의 상한을 없애는 설정을 넣었다. 기본 상한이 작아 그대로 두면 이미지 층이 커서 올리기가 실패한다. [code:platform/harbor/values.yaml:15] [docs:history/build_log/05_harbor.md:217]

## 데이터는 w3 한 곳에

Harbor의 구성 요소는 모두 infra 역할의 워커 w3에서만 뜨게 고정했다. 저장 공간 다섯도 모두 w3에 있다. 이미지 층을 담는 공간이 30Gi로 가장 크고, Harbor의 데이터베이스와 Trivy가 각각 5Gi, 캐시와 작업 기록이 각각 1Gi다. [code:platform/harbor/values.yaml:58-72] [code:platform/harbor/pvc-w3.yaml:8-58]

이 클러스터의 저장 공간은 local-path를 쓴다. local-path는 노드의 디스크를 그대로 잘라 쓰는 방식이라, 한 번 생긴 저장 공간은 처음 붙은 파드가 뜬 노드에 묶인다. 처음 Harbor를 깔았을 때는 구성 요소마다 처음 뜬 노드가 제각각이어서 저장 공간이 세 워커에 흩어졌고, 어느 워커를 내려도 Harbor의 일부가 멈췄다. 묶이는 것은 피할 수 없으니 묶이는 자리를 w3 하나로 정했다. 이제 멈추는 경우는 w3가 내려갈 때 하나만 남는다. [code:platform/harbor/values.yaml:23-25] [code:platform/harbor/pvc-w3.yaml:4] [docs:history/build_log/05_harbor.md:446]

여러 노드에 데이터를 복제하는 분산 저장소를 쓰지 않은 데도 까닭이 있다. 그런 저장소는 클러스터를 하나 더 얹는 만큼 무겁다. 게다가 VM이 모두 같은 물리 서버 한 대 위에 있어서, 노드끼리 복제해도 서버가 꺼지면 함께 꺼진다. 들인 품만큼 얻는 것이 없다. [docs:history/build_log/05_harbor.md:235]

w3로 옮길 때 새 저장 공간을 따로 만들어 붙였고, 옛 저장 공간은 지우지 않고 남겨 두었다. 새 저장 공간 다섯은 지워도 데이터가 바로 사라지지 않게 보존 정책을 Retain으로 바꿔 두었다. 이미지 층을 담는 공간에는 Helm이 업그레이드 때 지우지 않게 하는 표시도 달았다. [code:platform/harbor/pvc-w3.yaml:1-7] [code:platform/harbor/pvc-w3.yaml:13-14]

## Harbor 데이터베이스 백업

프로젝트, 로봇 계정, 태그, 정책 같은 Harbor의 정보는 모두 Harbor 안의 PostgreSQL 데이터베이스에 있다. 이것을 하루 한 번 떠서 서버 쪽으로 옮겨 둔다. Harbor 자체는 Helm으로 넣지만, 이 백업 작업은 `apps/harbor-backup`에 두어 ArgoCD가 자동 Sync로 넣는다. 빌드 서버가 이미지 태그를 커밋하는 앱이 아니고 백업 작업과 저장 공간 설정뿐이라, 바뀌면 곧바로 들어가도 된다고 보았다. [code:apps/harbor-backup/cronjob.yaml:3] [code:apps/harbor-backup/app.yaml:2]

백업은 매일 새벽 서울 시각으로 한 번 돈다. 다른 앱의 백업과 배치 작업이 도는 시각을 피했다. 백업 파일은 쓰는 도중에는 임시 이름으로 두고, 다 쓴 뒤 목차를 읽어 표 데이터가 들어 있는지 확인한 다음에야 제 이름을 붙인다. 반쯤 쓰다 만 파일이 백업으로 남지 않게 하려는 것이다. 파일마다 체크섬도 함께 남긴다. [code:apps/harbor-backup/cronjob.yaml:9] [code:apps/harbor-backup/cronjob.yaml:17-18] [code:apps/harbor-backup/cronjob.yaml:61-67]

백업은 30일 동안 두되, 날짜와 상관없이 가장 최근 7개는 늘 남긴다. 백업이 며칠 실패해도 남은 것이 다 지워지는 일이 없다. [code:apps/harbor-backup/cronjob.yaml:50-53] [code:apps/harbor-backup/cronjob.yaml:69-72] 백업을 뜨는 프로그램은 서버와 같은 Harbor 데이터베이스 이미지를 쓴다. 백업 도구의 판이 서버보다 낮으면 실패하기 때문이다. 그래서 Harbor를 올리면 이 이미지도 함께 올려야 한다. [code:apps/harbor-backup/cronjob.yaml:7]

백업이 쌓이는 곳은 서버(호스트)의 디스크다. 서버가 NFS(망을 거쳐 다른 컴퓨터의 폴더를 제 것처럼 쓰게 하는 방식)로 백업 폴더 하나를 클러스터의 사설망에만 쓰기로 열어 두고, 백업 작업이 그 폴더에 쓴다. 파드가 어느 사용자로 쓰든 서버에서는 서버 사용자의 파일로 저장된다. 서버 쪽 준비는 관리자 권한이 필요해서 사람이 `scripts/host-nfs-harbor-backup-setup.sh`를 한 번 돌린다. [code:scripts/host-nfs-harbor-backup-setup.sh:1-10] 서버의 NFS 공유 전반은 → 「공유 저장소」에서 다룬다.

복구할 때는 운영 데이터베이스를 바로 덮지 않는다. 먼저 따로 띄운 시험 데이터베이스에 넣어 표마다 행 수가 맞는지 본 뒤에 운영에 넣는다. 이 순서로 실제 복구를 시험해, 모든 표의 행 수가 운영과 같게 돌아오는 것까지 확인했다. [code:apps/harbor-backup/README.md:26-28] [code:apps/harbor-backup/README.md:53-55]

## 알려진 한계

- Harbor가 w3 한 노드에만 있다. w3가 내려가면 이미지를 올리고 받는 일이 모두 멈춘다. 이미 떠 있는 앱 파드는 이미지를 노드에 갖고 있어 그대로 돈다 [code:cluster/label-nodes.sh:7]
- 이미지 층은 백업하지 않는다. 데이터베이스만 돌아오면 프로젝트와 로봇 계정은 살아나지만 층이 없는 태그는 내려받을 수 없다. 앱 이미지는 앱 저장소의 커밋에서 다시 빌드할 수 있다는 것을 전제로 한다 [code:apps/harbor-backup/README.md:15-16]
- 백업이 운영 디스크와 같은 물리 서버에 있다. 다른 디스크나 바깥에 한 벌 더 두는 일은 남아 있다 [docs:TODO.md:16]
- w3로 옮기기 전의 옛 저장 공간 다섯이 아직 남아 있다. 사람이 판단해 지운다 [docs:TODO.md:7]
- Harbor 관리자 비밀번호는 저장소에 없고 Helm 릴리스 값에만 있다. 업그레이드 때 빠뜨리면 차트의 기본값이 들어간다 [docs:history/build_log/05_harbor.md:485]
- 분산 저장소가 없어 Harbor의 데이터는 w3의 디스크에만 있다 [code:platform/harbor/pvc-w3.yaml:4]

## 용어 풀이

- 이미지 저장소(레지스트리): 컨테이너 이미지를 올리고 내려받는 서버
- Helm 차트: 여러 매니페스트를 묶고 바꿀 값만 밖으로 꺼낸 설치 꾸러미
- 로봇 계정: 사람이 아닌 빌드 서버나 노드가 쓰도록 권한을 좁혀 만든 계정
- Trivy: 이미지에 든 소프트웨어의 알려진 취약점을 찾아 주는 검사 도구
- local-path: 노드의 디스크 일부를 그대로 저장 공간으로 내주는 방식. 데이터가 그 노드에 묶인다
- Retain: 저장 공간 요청을 지워도 실제 데이터와 볼륨을 남겨 두는 보존 정책
- NFS: 망을 거쳐 다른 컴퓨터의 폴더를 제 폴더처럼 쓰게 하는 공유 방식
- 체크섬: 파일 내용에서 계산한 짧은 값. 다시 계산해 같으면 파일이 바뀌지 않았다는 뜻이다

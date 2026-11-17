<!--
다루는 곳: README.md, cluster/Vagrantfile, apps/cloudflared/configmap.yaml, apps/cloudflared/app.yaml, platform/argocd/ingress.yaml, apps/monitoring/README.md, apps/monitoring/prometheus/configmap.yaml, apps/harbor-backup/README.md, apps/runshoes/README.md, bootstrap/root-app.yaml, scripts/host-gpu-exporter.sh, docs/runbooks/mysql-replica.md
읽은 커밋: ddbaadf
-->
# 하지 않은 것과 한계

> 이 글은 이 홈랩이 막지 못하는 장애, 일부러 하지 않은 일, 아직 원인을 모르는 일을 모아 다룹니다.

**여기 적은 것은 모두 저장소나 확인 기록에 남아 있는 한계입니다. 기록에 없는 약점을 짐작해 덧붙이거나, 기록에 있는 한계를 줄여 쓰지 않았습니다.**

## 왜 따로 적나

앞의 글들은 무엇을 골랐고 왜 골랐는지를 말합니다. 고른 것에는 늘 버린 것이 따라옵니다. 그 버린 쪽을 한곳에 모아야, 이 클러스터가 어디까지 믿을 만하고 어디서부터는 사람이 지켜봐야 하는지가 보입니다. 각 항목은 그 한계가 무엇인지, 그 때문에 무엇이 멈추거나 틀어지는지, 기록에 까닭이 있으면 까닭까지 짧게 적습니다.

## 하드웨어와 클러스터 구조

- **물리 서버가 한 대입니다.** VM 다섯 대가 같은 서버, 같은 디스크 위에 있습니다 [code:README.md:3] [docs:history/build_log/01_cluster.md:699]. 노드를 나눈 것은 VM 하나나 노드 프로그램 하나가 죽는 장애만 막습니다. 서버 자체가 꺼지면 클러스터, 운영 도구, 호스트의 추론 서버가 함께 멈춥니다 [docs:history/build_log/08_scale_out.md:436].
- **컨트롤 플레인(클러스터 전체를 관리하는 노드)이 m-k8s 한 대입니다** [docs:history/cluster_state_20261116.md:11]. m-k8s가 멈추면 이미 떠 있는 파드는 계속 돌지만, 새 배치와 복구, 사람이 내리는 명령이 멈춥니다 [docs:history/build_log/01_cluster.md:700].
- **노드의 대표 주소가 관리용 망에 잡혀 있습니다.** 노드마다 랜카드가 둘인데, 클러스터 통신은 고정 주소 망으로 가도록 맞췄지만 노드 프로그램(kubelet)에 대표 주소를 지정하는 옵션(`--node-ip`)을 주지 않아 대표 주소는 관리용 망 쪽으로 잡혀 있습니다 [docs:history/cluster_state_20261116.md:26]. 의도한 것이 아니라 기본값이 남은 것입니다 [docs:history/human_answers_20261116.md:15]. 관리용 망 주소는 VM을 다시 켤 때 바뀔 수 있고 [docs:history/human_answers_20261116.md:7], 모니터링이 각 노드의 컨테이너 사용량을 긁어 올 때 찾아가는 주소가 이 대표 주소입니다 [code:apps/monitoring/prometheus/configmap.yaml:33-43]. 지금까지 주소가 바뀐 적은 없다고 기록돼 있습니다 [docs:history/build_log/01_cluster.md:702]. 자세한 것은 → 「랜카드 둘: 관리망과 고정망」.
- **이미지 저장소와 배포 도구가 있는 w3, 모니터링이 있는 w4는 한 대씩입니다.** w3이 죽으면 배포와 빌드가, w4가 죽으면 모니터링이 그 노드가 돌아올 때까지 멈춥니다. 목표로 받아들인 한계입니다 [docs:history/build_log/08_scale_out.md:434]. 앱 노드도 둘뿐이라, 하나가 빠지면 각 앱이 파드 하나로 버팁니다 [docs:history/build_log/08_scale_out.md:433]. → 「워커를 늘리고 옮기기」

## 망과 보안

- **NetworkPolicy를 쓰지 않습니다.** NetworkPolicy는 파드 사이 통신을 규칙으로 막고 여는 기능입니다. 파드 망 도구로 Calico를 고른 까닭이 이 기능이 기본으로 들어 있어서였는데 [docs:history/build_log/01_cluster.md:177], 지금 저장소의 매니페스트에는 NetworkPolicy가 하나도 없습니다 [code:apps/] [code:platform/]. 클러스터 안에서는 어느 파드든 다른 파드에 닿을 수 있습니다.
- **cloudflared는 원점 인증서를 확인하지 않습니다.** 바깥 요청을 클러스터로 들여오는 터널 프로그램 cloudflared는 클러스터 안의 들어오는 문(ingress-nginx)까지 HTTPS로 가지만, 상대 인증서 확인을 꺼 두었습니다 [code:apps/cloudflared/configmap.yaml:15-17]. 그 구간에서는 상대가 진짜 ingress-nginx인지 따지지 않습니다. 지금 설정으로 확인을 켜면 일곱 주소 모두 실패한다는 것을 클러스터에서 확인했습니다 [docs:history/notls_check_20261117.md:20-22]. → 「TLS가 끝나는 곳과 noTLSVerify를 확인한 일」
- **사설망 안에서는 HTTP로도 닿습니다.** Ingress(바깥 요청을 주소에 따라 각 서비스로 나눠 주는 규칙)마다 HTTPS로 다시 오라고 돌려보내는 기능을 꺼 두었습니다. 터널은 HTTPS로 붙지만, VM 사설망에서는 암호화하지 않은 HTTP 경로도 그대로 열려 있습니다 [code:platform/argocd/ingress.yaml:7] [code:platform/argocd/ingress.yaml:15].
- **바깥 공개 주소가 모두 터널 하나를 지납니다.** 터널이 깨지면 두 서비스와 함께 ArgoCD, Grafana처럼 고칠 도구와 볼 도구의 화면도 바깥에서 사라집니다. 그래서 터널만은 자동 배포를 켜지 않고 사람이 반영합니다 [code:apps/cloudflared/app.yaml:4-7].

## 사람 손에 남은 것

- **비밀값은 저장소에 없고, 사람이 클러스터에 직접 만듭니다** [code:README.md:14] [code:CLAUDE.md:46]. 비밀값이 커밋에 새지 않는 대신, 클러스터를 다시 세우면 사람이 다시 넣어야 합니다.
- **호스트 서비스는 GitOps 밖입니다.** 추론 서버, 벡터 DB, 검색 서비스 같은 것은 VM이 아니라 호스트에서 컨테이너나 서비스로 돕니다 [docs:history/cluster_state_20261116.md:77-78]. 저장소로 상태를 되돌릴 수 없습니다. GPU 지표 수집기는 사라지면 사람이 스크립트를 다시 돌려 띄우고 [docs:history/build_log/09_monitoring.md:124] [code:scripts/host-gpu-exporter.sh:11], 다른 호스트 서비스를 어떻게 다시 띄우는지는 이 저장소에 기록이 없습니다. → 「GPU는 호스트에, 파드는 불러 쓰기만」
- **데이터베이스 원본이 죽으면 사람이 사본을 올립니다.** 자동 전환은 없습니다 [docs:runbooks/mysql-replica.md:3]. 자동 전환 도구는 부품과 메모리를 더 먹어 쓰지 않았습니다 [docs:history/build_log/08_scale_out.md:134-137]. 사람이 알아채고 올리기 전까지 두 앱의 쓰기는 실패합니다 [docs:history/build_log/08_scale_out.md:28]. 올리는 시험은 했지만, 앱 트래픽까지 옮기는 진짜 전환은 아직 해 보지 않았습니다 [docs:history/build_log/08_scale_out.md:432].
- **알림이 없습니다.** 모니터링은 지표와 로그를 모으고 대시보드로 보여 주지만, 알림을 보내는 구성 요소는 아직 없습니다. 무엇을 누구에게 알릴지 정하기 전입니다 [code:apps/monitoring/README.md:3]. 문제는 사람이 대시보드를 열어야 보입니다.
- **저장소에서 지운 것은 클러스터에 남습니다.** 루트 Application에서 지운 리소스를 클러스터에서도 지우는 기능(prune)을 꺼 두었습니다. 사람이 따로 지워야 합니다 [code:bootstrap/root-app.yaml:11].

- **이미지 취약점 검사 결과를 보고 조치하는 기준이 없습니다.** 포트폴리오 그림을 찍으며 처음 돌린 검사에서 이미지마다 Critical 22건이 나왔고, 22건 모두 고친 판이 나와 있다는 뜻의 Fixable이었습니다. 베이스 이미지를 올리면 줄어들 것으로 보이지만 확인한 것은 아니고, 아직 아무것도 고치지 않았습니다 [docs:history/human_answers_20261117.md:19-23].

## 백업

- **백업이 운영 디스크와 같은 물리 서버에 있습니다.** 호스트의 백업 폴더와 VM 디스크가 같은 서버, 같은 NVMe입니다 [docs:history/build_log/08_scale_out.md:435]. 다른 디스크나 바깥에 한 벌 더 두는 일은 남은 일로 적혀 있습니다 [docs:TODO.md:16].
- **런슈즈 데이터베이스는 정기 백업이 없습니다.** 구조를 바꾸는 배포 앞에 손으로 뜨는 덤프가 전부입니다 [code:apps/runshoes/README.md:54].
- **이미지 저장소의 이미지 층은 백업하지 않습니다.** Harbor 데이터베이스만 백업하므로 층이 사라진 태그는 내려받을 수 없습니다. 앱 이미지는 앱 저장소의 커밋에서 다시 빌드할 수 있다는 것을 전제로 합니다 [code:apps/harbor-backup/README.md:15-16].

## 원인을 모르는 것

- **ingress-nginx를 다시 띄울 때 12초 동안 모든 주소가 끊긴 일이 있었고, 그 원인은 확인하지 못했습니다** [docs:history/build_log/08_scale_out.md:249-251]. 그 뒤 ingress-nginx를 두 개로 늘렸지만, 하나씩 교체할 때도 1초 한 번은 모든 주소가 응답하지 않았습니다. 0은 아닙니다 [docs:history/build_log/08_scale_out.md:441]. → 「워커를 늘리고 옮기기」

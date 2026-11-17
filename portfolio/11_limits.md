<!--
다루는 곳: README.md, cluster/Vagrantfile, apps/cloudflared/configmap.yaml, apps/cloudflared/app.yaml, platform/argocd/ingress.yaml, apps/monitoring/README.md, apps/monitoring/prometheus/configmap.yaml, apps/harbor-backup/README.md, apps/runshoes/README.md, bootstrap/root-app.yaml, scripts/host-gpu-exporter.sh, docs/runbooks/mysql-replica.md
읽은 커밋: ddbaadf
-->
# 하지 않은 것과 한계

> 이 글은 이 홈랩이 막지 못하는 장애와 일부러 하지 않은 일을 모아 다룹니다.

**여기 적은 것은 모두 저장소나 확인 기록에 남아 있는 한계입니다. 기록에 없는 약점을 짐작해 덧붙이거나, 기록에 있는 한계를 줄여 쓰지 않았습니다. 안 하는 까닭을 한 줄로 쓸 수 있는 것만 한계로 두고, 아직 하지 않은 일은 저장소의 할 일 목록에 따로 둡니다 [c:a40b111].**

## 왜 따로 적나

앞의 글들은 무엇을 골랐고 왜 골랐는지를 말합니다. 고른 것에는 늘 버린 것이 따라옵니다. 그 버린 쪽을 한곳에 모아야, 이 클러스터가 어디까지 믿을 만하고 어디서부터는 사람이 지켜봐야 하는지가 보입니다. 각 항목은 그 한계가 무엇인지, 그 때문에 무엇이 멈추거나 틀어지는지, 기록에 까닭이 있으면 까닭까지 짧게 적습니다.

## 하드웨어와 클러스터 구조

- **물리 서버가 한 대입니다.** VM 다섯 대가 같은 서버, 같은 디스크 위에 있습니다 [code:cluster/Vagrantfile:3-10] [code:CLAUDE.md:8] [docs:history/build_log/01_cluster.md:699]. 노드를 나눈 것은 VM 하나나 노드 프로그램 하나가 죽는 장애만 막습니다. 서버 자체가 꺼지면 클러스터, 운영 도구, 호스트의 추론 서버가 함께 멈춥니다 [docs:history/build_log/08_scale_out.md:436].
- **컨트롤 플레인(클러스터 전체를 관리하는 노드)이 m-k8s 한 대입니다** [docs:history/cluster_state_20261116.md:11]. m-k8s가 멈추면 이미 떠 있는 파드는 계속 돌지만, 새 배치와 복구, 사람이 내리는 명령이 멈춥니다 [docs:history/build_log/01_cluster.md:700]. 늘리려면 클러스터 상태를 저장하는 etcd가 과반으로 결정하는 방식이라 셋이 필요합니다. 그런데 VM이 모두 같은 물리 서버 한 대 위에 있어, 셋으로 늘려도 서버가 꺼지면 함께 꺼집니다. 들이는 자원만큼 얻는 것이 없습니다 [c:a40b111].
- **이미지 저장소와 배포 도구가 있는 w3, 모니터링이 있는 w4는 한 대씩입니다.** w3이 죽으면 배포와 빌드가, w4가 죽으면 모니터링이 그 노드가 돌아올 때까지 멈춥니다. 목표로 받아들인 한계입니다 [docs:history/build_log/08_scale_out.md:434]. 앱 노드도 둘뿐이라, 하나가 빠지면 각 앱이 파드 하나로 버팁니다 [docs:history/build_log/08_scale_out.md:433]. → 「워커를 늘리고 옮기기」

## 망과 보안

- **cloudflared는 원점 인증서를 확인하지 않습니다.** 바깥 요청을 클러스터로 들여오는 터널 프로그램 cloudflared는 클러스터 안의 들어오는 문(ingress-nginx)까지 HTTPS로 가지만, 상대 인증서 확인을 꺼 두었습니다 [code:apps/cloudflared/configmap.yaml:15-17]. 그 구간에서는 상대가 진짜 ingress-nginx인지 따지지 않습니다. 지금 설정으로 확인을 켜면 일곱 주소 모두 실패한다는 것을 클러스터에서 확인했습니다 [docs:history/notls_check_20261117.md:20-22]. → 「TLS가 끝나는 곳과 noTLSVerify를 확인한 일」
- **사설망 안에서는 HTTP로도 닿습니다.** Ingress(바깥 요청을 주소에 따라 각 서비스로 나눠 주는 규칙)마다 HTTPS로 다시 오라고 돌려보내는 기능을 꺼 두었습니다. 터널은 HTTPS로 붙지만, VM 사설망에서는 암호화하지 않은 HTTP 경로도 그대로 열려 있습니다 [code:platform/argocd/ingress.yaml:7] [code:platform/argocd/ingress.yaml:15].
- **바깥 공개 주소가 모두 터널 하나를 지납니다.** 터널이 깨지면 두 서비스와 함께 ArgoCD, Grafana처럼 고칠 도구와 볼 도구의 화면도 바깥에서 사라집니다. 그래서 터널만은 자동 배포를 켜지 않고 사람이 반영합니다 [code:apps/cloudflared/app.yaml:4-7].

## 사람 손에 남은 것

- **비밀값은 저장소에 없고, 사람이 클러스터에 직접 만듭니다** [code:CLAUDE.md:46]. 비밀값이 커밋에 새지 않는 대신, 클러스터를 다시 세우면 사람이 다시 넣어야 합니다.
- **호스트 서비스는 GitOps 밖입니다.** 추론 서버, 벡터 DB, 검색 서비스 같은 것은 VM이 아니라 호스트에서 컨테이너나 서비스로 돕니다 [docs:history/cluster_state_20261116.md:77-78]. 저장소로 상태를 되돌릴 수 없습니다. GPU 지표 수집기는 사라지면 사람이 스크립트를 다시 돌려 띄우고 [docs:history/build_log/09_monitoring.md:124] [code:scripts/host-gpu-exporter.sh:11]. → 「GPU는 호스트에, 파드는 불러 쓰기만」
- **데이터베이스 원본이 죽으면 사람이 사본을 올립니다.** 자동 전환은 없습니다 [docs:runbooks/mysql-replica.md:3]. 자동 전환 도구는 부품과 메모리를 더 먹어 쓰지 않았습니다 [docs:history/build_log/08_scale_out.md:134-137]. 사람이 알아채고 올리기 전까지 두 앱의 쓰기는 실패합니다 [docs:history/build_log/08_scale_out.md:28]. 올리는 시험은 했지만, 앱 트래픽까지 옮기는 진짜 전환은 아직 해 보지 않았습니다 [docs:history/build_log/08_scale_out.md:432].
- **저장소에서 지운 것은 클러스터에 남습니다.** 루트 Application에서 지운 리소스를 클러스터에서도 지우는 기능(prune)을 꺼 두었습니다. 사람이 따로 지워야 합니다 [code:bootstrap/root-app.yaml:11].

## 백업

- **이미지 저장소의 이미지 층은 백업하지 않습니다.** Harbor 데이터베이스만 백업하므로 층이 사라진 태그는 내려받을 수 없습니다. 앱 이미지는 앱 저장소의 커밋에서 다시 빌드할 수 있다는 것을 전제로 합니다 [code:apps/harbor-backup/README.md:15-16].

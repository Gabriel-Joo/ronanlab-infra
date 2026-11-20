<!--
다루는 곳: bootstrap/root-app.yaml, cluster/Vagrantfile
읽은 커밋: 736d833
-->
# 전체 그림

GPU 호스트 한 대 안의 VM 다섯 대로 세운 kubeadm 클러스터와, 그 위의 앱 둘과 운영 도구를 한 장에 모은다. 각 부분의 설정과 명령은 같은 번호의 개발자 문서에 있다.

## 저장소 구조

처음 오는 사람은 문서 차례 [docs/README.md](README.md)부터 본다. 폴더는 아래와 같다.

| 폴더 | 무엇 |
| --- | --- |
| `bootstrap/root-app.yaml` | 루트 Application(App of Apps). `main`의 `apps/*/app.yaml`을 읽어 앱 Application을 만든다 [code:bootstrap/root-app.yaml:22-28] |
| `apps/` | ArgoCD가 배포하는 것. petmint, runshoes, cloudflared, harbor-backup, monitoring [code:apps/] |
| `platform/` | ArgoCD 밖에서 사람이 Helm이나 kubectl로 넣은 기반. cert-manager, coredns, ingress-nginx, metallb, harbor, jenkins, argocd ingress [code:bootstrap/root-app.yaml:13] [repo:CLAUDE.md:13] |
| `cluster/` | VM 정의 `Vagrantfile`, 노드 설치 `setup-node.sh`, 역할 라벨 `label-nodes.sh`. 앞의 둘은 호스트 `~/k8s-cluster`의 사본이라 고치면 양쪽을 같이 고친다 [repo:CLAUDE.md:16-18] |
| `scripts/` | 호스트 스크립트(`host-nfs-harbor-backup-setup.sh`는 sudo로 사람이 돌린다), 배포 키, MySQL 복제 맞추기와 확인, 문서 점검 [code:scripts/host-nfs-harbor-backup-setup.sh:3] [code:scripts/] |
| `docs/` | 개발자 문서(00~14), 남은 일 `TODO.md`, 기록 `history/`. 노션 원고는 `notion/`, 포트폴리오는 `portfolio/` [docs:README.md] |

## 지금 구성

### 호스트

- 물리 서버 한 대. Ubuntu 26.04.1 LTS, 커널 7.0.0-42-generic, 32코어, 메모리 61GiB [docs:history/cluster_state_20261116.md:75]
- GPU: NVIDIA GeForce RTX 5070 Ti, 드라이버 595.99.02, 메모리 16303MiB [docs:history/cluster_state_20261116.md:76]
- libvirt 망 둘: `default`(virbr0, 192.168.122.0/24)와 `vagrant-libvirt`(192.168.121.0/24) [docs:history/cluster_state_20261116.md:28]
- 호스트에서 도는 것: Ollama, Open WebUI, Milvus, nvidia-gpu-exporter, MySQL 셋(Docker), cloudflared-ollama, model-service, petmint-search, NFS 서버(systemd) [docs:history/cluster_state_20261116.md:77-78]

### 노드

| 노드 | 역할 | CPU | 메모리(MiB) | eth1 고정 주소 | 역할 라벨 |
| --- | --- | --- | --- | --- | --- |
| m-k8s | control-plane | 2 | 4096 | 192.168.122.10 | 없음 |
| w1-k8s | 워커 | 2 | 8192 | 192.168.122.11 | app |
| w2-k8s | 워커 | 2 | 8192 | 192.168.122.12 | app |
| w3-k8s | 워커 | 2 | 8192 | 192.168.122.13 | infra |
| w4-k8s | 워커 | 2 | 8192 | 192.168.122.14 | platform |

- 값의 근거: [code:cluster/Vagrantfile:3-10] [docs:history/cluster_state_20261116.md:9-15]
- 박스 `generic/ubuntu2204`, provider libvirt [code:cluster/Vagrantfile:1] [code:cluster/Vagrantfile:19-23]
- 다섯 대 모두 Ubuntu 22.04.3 LTS, kubelet v1.35.9, containerd 2.2.1 [docs:history/cluster_state_20261116.md:17]
- 라벨 뜻: app은 앱과 MySQL(w1 Primary, w2 Replica), infra는 Harbor, Jenkins, ArgoCD, platform은 모니터링 [code:cluster/label-nodes.sh:6-8]
- 노드마다 랜카드 둘. eth0은 vagrant-libvirt 관리망(DHCP), eth1은 클러스터용 고정망 [docs:history/human_answers_20261116.md:7-9]

### 클러스터 위의 것

| 무엇 | 네임스페이스 | 넣는 길 | 자리 |
| --- | --- | --- | --- |
| petmint(펫보험 상담 RAG) | petmint | ArgoCD 자동 Sync | `apps/petmint/` |
| runshoes(러닝화 스펙 아카이브) | runshoes | ArgoCD 자동 Sync | `apps/runshoes/` |
| 모니터링(Prometheus, Grafana, Loki, Alloy 등) | monitoring | ArgoCD 자동 Sync | `apps/monitoring/` |
| Harbor DB 백업 | harbor | ArgoCD 자동 Sync | `apps/harbor-backup/` |
| Cloudflare 터널 커넥터 | cloudflared | ArgoCD 수동 Sync | `apps/cloudflared/` |
| cert-manager, coredns, ingress-nginx, metallb, harbor, jenkins, argocd ingress | 각각 | 사람이 helm, kubectl | `platform/` |

- 앱 설명: [docs:history/build_log/07_project_deploy.md:16] [repo:apps/runshoes/README.md:3]
- Sync 방식: [docs:history/cluster_state_20261116.md:54-61]
- `platform/`이 ArgoCD 밖인 것: [code:bootstrap/root-app.yaml:13]
- 모니터링 구성: [repo:apps/monitoring/README.md:3-6]
- 두 앱 모두 앱 파드 2개(w1, w2)와 MySQL Primary(w1), Replica(w2) [docs:history/build_log/07_project_deploy.md:3]

### 흐름

- 배포: 앱 저장소 push, Jenkins 빌드, Harbor push, 이 저장소 `apps/<앱>/kustomization.yaml` 태그 커밋, ArgoCD 자동 Sync, 롤링 [docs:history/build_log/07_project_deploy.md:3] [code:apps/petmint/app.yaml:1]
- 바깥 공개: 클러스터 안 cloudflared 파드 2개가 터널 `ronanlab-tunnel` 하나로 공개 주소 일곱을 받아 모두 `ingress-nginx-controller.ingress-nginx.svc.cluster.local:443`으로 보낸다 [repo:apps/cloudflared/README.md:3-4] [code:apps/cloudflared/deployment.yaml:13] [docs:history/cluster_state_20261116.md:50]
- 안쪽 문: MetalLB VIP 192.168.122.240(ingress-nginx LoadBalancer, 80과 443) [docs:history/cluster_state_20261116.md:34]
- 인증서: cert-manager, ClusterIssuer `letsencrypt-prod`, Certificate 다섯 [docs:history/cluster_state_20261116.md:48]
- GPU 추론: 파드가 호스트의 Ollama(11434), model-service(8200), Milvus(19530), search(8100)를 192.168.122.1로 부른다 [docs:history/cluster_state_20261116.md:80]

## 설정 자리

| 파일 | 뜻 |
| --- | --- |
| `bootstrap/root-app.yaml:22-28` | 루트 Application. `main`의 `apps/*/app.yaml`만 읽는다 [code:bootstrap/root-app.yaml:22-28] |
| `bootstrap/root-app.yaml:33-43` | 자식 `spec.syncPolicy`를 덮지 않는다, 루트는 자동 Sync이고 prune과 selfHeal 끔 [code:bootstrap/root-app.yaml:33-43] |
| `apps/<앱>/app.yaml` | 앱별 Application. 모두 `targetRevision: main` [code:apps/petmint/app.yaml:18-21] |
| `cluster/Vagrantfile` | VM 다섯 대 정의 [code:cluster/Vagrantfile:3-10] |
| `cluster/label-nodes.sh` | 노드 역할 라벨 [code:cluster/label-nodes.sh:10-14] |
| `platform/versions.yaml` | 저장소 밖에서 넣은 것의 판 [code:platform/versions.yaml:8-53] |

## 바꾸거나 다시 만들기

- 루트 Application은 사람이 한 번만 넣는다. 그 뒤 앱은 `apps/<이름>/`에 `app.yaml`과 매니페스트를 넣고 push하면 생긴다 [code:bootstrap/root-app.yaml:1-3]

```
kubectl apply -f bootstrap/root-app.yaml
```

- 부분별 절차는 같은 번호의 개발자 문서에 있다(차례는 `docs/style_guide.md` 1절) [docs:style_guide.md:5-41]

## 확인

호스트에는 kubectl이 없어 m-k8s에서 친다 [repo:CLAUDE.md:27]

```
cd ~/k8s-cluster && vagrant status                                   # 다섯 대 running
vagrant ssh m-k8s -c 'kubectl get nodes -L node.ronanlab.dev/role'   # 다섯 대 Ready, v1.35.9, 라벨 app app infra platform
vagrant ssh m-k8s -c 'kubectl -n argocd get applications'            # root 와 앱 다섯이 Synced, Healthy
```

기대 결과의 근거: [docs:history/cluster_state_20261116.md:9-17] [docs:history/cluster_state_20261116.md:54-61]

## 알려진 한계

- 모든 것이 물리 서버 한 대 안에 있다. 호스트가 멈추면 클러스터, 운영 도구, 추론 서버가 함께 멈춘다 [code:cluster/Vagrantfile:3-10] [repo:CLAUDE.md:8]
- control-plane은 m-k8s 한 대다 [docs:history/cluster_state_20261116.md:11]
- 공개 주소 일곱이 터널 하나를 지난다. 터널이 깨지면 ArgoCD, Grafana 화면도 바깥에서 안 보인다 [code:apps/cloudflared/app.yaml:4-7]
- 노드 InternalIP가 eth0(DHCP) 주소로 잡혀 있다. kubelet에 `--node-ip`가 없어서다 [docs:history/cluster_state_20261116.md:26] [docs:history/human_answers_20261116.md:15]

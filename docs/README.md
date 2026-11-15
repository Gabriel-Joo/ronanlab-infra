# ronanlab-infra docs

이 디렉터리가 인프라 문서의 원본이다(2026-11-10부터). 노션 「프로젝트 / 인프라」 아래 문서는 사람이 처음 쓴 기록이고,
2026-11-12 여기로 옮기면서 지금 코드 · 클러스터와 맞췄다. 노션과 다르면 이 문서와 저장소의 코드가 맞다.

## 차례

Notion 게시는 이 표의 순서를 따른다. 「노션 제목」은 각 문서 맨 위 제목 줄과 같다. 줄 순서가 곧 차례다.
첫 칸은 백틱 파일 이름만 둔다(게시기가 읽는다, FOREMAN bridge/docsync.py table_rows).

| 파일 | 노션 제목 | 내용 |
| --- | --- | --- |
| `00_server.md` | [인프라/서버 구축(하드웨어)](00_server.md) | 물리 GPU 서버: 네트워크, OS · 드라이버 · CUDA, 원격 접속, Docker(Ollama · Open WebUI), GPU 운영 규칙 |
| `kubernetes_install.md` | [쿠버네티스 설치](kubernetes_install.md) | 01~09의 머리: 목표, 전체 구조, 설계 원칙, 13단계 순서와 진행 상황 |
| `01_cluster.md` | [01. 클러스터 구축](01_cluster.md) | KVM/libvirt · Vagrant VM 5대, containerd · kubeadm 1.35.9, Calico, 노드 추가 · 메모리 절차 |
| `02_metrics_storage_ingress.md` | [02. 메트릭·스토리지·Ingress](02_metrics_storage_ingress.md) | metrics-server, local-path, ingress-nginx, MetalLB, cert-manager, CoreDNS rewrite |
| `03_cloudflare_tunnel.md` | [03. Cloudflare Tunnel 연결](03_cloudflare_tunnel.md) | 도메인, ronanlab-tunnel(공개 주소 일곱) · ollama-tunnel, Access |
| `04_argocd.md` | [04. ArgoCD](04_argocd.md) | 설치, App of Apps, 자동 · 수동 Sync, 웹훅 · 알림 |
| `05_harbor.md` | [05. Harbor](05_harbor.md) | Helm 설치, values, 스토리지(w3), DB 백업 |
| `06_jenkins.md` | [06. Jenkins](06_jenkins.md) | Helm 설치, BuildKit rootless, 로봇 계정, 플러그인 고정, 파이프라인 |
| `07_project_deploy.md` | [07. 프로젝트 배포](07_project_deploy.md) | petmint · runshoes: Secret, Kustomize, Jenkins → Harbor → ArgoCD, MySQL, Ingress |
| `08_scale_out.md` | [08. 구조 확장·이관](08_scale_out.md) | 가용성: 노드 역할 배치, 앱 분산, Harbor · ArgoCD 이사, MySQL Replica, 노드 정비 절차 |
| `09_monitoring.md` | [09. 모니터링](09_monitoring.md) | Prometheus · Grafana · Loki를 왜 이렇게 세웠나, 설치 기록(지금 구성은 `apps/monitoring/README.md`) |
| `history/cloudflare_tunnel_vcluster.md` | [Cloudflare Tunnel 세팅 (vcluster 시절)](history/cloudflare_tunnel_vcluster.md) | 학교 vcluster 시절 RUNSHOES 터널 · CI 기록과 시행착오 |

history/ 아래 문서는 게시기가 표 순서로 읽지 못해 맨 뒤에 붙는다.

모든 문서는 같은 꼴이다: 제목 줄, 머리 세 줄(요약 · 날짜 · 범위 · 코드), 절 다섯(1. 지금 구성 / 2. 왜 이렇게 했나 / 3. 진행 기록 / 4. 남은 한계 / 5. 확인 방법). 말투는 한다체.

## 지키는 것

문서를 새로 쓰거나 고칠 때도 이 셋을 지킨다(2026-11-16 사용자).

- **원격 태그 `archive/main-before-reword-20261113`은 지우지 않는다. 문서 속 옛 커밋 해시(10개)도 고치지 않는다.** 2026-11-13 커밋 메시지를 다시 쓰며 force push해서 그 앞 커밋의 해시가 모두 바뀌었다. 문서 여러 곳이 옛 해시를 가리키는데, 그 해시는 이 태그가 있어야 GitHub에서 열린다. 해시를 새 것으로 바꾸는 커밋을 또 만들면 이력에 쌓이기만 하므로, 옛 해시는 태그로 찾는다.
- **공개되는 글에 서버 IP와 포트를 적지 않는다. 도메인 ronanlab.dev는 적어도 된다.** 도메인은 Cloudflare 공개 주소로 이미 밖에 드러나 있다. IP와 포트는 서버가 어디 있고 무엇이 열려 있는지를 알려 주므로 공개하지 않는다.
- **사설 대역 주소(MetalLB VIP 등)와 자기 자신 주소(localhost)는 저장소 문서에 숫자로 둬도 된다. 노션 공개 판에는 숫자를 넣지 않고 역할로 적는다.** 「클러스터 내부 주소」, 「호스트에서 도는 추론 서버」처럼 쓴다. 이 주소들은 밖에서 닿지 않아 바로 위 줄의 서버 IP와 포트에 들지 않는다(2026-11-16 사용자).

## 그 밖의 문서

| 문서 | 내용 |
| --- | --- |
| [runbooks/mysql-replica.md](runbooks/mysql-replica.md) | MySQL Replica 구성 · 다시 만들기 · 수동 승격 · 되돌리기, 시험 기록 |
| [TODO.md](TODO.md) | 남은 일. 한 줄에 하나, 상세는 각 문서 4절 |
| [history/notion_sync_20261112.md](history/notion_sync_20261112.md) | 노션에서 옮기며 코드와 달라 고친 것, 판단하지 못해 남긴 것 |

앱별 운영 문서는 그 앱 디렉터리에 있다: `apps/<앱>/README.md`, `apps/runshoes/runbooks/`. 모니터링 구성 · 접속은 `apps/monitoring/README.md`.

## 같이 보는 문서(앱 저장소)

- 펫퍼민트 `petmint-rag-chatbot/docs/02_pipeline/14_deployment.md`(배포), `12_data_storage.md` 1-5절(MySQL 백업 · 복구), `13_access_and_tunnel.md`(Access · 터널)
- 런슈즈 `runshoes/docs/06_deployment.md`(배포)

# ronanlab-infra docs

인프라 문서는 두 벌이다. `docs/00_overview.md` ~ `14_operations.md`는 운영하는 사람이 보는 개발자 문서이고, 저장소 맨 위 `notion/`은 비개발자도 읽는 노션 기술문서 원고다. 두 벌은 같은 번호와 같은 편 나눔을 쓴다. 코드와 지금 상태가 원칙이고 문서가 그것을 따른다. 쓰는 법과 점검은 [style_guide.md](style_guide.md), `python3 scripts/docs-check.py`(2026-11-16 새로 씀). 같은 스크립트가 포트폴리오 `portfolio/` 열두 편도 점검한다. 포트폴리오는 기술문서와 따로 자기 편끼리 읽은 커밋 하나를 쓰고, 도메인은 ronanlab.dev만 된다(2026-11-17).

노션에는 `notion/` 원고만 올라간다(`.foreman/notion.toml`의 `src`). 게시기가 머리 주석, 근거 표시, 저장소 링크를 떼고 맨 아래 갱신 줄에 읽은 커밋을 적는다.

- 코드를 고치면 그 코드를 가리키는 문서도 같은 브랜치에서 고친다. 걸리는 문서는 `python3 scripts/docs_for_code.py <코드 경로>` 또는 `--range main...HEAD --unfixed`로 본다(2026-11-17, 규칙은 [style_guide.md](style_guide.md) 7절)

## 차례

| 번호 | 개발자 문서 | 노션 원고 | 다루는 것 |
| --- | --- | --- | --- |
| 00 | [00_overview.md](00_overview.md) | `notion/00_overview.md` | 전체 그림 |
| 01 | [01_server.md](01_server.md) | `notion/01_server/` | 물리 서버, 사무실 망, OS와 드라이버, 원격 접속(근거는 노션 하드웨어 기록) |
| 02 | [02_nodes.md](02_nodes.md) | `notion/02_nodes/` | VM 다섯 대, 랜카드 둘, 노드 설치, 역할 라벨과 워커 증설 |
| 03 | [03_kubernetes.md](03_kubernetes.md) | `notion/03_kubernetes.md` | kubeadm, Calico, CoreDNS, 저장소 밖 설치물의 판 |
| 04 | [04_ingress.md](04_ingress.md) | `notion/04_ingress.md` | MetalLB, ingress-nginx |
| 05 | [05_public.md](05_public.md) | `notion/05_public/` | Cloudflare 터널, 공개 경로와 내부 경로, 인증서와 TLS |
| 06 | [06_gitops.md](06_gitops.md) | `notion/06_gitops.md` | ArgoCD, App of Apps, Sync |
| 07 | [07_registry.md](07_registry.md) | `notion/07_registry.md` | Harbor와 그 백업 |
| 08 | [08_build.md](08_build.md) | `notion/08_build.md` | Jenkins, 이미지 태그 고정 |
| 09 | [09_deploy.md](09_deploy.md) | `notion/09_deploy/` | 앱 매니페스트, 처음 배포와 시크릿, 버전이 바뀌는 길(런슈즈 런북 15편) |
| 10 | [10_database.md](10_database.md) | `notion/10_database.md` | MySQL 복제와 백업 |
| 11 | [11_gpu.md](11_gpu.md) | `notion/11_gpu.md` | 호스트 GPU와 클러스터가 부르는 호스트 서비스 |
| 12 | [12_monitoring.md](12_monitoring.md) | `notion/12_monitoring/` | 지표, 로그, 대시보드 |
| 13 | [13_storage.md](13_storage.md) | `notion/13_storage.md` | local-path, 호스트 NFS |
| 14 | [14_operations.md](14_operations.md) | `notion/14_operations.md` | 운영 규칙과 문서 게시 |

## 지키는 것

문서를 새로 쓰거나 고칠 때도 이 셋을 지킨다(2026-11-16 사용자).

- **원격 태그 `archive/main-before-reword-20261113`은 지우지 않는다. 문서 속 옛 커밋 해시(10개)도 고치지 않는다.** 2026-11-13 커밋 메시지를 다시 쓰며 force push해서 그 앞 커밋의 해시가 모두 바뀌었다. 문서 여러 곳이 옛 해시를 가리키는데, 그 해시는 이 태그가 있어야 GitHub에서 열린다. 해시를 새 것으로 바꾸는 커밋을 또 만들면 이력에 쌓이기만 하므로, 옛 해시는 태그로 찾는다.
- **공개되는 글에 서버 IP와 포트를 적지 않는다. 도메인 ronanlab.dev는 적어도 된다.** 도메인은 Cloudflare 공개 주소로 이미 밖에 드러나 있다. IP와 포트는 서버가 어디 있고 무엇이 열려 있는지를 알려 주므로 공개하지 않는다.
- **사설 대역 주소(MetalLB VIP 등)와 자기 자신 주소(localhost)는 저장소 문서에 숫자로 둬도 된다. 노션 공개 판에는 숫자를 넣지 않고 역할로 적는다.** 「클러스터 내부 주소」, 「호스트에서 도는 추론 서버」처럼 쓴다. 이 주소들은 밖에서 닿지 않아 바로 위 줄의 서버 IP와 포트에 들지 않는다(2026-11-16 사용자).

노션 원고는 이보다 더 좁게 쓴다. 도메인, 홈 경로, 토큰 꼴 문자열도 넣지 않는다(style_guide 4절, 점검 스크립트가 막는다).

## 그 밖의 문서

| 문서 | 내용 |
| --- | --- |
| [runbooks/mysql-replica.md](runbooks/mysql-replica.md) | MySQL Replica 구성, 다시 만들기, 수동 승격, 되돌리기, 시험 기록 |
| [TODO.md](TODO.md) | 남은 일. 한 줄에 하나 |
| [history/build_log/](history/build_log/) | 옛 문서 00~09와 kubernetes_install.md. 구축하면서 그때그때 남긴 기록이고, 옛 커밋 해시가 여기 있다 |
| [history/cluster_state_20261116.md](history/cluster_state_20261116.md) | 새 문서를 쓰기 전에 본 클러스터와 호스트 상태 |
| [history/human_answers_20261116.md](history/human_answers_20261116.md) | 사람이 답한 설계 까닭(랜카드 둘 등) |
| [history/notion_hardware_20261116.md](history/notion_hardware_20261116.md) | 노션 하드웨어 기록에서 고른 사실, 노션과 지금이 다른 곳 |
| [history/notion_sync_20261112.md](history/notion_sync_20261112.md) | 노션에서 옮기며 코드와 달라 고친 것 |
| [history/cloudflare_tunnel_vcluster.md](history/cloudflare_tunnel_vcluster.md) | 학교 vcluster 시절 터널과 CI 기록 |

앱별 운영 문서는 그 앱 디렉터리에 있다: `apps/<앱>/README.md`, `apps/runshoes/runbooks/`. 모니터링 구성과 접속은 `apps/monitoring/README.md`.

## 같이 보는 문서(앱 저장소)

- 펫퍼민트 `petmint-rag-chatbot/docs/02_pipeline/14_deployment.md`(배포), `12_data_storage.md` 1-5절(MySQL 백업과 복구), `13_access_and_tunnel.md`(Access와 터널)
- 런슈즈 `runshoes/docs/06_deployment.md`(배포)

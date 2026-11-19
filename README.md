<!-- 이 파일은 `tools/docs.py readme`가 만든다. 손으로 고치면 다음에 만들 때 날아간다. 소개는 포트폴리오 00편 첫 문단, 편 목록은 원고 첫 # 줄, 노션 주소는 게시 기록에서 온다 -->
# ronanlab-infra

GPU가 든 서버 한 대 안에 가상 머신 다섯 대로 쿠버네티스 클러스터를 직접 세우고, 그 위에서 실제로 공개된 서비스 둘과 배포, 이미지 저장, 모니터링 도구를 운영합니다. 바깥 요청은 Cloudflare 터널로 들어오고, 언어 모델 추론은 클러스터 밖 호스트의 GPU가 맡습니다.

## 포트폴리오

[노션에서 보기](https://app.notion.com/p/00-41b3218bb52481a882a9d2498369ca0a)

| 번호 | 제목 | 하위 |
|---|---|---|
| 00 | [한눈에 보는 홈랩](portfolio/00_overview.md) |  |
| 01 | [손으로 세운 여러 노드 클러스터](portfolio/01_kubeadm.md) |  |
| 02 | [랜카드 둘: 관리망과 고정망](portfolio/02_two_nics.md) |  |
| 03 | [문은 하나만: MetalLB와 ingress-nginx](portfolio/03_one_door.md) |  |
| 04 | [포트포워딩 없이 공개하기](portfolio/04_tunnel.md) |  |
| 05 | [TLS가 끝나는 곳과 noTLSVerify를 확인한 일](portfolio/05_tls.md) |  |
| 06 | [GPU는 호스트에, 파드는 불러 쓰기만](portfolio/06_gpu.md) |  |
| 07 | [사람 손을 타지 않는 배포](portfolio/07_delivery.md) |  |
| 08 | [모니터링은 차트 대신 매니페스트로](portfolio/08_monitoring.md) |  |
| 09 | [워커를 늘리고 옮기기](portfolio/09_scale_out.md) |  |
| 10 | [문서를 기계로 검사하기](portfolio/10_docs.md) |  |
| 11 | [알려진 한계](portfolio/11_limits.md) |  |

## 기술문서

[노션에서 보기](https://app.notion.com/p/41b3218bb52481d4a890cb2f8e05bdfa)

| 번호 | 제목 | 하위 |
|---|---|---|
| 00 | [전체 그림](notion/00_overview.md) |  |
| 01 | [서버와 호스트 OS](notion/01_server.md) | 하위 3 |
| 02 | [가상 머신과 노드](notion/02_nodes.md) | 하위 3 |
| 03 | [쿠버네티스 설치와 파드 망](notion/03_kubernetes.md) |  |
| 04 | [들어오는 문](notion/04_ingress.md) |  |
| 05 | [바깥 공개와 인증서](notion/05_public.md) | 하위 2 |
| 06 | [GitOps](notion/06_gitops.md) |  |
| 07 | [이미지 저장소](notion/07_registry.md) |  |
| 08 | [빌드와 태그 고정](notion/08_build.md) |  |
| 09 | [앱이 올라가는 길](notion/09_deploy.md) | 하위 3 |
| 10 | [데이터베이스 복제와 백업](notion/10_database.md) |  |
| 11 | [GPU와 호스트 서비스](notion/11_gpu.md) |  |
| 12 | [모니터링](notion/12_monitoring.md) | 하위 3 |
| 13 | [공유 저장소](notion/13_storage.md) |  |
| 14 | [운영 규칙과 문서 게시](notion/14_operations.md) |  |
| 15 | [알려진 한계](notion/15_limits.md) |  |

## 문서

| 문서 | 제목 | 요약 |
|---|---|---|
| [00_overview.md](docs/00_overview.md) | 전체 그림 | GPU 호스트 한 대 안의 VM 다섯 대로 세운 kubeadm 클러스터와, 그 위의 앱 둘과 운영 도구를 한 장에 모은다. |
| [01_server.md](docs/01_server.md) | 서버와 호스트 OS | 물리 서버 한 대와 그 호스트 OS, 사무실 망, 원격 접속을 다룬다. |
| [02_nodes.md](docs/02_nodes.md) | 가상 머신과 노드 | 클러스터를 이루는 VM 다섯 대의 정의와 랜카드 둘, 노드 설치, 역할 라벨과 배치를 다룬다. |
| [03_kubernetes.md](docs/03_kubernetes.md) | 쿠버네티스 설치와 파드 망 | kubeadm으로 세운 클러스터의 판과 설치, Calico 파드 망, CoreDNS 설정을 다룬다. |
| [04_ingress.md](docs/04_ingress.md) | 들어오는 문 | 클러스터 안으로 들어오는 문인 ingress-nginx와, 그 앞에 대표 주소 하나를 주는 MetalLB를 다룬다. |
| [05_public.md](docs/05_public.md) | 바깥 공개와 인증서 | Cloudflare 터널로 바깥에 공개하는 길과 경로마다의 Access, cert-manager 인증서와 TLS가 끝나는 곳을 다룬다. |
| [06_gitops.md](docs/06_gitops.md) | GitOps | ArgoCD가 `main`을 읽어 클러스터에 넣는다. |
| [07_registry.md](docs/07_registry.md) | 이미지 저장소 | Harbor를 Helm으로 클러스터 안에 세웠다. |
| [08_build.md](docs/08_build.md) | 빌드와 태그 고정 | Jenkins가 앱 이미지를 굽고 Harbor에 올린 뒤 이 저장소의 `newTag`를 커밋하는 데까지, 그리고 클러스터의 모든 이미지 판을 고정한 자리를 적는다. |
| [09_deploy.md](docs/09_deploy.md) | 앱이 올라가는 길 | petmint와 runshoes 두 앱의 매니페스트, 처음 세우는 순서와 Secret, 버전을 바꾸는 절차를 적는다. |
| [10_database.md](docs/10_database.md) | 데이터베이스 복제와 백업 | 두 앱의 MySQL Primary와 Replica, 복제를 맞추고 확인하는 스크립트, petmint 덤프 백업을 다룬다. |
| [11_gpu.md](docs/11_gpu.md) | GPU와 호스트 서비스 | GPU는 호스트에만 있고 VM에 넘기지 않는다(패스스루 없음). |
| [12_monitoring.md](docs/12_monitoring.md) | 모니터링 | `apps/monitoring/`의 손으로 쓴 매니페스트(차트 없음)를 ArgoCD Application `monitoring`이 자동 Sync한다. |
| [13_storage.md](docs/13_storage.md) | 공유 저장소 | 클러스터의 저장 공간 두 갈래, 기본 StorageClass local-path와 호스트 NFS 정적 PV를 다룬다. |
| [14_operations.md](docs/14_operations.md) | 운영 규칙과 문서 게시 | 저장소를 고치는 규칙(누가, 어디서, 어떤 차례로)과 문서를 노션에 게시하는 구조를 적는다. |

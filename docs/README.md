# ronanlab-infra docs

이 디렉터리가 인프라 문서의 원본이다(2026-11-10부터). 노션 「쿠버네티스 설치」 · 「인프라/서버 구축 포트폴리오 문서」는 사람이 처음 쓴 기록이고,
여기로 옮기면서 **지금 코드 · 클러스터와 맞는 것**만 남긴다 — 노션과 다르면 이 문서와 저장소의 코드가 맞다.

| 문서 | 내용 |
| --- | --- |
| [01_cluster.md](01_cluster.md) | 클러스터 — 호스트 · VM · 네트워크 · 버전 · 노드 추가 절차(`cluster/`의 Vagrantfile · setup-node.sh) |
| [02_availability.md](02_availability.md) | 가용성 — 노드 배치 목표 · 장애 시나리오 · 앱 분산(anti-affinity · PDB) · 노드 정비 절차 · 백업 · 알려진 한계 |
| [TODO.md](TODO.md) | 남은 일 — 한 줄에 하나, 상세는 각 문서 4절 |

아직 옮기지 않은 노션 하위 페이지(02 메트릭·스토리지·Ingress ~ 08 프로젝트 배포)는 [TODO.md](TODO.md)에 있다.
앱별 운영 문서는 그 앱 디렉터리에 있다 — `apps/<앱>/README.md`, `apps/runshoes/runbooks/`.

## 같이 보는 문서(앱 저장소)

- 펫퍼민트 `petmint-rag-chatbot/docs/02_pipeline/14_deployment.md`(배포) · `12_data_storage.md` 1-5절(MySQL 백업 · 복구)
- 런슈즈 `runshoes/docs/06_deployment.md`(배포)

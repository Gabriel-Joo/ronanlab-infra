# TODO — 남은 일

한 줄에 하나. 상세는 각 문서 4절(남은 한계). 끝나면 줄을 지운다.

## 가용성 묶음 2 (사용자 2026-11-10 — 순서 그대로)

- Harbor 이사 w1 · w2 · w3 → w3 (local-path PVC 옮기기 — registry 20Gi · redis · jobservice) → [02_availability.md](02_availability.md) 1-2절
- ArgoCD 이사 m-k8s · 여러 워커 → w3 → 02 1-1절
- MySQL Replica 구성(petmint · runshoes, w2) + 수동 승격 런북 → 02 4절
- 배치 고정 — 앱 w1 · w2, Harbor/Jenkins/ArgoCD w3, 플랫폼 w4(nodeAffinity · taint) → 02 1-1절
- 모니터링(Prometheus · Grafana, `apps/monitoring`) + Loki 설치 → 02 1-1절

## 그 밖

- ingress-nginx replicas 2 + PDB — 지금 단일 replica, 재시작 때 12초 끊김 원인 확인 → 02 4절
- runshoes ShedLock 들어오면 `ACTIVITY_CLEANUP_CRON` env 빼기(앱 리포 일 먼저) → 02 4절
- 백업을 다른 물리 디스크 · 바깥으로 한 벌 더(지금 운영 DB와 같은 NVMe) → 02 4절
- runshoes MySQL 정기 백업(지금 스키마 배포 전 수동 덤프만) → 02 1-4절
- 노션 「쿠버네티스 설치」 하위 02~08 페이지를 docs로 옮기기(02 메트릭·스토리지·Ingress, 03 Cloudflare Tunnel, 04 ArgoCD, 05 Harbor, 06 Jenkins, 07 모니터링, 08 프로젝트 배포) → [README.md](README.md)

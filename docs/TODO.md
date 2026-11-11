# TODO — 남은 일

한 줄에 하나. 상세는 각 문서 4절(남은 한계). 끝나면 줄을 지운다.

## 가용성 — 묶음 2 뒤(2026-11-10)

- 옛 Harbor PVC 다섯 지우기 — 새 쪽(w3)이 며칠 정상으로 돈 뒤, 사람이 판단(`harbor-registry` w2 16GB 등) → [02_availability.md](02_availability.md) 1-2절
- GPU exporter 띄우기 — 호스트에서 `bash scripts/host-gpu-exporter.sh`(docker 그룹) → `apps/monitoring/README.md`
- MySQL 승격을 앱 트래픽까지 옮겨 한 번 해 보기(점검 시간에) — 앱 재시작 · 앱 확인 시간을 다시 잰다 → [runbooks/mysql-replica.md](runbooks/mysql-replica.md)
- Jenkins 빌드 Pod 에 nodeSelector(infra) — 앱 저장소 Jenkinsfile 일 → 02 4절
- petmint 앱 계측 — 거절 여부 · 검색 시간을 턴 로그에(또는 `/metrics`) → 대시보드 빈 패널 둘 → 02 4절
- Milvus 지표 — 9091 게시 주소를 사설망으로(호스트 docker) → `apps/monitoring/README.md`
- 알림(Alertmanager) → 02 4절
- ingress-nginx 재시작 끊김 원인(1개일 때 12초, 2개일 때 1초) → 02 4절

## 그 밖

- runshoes ShedLock 들어오면 `ACTIVITY_CLEANUP_CRON` env 빼기(앱 리포 일 먼저) → 02 4절
- 백업을 다른 물리 디스크 · 바깥으로 한 벌 더(지금 운영 DB와 같은 NVMe) → 02 4절
- runshoes MySQL 정기 백업(지금 스키마 배포 전 수동 덤프만) → 02 1-4절
- 노션 「쿠버네티스 설치」 하위 페이지를 docs로 옮기기(묶음 3) → [README.md](README.md)

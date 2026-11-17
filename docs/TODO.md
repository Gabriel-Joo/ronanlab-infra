# TODO — 남은 일

한 줄에 하나. 「08」은 옛 문서 [history/build_log/08_scale_out.md](history/build_log/08_scale_out.md)다. 끝나면 줄을 지운다.

## 가용성 — 묶음 2 뒤(2026-11-10)

- 옛 Harbor PVC 다섯 지우기 — 새 쪽(w3)이 며칠 정상으로 돈 뒤, 사람이 판단(`harbor-registry` w2 16GB 등) → 08 1-2절
- MySQL 승격을 앱 트래픽까지 옮겨 한 번 해 보기(점검 시간에) — 앱 재시작 · 앱 확인 시간을 다시 잰다 → [runbooks/mysql-replica.md](runbooks/mysql-replica.md)
- Jenkins 빌드 Pod 에 nodeSelector(infra) — 앱 저장소 Jenkinsfile 일 → 08 4절
- 알림(Alertmanager) → 08 4절
- ingress-nginx 재시작 끊김 원인(1개일 때 12초, 2개일 때 1초) → 08 4절

## 그 밖

- 백업을 다른 물리 디스크 · 바깥으로 한 벌 더(지금 운영 DB와 같은 NVMe) → 08 4절
- runshoes MySQL 정기 백업(지금 스키마 배포 전 수동 덤프만) → 08 1-4절

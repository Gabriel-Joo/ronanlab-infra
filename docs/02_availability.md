## 02. 가용성 — 노드 배치 · 장애 시나리오 · 정비 절차

#### 0. 한 줄 요약

목표는 "노드 하나가 죽어도 뭔가는 돈다"이다. 2026-11-10 묶음 1에서 앱 두 개를 노드 둘에 나누고(anti-affinity · PDB), Harbor DB 백업을 더하고,
워커를 4대 · 8GB로 늘렸다. 노드마다 역할을 고정하는 배치와 MySQL Replica는 묶음 2다 — 지금은 local-path PVC가 노드 여기저기에 묶여 있어
어느 워커를 내려도 무언가가 멈춘다(1-2절 표).

#### 1. 최종 설계

##### 1-1. 목표 배치 (사용자 2026-11-10)

```
m-k8s   컨트롤 플레인만                                    4096
w1      MySQL Primary ×2 + petmint ×1 + runshoes ×1        8192
w2      MySQL Replica ×2 + petmint ×1 + runshoes ×1        8192
w3      Harbor + Jenkins + ArgoCD                          8192
w4      플랫폼 (Prometheus · Grafana · Loki)               8192
```

| 죽는 노드 | 목표에서 | 
| --- | --- |
| w3 | 서비스는 돈다. 배포 · 빌드만 멈춘다 |
| w4 | 모니터링만 멈춘다 |
| w1 | 앱은 w2의 Pod가 받는다. MySQL은 Replica를 수동 승격 |

메모리 · 노드 수(묶음 1)는 끝났다. 배치 고정 · Harbor/ArgoCD 이사 · Replica · 모니터링은 묶음 2([TODO.md](TODO.md)).

##### 1-2. 지금 (2026-11-10 묶음 1 뒤) — 노드에 묶인 것

local-path PVC는 처음 뜬 노드의 디스크에 생겨 그 노드에 묶인다(Pod를 옮길 수 없다). 그 밖의 것은 스케줄러가 아무 워커에나 둔다.

| 노드 | 묶인 것(local-path PVC) | 그 노드가 죽으면 멈추는 것 |
| --- | --- | --- |
| w1 | petmint `mysql-0` · `runshoes-mysql-0` · `harbor-redis-0` · `harbor-jobservice` | 두 앱의 DB 기능(runshoes는 Ready가 빠져 503), Harbor 로그인 · push |
| w2 | `harbor-registry`(20Gi 레이어) · `harbor-trivy-0` | 이미지 pull · push(새 Pod가 이미지를 못 받는다) |
| w3 | `harbor-database-0` · `jenkins-0` | Harbor 전체, 빌드 |
| w4 | 없음 | 그 위의 Pod가 다른 노드로 옮겨질 때까지 잠깐 |

- 앱 Pod(petmint 2 · runshoes 2) · cloudflared 2는 노드 둘에 나뉘어 한 노드가 죽어도 응답한다
- ingress-nginx · CoreDNS(2) · ArgoCD · cert-manager 등 단일 replica 무상태 Deployment는 노드가 죽으면 다른 노드에서 다시 뜬다(그동안 끊긴다 —
  NotReady 판정 · 축출까지 기본 약 5분)

##### 1-3. 앱 분산 — anti-affinity · PDB

| 앱 | replicas | 분산 | PDB | 롤링 |
| --- | --- | --- | --- | --- |
| petmint (`apps/petmint/app/`) | 2 | required anti-affinity(hostname) | minAvailable 1 | maxSurge 1 · maxUnavailable 0 (수동 Sync) |
| runshoes (`apps/runshoes/app/`, 2026-11-10) | 2 | 같음 | minAvailable 1 (petmint와 맞춤) | 같음 (자동 Sync) |

- required라 같은 노드에 둘을 두지 않는다. 롤링 중에는 2+1개라 **스케줄 가능한 워커가 3대** 필요하다 — 워커가 4대가 돼서 한 대를 내린 동안에도
  롤링이 된다(2026-11-10 w1을 cordon한 채 runshoes 새 태그가 w2 · w3로 롤링됨). 다만 Harbor가 멈춘 동안이면 새 Pod가 이미지를 못 받아 멈춘다(옛 Pod가 계속 받는다)
- PDB는 drain(자발적 축출)만 막는다. 노드가 갑자기 죽는 것은 막지 못한다 — 그때는 남은 Pod 하나가 받는다
- runshoes는 replicas 2와 함께 `ActivityCleanup`(@Scheduled, Pod마다 돈다)을 껐다 — env `ACTIVITY_CLEANUP_CRON: "-"`.
  ShedLock(앱 리포)이 들어오면 그 env를 뺀다(4절 한계)

##### 1-4. 백업

| 대상 | 방식 | 어디로 | 복구 시험 |
| --- | --- | --- | --- |
| petmint MySQL | CronJob 03:30 KST mysqldump `--single-transaction` (`apps/petmint/backup/`) | 호스트 `~/backup/mysql/petmint` (NFS) | 앱 리포 docs 12번 1-5절 |
| Harbor DB(PostgreSQL `registry`) | CronJob 03:45 KST `pg_dump -Fc` (`apps/harbor-backup/`, 2026-11-10) | 호스트 `~/backup/harbor` (NFS, fsid 105) | 2026-11-10 시험 DB에 복구 — 49개 테이블 행 수 운영과 같음(`apps/harbor-backup/README.md`) |
| runshoes MySQL | 정기 백업 없음 — 스키마 배포 전 수동 덤프(`apps/runshoes/runbooks/`) | 호스트 `~/k8s-cluster/backup/` | 런북마다 |

방식은 같다: CronJob → 호스트 NFS 쓰기 PV/PVC, `.part`로 쓰고 검증 뒤 이름 바꿈 + sha256, 보존 30일 · 최신 7개. 호스트 export는 sudo 스크립트로 한 번.

##### 1-5. 노드 정비 절차 (한 노드씩 — 2026-11-10 w2 → w3 → w1로 확인)

```bash
free -g                                              # 호스트 여유
kubectl cordon <노드>
# 1. 그 노드의 단일 replica 무상태 Deployment 를 먼저 옮긴다 — rollout restart 는 새 Pod 가 Ready 된 뒤 옛 Pod 를 내린다(끊김 없음)
#    (PVC 가 있는 것 — harbor-registry · jobservice 등 — 은 옮길 수 없어 뺀다)
kubectl -n <ns> rollout restart deploy <이름> ... && kubectl -n <ns> rollout status deploy <이름>
# 2. 앱 Pod 를 Harbor 가 살아 있을 때 먼저 내보낸다 — 새 노드가 이미지를 받아야 한다(어느 워커를 내려도 Harbor 일부가 멈춘다, 1-2절)
kubectl drain <노드> --ignore-daemonsets --delete-emptydir-data --pod-selector='app.kubernetes.io/name in (petmint-app,runshoes)'
kubectl drain <노드> --ignore-daemonsets --delete-emptydir-data --pod-selector='app=cloudflared'
# 3. Jenkins 빌드 · Jenkins 태그 커밋의 롤아웃이 돌고 있으면 끝날 때까지 기다린다(빌드 Pod: runshoes-app-* · petmint-app-*)
# 4. 나머지 drain(PVC 에 묶인 Pod 는 노드가 돌아올 때까지 Pending) → halt → (메모리 변경, 01_cluster.md 1-5절) → up
kubectl drain <노드> --ignore-daemonsets --delete-emptydir-data
cd ~/k8s-cluster && vagrant halt <노드> && vagrant up <노드>
# 5. NotReady 를 거쳐 다시 Ready 인 것을 보고 uncordon(꺼진 직후에는 Ready 가 아직 남아 있다 — 2026-11-10 w2 에서 낡은 Ready 를 보고 uncordon 함)
kubectl wait --for=condition=Ready node/<노드> && kubectl uncordon <노드>
```

- **펫퍼민트 Sync를 하지 않는다**(사용자) — 정비 중에는 워커가 하나 모자란다
- drain은 끝난 Job의 Pod(Completed)도 지운다 — Job 객체는 남지만 그 Pod 로그는 사라진다
- 바깥에서 1초마다 응답을 남겨 두면 끊긴 구간을 셀 수 있다(5절 기록이 그것)

#### 2. 왜 이렇게 했나

- **증설 전에 앱부터 둘로**: 노드를 하나씩 내리는데 replicas 1이면 그 노드를 내릴 때 서비스가 끊긴다. runshoes를 먼저 2로 하고 PDB를 petmint와 맞췄다
- **ActivityCleanup을 끈 것(사용자 결정)**: 두 Pod의 같은 시각 DELETE가 같은 행을 두고 잠금을 다툴 수 있다. 코드 주석은 "멱등"이라고 하지만 운영 중 경합은 피하고,
  분산 잠금(ShedLock)은 앱 리포 일이라 그 전까지 끈다
- **Harbor 백업을 ArgoCD로**: Harbor 자체는 `platform/`(Helm, ArgoCD 밖)이지만 백업 CronJob은 git으로 관리되는 쪽이 낫다 — MySQL 백업과 같은 자리 · 같은 방식
- **워커 4대**: 목표 배치의 w4(플랫폼) 자리이자, 한 대를 정비하는 동안에도 anti-affinity 롤링(2+1)이 되는 최소 수
- **수동 승격**: MySQL 자동 장애 전환에는 Operator(예: Group Replication · Orchestrator)가 필요한데 자원 제약으로 Replica + 수동 승격을 택했다(묶음 2)

#### 3. 시도했던 것들

- 첫 정비 순서는 그냥 `kubectl drain`이었다 — 앱 Pod가 옮겨가며 Harbor에서 이미지를 받아야 하는데, 같은 drain이 Harbor 구성 요소(PVC가 그 노드)를 같이 멈추면
  새 Pod가 ImagePullBackOff가 될 수 있다. 앱 Pod를 먼저 내보내는 순서로 바꿨다(1-5절 2번)
- w1 정비 중 Jenkins가 runshoes를 빌드하고 있었다 — w1(Harbor redis)을 내리면 push가 실패할 수 있어 빌드 · 롤아웃이 끝난 뒤 내렸다

#### 4. 남은 한계

- **MySQL 자동 장애 전환이 없다.** 지금은 Replica도 없어 w1이 죽으면 두 앱의 DB가 w1이 돌아올 때까지 멈춘다. Operator가 필요한데 자원 제약으로 Replica + 수동 승격을 택했다(묶음 2)
- **백업이 운영 DB와 같은 물리 디스크에 있다.** 호스트 NFS(`~/backup/`)와 VM 디스크(local-path)가 같은 서버 · 같은 NVMe다 — 디스크가 죽으면 둘 다 잃는다
- **VM이 모두 같은 물리 서버에 있다.** 서버 자체(전원 · 메인보드 · 디스크)가 죽으면 전부 멈춘다. 노드 분산은 VM · 커널 · kubelet 장애만 막는다
- **런슈즈 activity_logs 정리가 꺼져 있다(2026-11-10부터).** ShedLock이 들어올 때까지 activity_logs가 지워지지 않고 쌓인다 — 앱이 정리하며 남기던 경고(행 수가 경고선을 넘음)도 안 나온다
- **Harbor 이미지 레이어는 백업하지 않는다.** DB만 있다 — 레이어가 사라지면 앱 리포 커밋에서 다시 빌드한다
- **단일 replica 무상태 컴포넌트**(ingress-nginx · ArgoCD · cert-manager · metrics-server)는 노드가 갑자기 죽으면 다른 노드에서 다시 뜰 때까지 멈춘다. 특히 ingress-nginx는 모든 앱의 입구다
- **ingress-nginx 재시작 때 12초 끊김(원인 미확인)**: 2026-11-10 w1 정비에서 ingress-nginx · MetalLB 컨트롤러 등 8개를 같은 순간 `rollout restart`했을 때
  19:27:20~31 모든 호스트가 응답하지 않았다. Service는 `externalTrafficPolicy: Cluster`라 VIP가 컨트롤러 노드에 묶이지는 않는다. 다음에는 ingress-nginx만 따로 재시작하며 본다

#### 5. 검증 항목 · 기록

##### 5-1. 2026-11-10 묶음 1 실행 기록

| 단계 | 커밋 · 변경 | 확인 |
| --- | --- | --- |
| 1 runshoes replicas 2 | `fdc9600` deployment(replicas 2 · anti-affinity · env) · `pdb.yaml` | Pod w1 · w3, PDB ALLOWED 1, 두 Pod env `-`, `@Scheduled` 스레드(`scheduling-*`) 0개, 응답 200×6, ArgoCD Synced/Healthy |
| 2 petmint 확인 | 변경 없음(Sync 안 함) | 매니페스트 · 클러스터 모두 replicas 2 · required anti-affinity · PDB minAvailable 1 |
| 3 Harbor DB 백업 | `adbe654` · `e2c9b36`, 호스트 export(sudo) | 첫 덤프 500,480B · 테이블 데이터 49 · sha256 OK, 시험 DB 복구 49개 테이블 행 수 같음 |
| 4 w4 | Vagrantfile(+ DNS 프로비저너), setup-node.sh(버전 고정), kubeadm join | Ready, w4 고정 시험 Pod에서 Harbor pull · DNS · MySQL TCP · Service 200 · Ollama 200 · NFS |
| 5 w1~w3 8GB | Vagrantfile, virsh 메모리, w2 → w3 → w1 | 노드마다 Ready · 용량 8128536Ki · 묶인 Pod 복귀 · 응답(아래) |

호스트 메모리(available): 시작 35GB → w4 뒤 33GB → w2 뒤 32GB → w3 뒤 29GB → w1 뒤 25GB.

##### 5-2. 정비 중 응답 (호스트 → VIP, 1초마다)

| 구간 | petmint `/` | runshoes `/api/shoes` | Harbor ping | ArgoCD | Jenkins |
| --- | --- | --- | --- | --- | --- |
| w2 (19:07~19:20) | 실패 0 | 0 | 1 (core 재시작 순간) | 0 | 0 |
| w3 (19:20~19:26) | 0 | 0 | 0 | 1 | 235 (약 5분, PVC가 w3 — 예정) |
| w1 (19:26~19:37) | 11 (19:27:20~31) | 90 | 92 | 11 | 11 |

w1의 runshoes 78건 · Harbor 81건은 MySQL · redis가 내려간 19:35:15~19:36:59(약 1분 40초, 예정 — 사용자가 받아들임), 나머지(runshoes 12 · 그 밖 11건씩)는 위 4절의 12초 끊김이다.
petmint `/`는 정적 응답이라 MySQL이 멈춘 동안에도 200이었다(DB를 쓰는 API는 실패).

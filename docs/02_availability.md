## 02. 가용성 — 노드 배치 · 장애 시나리오 · 정비 절차

#### 0. 한 줄 요약

목표는 "노드 하나가 죽어도 뭔가는 돈다"이다. 2026-11-10 하루에 두 묶음으로 했다.
- 묶음 1: 앱 두 개를 노드 둘에 나누고(anti-affinity · PDB), Harbor DB 백업을 더하고, 워커를 4대 · 8GB로 늘렸다
- 묶음 2: 노드마다 역할을 고정했다(app w1 · w2 / infra w3 / platform w4), Harbor를 w3 한 곳으로 옮기고, MySQL Replica(w2)와 수동 승격 런북을 만들고, 모니터링 · Loki를 w4에 올렸다

#### 1. 최종 설계

##### 1-1. 배치 (사용자 2026-11-10 목표 — 묶음 2로 맞췄다)

```
m-k8s   컨트롤 플레인만(control-plane taint)                          4096
w1      app       MySQL Primary ×2 + petmint ×1 + runshoes ×1         8192
w2      app       MySQL Replica ×2 + petmint ×1 + runshoes ×1         8192
w3      infra     Harbor + Jenkins + ArgoCD                           8192
w4      platform  Prometheus · Grafana · Loki                         8192
```

노드 라벨 `node.ronanlab.dev/role`(`cluster/label-nodes.sh` — 노드를 다시 만들면 다시 돌린다). 매니페스트는 이 라벨을 nodeSelector로 본다.

| 죽는 노드 | 멈추는 것 | 도는 것 |
| --- | --- | --- |
| w1 | MySQL Primary 둘 → 사람이 Replica 승격([runbooks/mysql-replica.md](runbooks/mysql-replica.md)) | 앱은 w2의 Pod가 받는다(DB 쓰기는 승격 전까지 실패) |
| w2 | Replica(복제만 멈춤) | 앱은 w1의 Pod가 받는다 |
| w3 | 배포 · 빌드(Harbor · Jenkins · ArgoCD) | 서비스 전부 — 떠 있는 Pod는 이미지가 노드에 있다 |
| w4 | 모니터링 · 로그 | 서비스 · 배포 전부 |

정해 두지 않은 것: ingress-nginx(2개, 분산 선호) · cloudflared(2개) · CoreDNS · cert-manager · MetalLB 컨트롤러 · local-path-provisioner는 아무 워커에나 뜬다.
Jenkins 빌드 Pod(BuildKit)는 앱 저장소 Jenkinsfile이 정해 아무 워커에나 뜬다(4절).

##### 1-2. 노드에 묶인 것(local-path PVC) — 묶음 2 뒤

| 노드 | 묶인 것 |
| --- | --- |
| w1 | petmint `mysql-0` · `runshoes-mysql-0`(Primary) |
| w2 | `mysql-replica-0` · `runshoes-mysql-replica-0` |
| w3 | Harbor 다섯(`harbor-*-w3` — `platform/harbor/pvc-w3.yaml`) · `jenkins-0` |
| w4 | `prometheus-0` · `loki-0` |

**옛 Harbor PVC 다섯은 지우지 않고 남겨 두었다**(registry · trivy w2, redis · jobservice w1, database w3 — 원본 보존, 사용자). Harbor PV는 전부 reclaimPolicy Retain.
새 쪽이 며칠 정상으로 돈 뒤 사람이 지운다(TODO).

##### 1-3. 앱 분산 — anti-affinity · PDB · 롤링

| 앱 | replicas | 분산 | PDB | 롤링 |
| --- | --- | --- | --- | --- |
| petmint | 2 | app 노드(w1 · w2) + required anti-affinity | minAvailable 1 | maxSurge 0 · maxUnavailable 1 (자동 Sync, 2026-11-11~) |
| runshoes | 2 | 같음 | minAvailable 1 | 같음 (자동 Sync) |

- app 노드가 둘뿐이라 새 Pod를 먼저 띄우는 롤링(2+1)은 세 번째 Pod가 갈 곳이 없다 → **옛 Pod 하나를 먼저 내리고 새 Pod**. 롤링 동안 잠깐 Pod가 하나다(처리 용량 절반, 서비스는 이어진다 — 2026-11-10 1초 탐침 실패 0)
- app 노드 하나가 죽으면 두 번째 Pod는 그 노드가 돌아올 때까지 Pending이고, 그동안 롤링은 멈춘다(남은 하나가 받는다)
- runshoes는 replicas 2와 함께 `ActivityCleanup`을 꺼 두었다(env `ACTIVITY_CLEANUP_CRON: "-"`, ShedLock 전까지)

##### 1-4. 데이터 — Replica · 백업

| 대상 | 무엇 | 어디로 |
| --- | --- | --- |
| petmint · runshoes MySQL | Replica(w2), binlog 파일 · 위치 복제, 자동 전환 없음 — [runbooks/mysql-replica.md](runbooks/mysql-replica.md) | Replica 디스크(w2) |
| petmint MySQL | CronJob 03:30 KST mysqldump(`apps/petmint/backup/`) | 호스트 `~/backup/mysql/petmint`(NFS) |
| Harbor DB | CronJob 03:45 KST `pg_dump -Fc`(`apps/harbor-backup/`) | 호스트 `~/backup/harbor`(NFS) |
| runshoes MySQL | 정기 덤프 없음 — 스키마 배포 전 수동 덤프(`apps/runshoes/runbooks/`). Replica가 생겼다 | — |

Replica는 백업이 아니다 — Primary에서 지운 것은 Replica에서도 지워진다. 덤프는 그대로 필요하다.

##### 1-5. 노드 정비 절차 (한 노드씩)

```bash
free -g                                              # 호스트 여유
kubectl cordon <노드>
# 1. 그 노드의 단일 replica 무상태 Deployment 를 먼저 옮긴다(rollout restart — 새 Pod 가 Ready 된 뒤 옛 Pod 를 내린다)
#    배치를 고정한 것은 같은 역할의 다른 노드가 없으면 옮겨지지 않는다(infra · platform 은 노드가 하나) — 그 노드 정비 동안 멈춘다
# 2. 앱 노드(w1 · w2)면 앱 Pod 를 먼저 — 남은 app 노드에 하나가 이미 있어 새 Pod 는 Pending(남은 하나가 받는다)
kubectl drain <노드> --ignore-daemonsets --delete-emptydir-data --pod-selector='app.kubernetes.io/name in (petmint-app,runshoes)'
# 3. Jenkins 빌드 · 태그 커밋 롤아웃이 돌고 있으면 끝날 때까지 기다린다(w3 정비 때 특히)
# 4. 나머지 drain(PVC 에 묶인 Pod 는 돌아올 때까지 Pending) → halt → (메모리 변경, 01_cluster.md 1-5절) → up
kubectl drain <노드> --ignore-daemonsets --delete-emptydir-data
cd ~/k8s-cluster && vagrant halt <노드> && vagrant up <노드>
# 5. NotReady 를 거쳐 다시 Ready 인 것을 보고 uncordon(꺼진 직후에는 Ready 가 아직 남아 있다)
kubectl wait --for=condition=Ready node/<노드> && kubectl uncordon <노드>
```

| 정비하는 노드 | 그동안 멈추는 것 |
| --- | --- |
| w1 | MySQL Primary 둘(쓰기 · runshoes Ready) — 짧으면 기다리고, 길면 런북 3절로 승격 |
| w2 | Replica(돌아오면 따라잡는다), 앱 용량 절반 |
| w3 | Harbor · Jenkins · ArgoCD(배포 · 빌드) |
| w4 | 모니터링 · 로그(그동안의 지표 · 로그는 빈다) |

- 펫퍼민트 Sync는 정비 중에는 하지 않는다(사용자)
- drain은 끝난 Job의 Pod(Completed)도 지운다 — 그 Pod 로그는 사라진다(Loki에는 남는다)

##### 1-6. 모니터링 (w4)

`apps/monitoring/README.md` — Prometheus 15일 · Loki 7일(서버 로그만, 대화 기록 없음) · Grafana 대시보드 `petmint — 운영`.
앱에 `/metrics`가 없어 HTTP 지표는 ingress-nginx에서, 질문 · 답 지표는 petmint 턴 로그(Replica, 컬럼 단위 읽기 계정)에서 얻는다.

#### 2. 왜 이렇게 했나

- **증설 전에 앱부터 둘로**(묶음 1): 노드를 하나씩 내리는데 replicas 1이면 그 노드를 내릴 때 서비스가 끊긴다
- **역할별 노드**(묶음 2): 노드가 죽었을 때 무엇이 멈추는지를 노드 이름으로 말할 수 있게. 전에는 local-path PVC가 노드 여기저기에 생겨 어느 워커를 내려도 Harbor 일부가 멈췄다
- **Harbor 이사는 새 PVC + 복사**: local-path는 PVC를 다른 노드로 옮길 수 없다. 원본을 지우지 않는다는 조건이라 새 이름의 PVC를 w3에 만들고 tar로 복사한 뒤 `existingClaim`으로 바꿨다
- **MySQL은 수동 승격**: 자동 전환에는 Operator가 필요한데 자원 제약으로 Replica + 런북을 택했다. GTID는 Primary 재시작이 필요해 binlog 파일 · 위치로
- **Grafana가 DB를 직접 읽는다**: 앱 코드를 고치지 않고 질문 · 답 지표를 얻는 길. Replica를 읽어 운영에 부하를 주지 않고, 컬럼 단위 권한으로 본문을 읽을 수 없게 했다
- **ingress-nginx 2개**: 메트릭을 켜려면 재시작이 필요했고, 1개일 때 재시작이 12초 끊김을 냈다(묶음 1) — 먼저 늘린 뒤 바꿨다

#### 3. 시도했던 것들

- 첫 정비 순서는 그냥 `kubectl drain`이었다 — 앱 Pod가 옮겨가며 Harbor에서 이미지를 받아야 하는데 같은 drain이 Harbor를 멈추면 새 Pod가 ImagePullBackOff가 될 수 있다. 앱 Pod를 먼저 내보내는 순서로 바꿨다(묶음 1)
- Harbor 차트에서 registry · jobservice에 `existingClaim`을 주면 차트가 옛 PVC를 더 그리지 않아 helm이 지울 수 있다 — 차트가 `helm.sh/resource-policy: keep`을 달아 둔 것을 확인하고, PV를 Retain으로 바꾼 뒤 올렸다
- Replica 시드 스크립트: `tee >(grep -m1)`로 binlog 위치를 뽑다가 grep이 먼저 끝나 tee가 SIGPIPE로 끊겼다 → awk 한 프로세스. MySQL 8.0.46 mysqldump는 `--source-data`여도 `CHANGE MASTER TO` 문법으로 적는다

#### 4. 남은 한계

- **MySQL 자동 장애 전환이 없다.** Replica는 있지만 승격은 사람이 한다 — 기계 쪽 시간은 약 2분(승격 1초 안 + 앱 재시작 1~1.5분, 런북 시험 기록), 나머지는 알아채고 판단하는 시간이다. 앱 트래픽까지 옮기는 진짜 전환은 아직 해 보지 않았다
- **app 노드가 둘이다.** 롤링 때 잠깐 Pod 하나, app 노드 하나가 죽으면 Pod 하나로 버틴다
- **infra · platform 노드는 하나씩이다.** w3이 죽으면 배포 · 빌드가, w4가 죽으면 모니터링이 그 노드가 돌아올 때까지 멈춘다(목표대로)
- **백업이 운영 DB와 같은 물리 디스크에 있다.** 호스트 NFS(`~/backup/`)와 VM 디스크가 같은 서버 · 같은 NVMe다
- **VM이 모두 같은 물리 서버에 있다.** 서버 자체가 죽으면 전부 멈춘다. 노드 분산은 VM · kubelet 장애만 막는다
- **런슈즈 activity_logs 정리가 꺼져 있다(2026-11-10부터).** ShedLock 전까지 activity_logs가 쌓인다
- **Harbor 이미지 레이어는 백업하지 않는다.** DB만 있다 — 레이어가 사라지면 앱 리포 커밋에서 다시 빌드한다
- **옛 Harbor PVC 다섯이 디스크를 쓰고 있다**(registry 16GB w2 등) — 지울 때까지
- **Jenkins 빌드 Pod는 배치가 고정되지 않았다.** Jenkinsfile(앱 저장소)의 Pod 템플릿에 nodeSelector를 넣어야 한다 — 빌드(상한 3Gi)가 app 노드에 뜨면 앱과 메모리를 나눈다
- **ingress-nginx 재시작 때 짧은 끊김.** 1개일 때 12초(묶음 1, 원인 미확인), 2개로 늘린 뒤 롤링에서 1초 한 번(2026-11-10 21:13:29) — 0은 아니다
- **모니터링**: GPU exporter를 아직 띄우지 않았다(호스트 컨테이너, 사람이 띄운다) · Milvus 지표는 2026-11-11 9091을 사설망에도 게시해 up(디버그 경로도 함께 열림 — 앱 리포 docs 15번 4절) · 거절률 · 검색 지연은 2026-11-11 턴 로그 칸(refused · search_ms, 앱 0009)으로 붙였다 · Grafana · Prometheus 바깥 주소는 2026-11-11 클러스터 쪽(Ingress · 인증서 · 터널)까지 — Access · DNS는 사람이 대시보드에서(Prometheus는 자체 로그인이 없어 Access가 먼저) · 알림(Alertmanager) 없음 · Prometheus · Loki 한 대씩

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

##### 5-2. 묶음 1 정비 중 응답 (호스트 → VIP, 1초마다)

| 구간 | petmint `/` | runshoes `/api/shoes` | Harbor ping | ArgoCD | Jenkins |
| --- | --- | --- | --- | --- | --- |
| w2 (19:07~19:20) | 실패 0 | 0 | 1 (core 재시작 순간) | 0 | 0 |
| w3 (19:20~19:26) | 0 | 0 | 0 | 1 | 235 (약 5분, PVC가 w3 — 예정) |
| w1 (19:26~19:37) | 11 (19:27:20~31) | 90 | 92 | 11 | 11 |

w1의 runshoes 78건 · Harbor 81건은 MySQL · redis가 내려간 19:35:15~19:36:59(약 1분 40초, 예정 — 사용자가 받아들임), 나머지(runshoes 12 · 그 밖 11건씩)는 위 4절의 12초 끊김이다.
petmint `/`는 정적 응답이라 MySQL이 멈춘 동안에도 200이었다(DB를 쓰는 API는 실패).

##### 5-3. 2026-11-10 묶음 2 실행 기록

| 단계 | 커밋 | 확인 |
| --- | --- | --- |
| 1 Harbor → w3 | `d5bf708` | 이사 직전 DB 백업, Jenkins 빌드 없음 확인 → Harbor 정지 → 노드 간 tar 73초(registry 3,408파일 16.9GB) → 파일 이름 · 크기 · 권한 · 소유자 목록 md5 원본과 같음 → helm upgrade. Harbor 멈춘 시간 약 4분. DB 49개 테이블 행 수 이사 전과 같음, w4에서 `imagePullPolicy: Always` pull, 시험 push → 조회 → 삭제(404). 옛 PVC 다섯 그대로, w3 루트 62G → 92G |
| 2 ArgoCD → w3 | `61dbc5c` | PVC 없음. 7개 모두 w3, Application 5개 Synced/Healthy, 커밋 뒤 웹훅으로 12초 만에 새 커밋을 봄 |
| 3 MySQL Replica | `72d0716` · `25d94d0` | 두 Replica w2, 테이블 행 수 · 계정 Primary와 같음, 쓰기 전달 확인. 승격 시험(runshoes): SQL 0.2초 · Service 전환 0.1초 · 다시 만들기 10초 |
| 4 배치 고정 | `684774a` | 앱 w1 · w2(롤링 실패 0), Jenkins w3(재기동 66초). 앱 재시작 runshoes 82초 · petmint 23초 |
| 5 모니터링 | `b15b7ff`(ingress) · `eb13e8f` | 전부 w4, 수집 대상 up(milvus · nvidia-gpu 제외 — 4절), Loki 12개 네임스페이스 · 챗봇 질문 줄 0건, Grafana 데이터소스 셋 OK, 읽기 계정이 질문 · 코멘트 컬럼에서 ERROR 1143 |

Harbor · ArgoCD · Jenkins를 옮기는 동안 앱 응답은 끊기지 않았다(앱 Pod는 이미지를 노드에 갖고 있다). 배치 고정 롤링 · 앱 재시작 동안 1초 탐침 실패 0,
ingress-nginx를 2개로 늘린 뒤 메트릭을 켜는 롤링에서 1초 한 번 다섯 호스트 모두 응답 없음.

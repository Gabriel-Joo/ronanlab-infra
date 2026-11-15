<!--
다루는 곳: apps/petmint/mysql/, apps/runshoes/mysql/, apps/petmint/backup/, scripts/mysql-replica-seed.sh, scripts/mysql-replica-check.sh
읽은 커밋: e8e24ea
-->
# 데이터베이스 복제와 백업

두 앱의 MySQL Primary와 Replica, 복제를 맞추고 확인하는 스크립트, petmint 덤프 백업을 다룬다. 승격과 되돌리기의 전체 절차는 런북 `docs/runbooks/mysql-replica.md`가 원본이다. 노드 배치의 까닭과 지난 시험 기록은 `docs/history/build_log/08_scale_out.md`에 있다. [docs:runbooks/mysql-replica.md] [docs:history/build_log/08_scale_out.md]

## 지금 구성

| | petmint | runshoes |
| --- | --- | --- |
| 네임스페이스 | `petmint` | `runshoes` |
| Primary | StatefulSet `mysql`, Pod `mysql-0` | StatefulSet `runshoes-mysql`, Pod `runshoes-mysql-0` |
| Replica | StatefulSet `mysql-replica`, Pod `mysql-replica-0` | StatefulSet `runshoes-mysql-replica`, Pod `runshoes-mysql-replica-0` |
| 앱이 붙는 Service | `mysql` (headless, Primary만) | `runshoes-mysql` (headless, Primary만) |
| Replica Service | `mysql-replica` (headless) | `runshoes-mysql-replica` (headless) |
| 데이터베이스 | `petmint`, `insurance_core` | `runshoes` |
| PVC | local-path 10Gi씩 | local-path 2Gi씩 |
| 정기 백업 | CronJob `mysql-backup` | 없음 |

- 이미지는 네 StatefulSet 모두 `mysql:8.0.46`이다. [code:apps/petmint/mysql/statefulset.yaml:31] [code:apps/petmint/mysql/replica.yaml:61] [code:apps/runshoes/mysql/statefulset.yaml:41] [code:apps/runshoes/mysql/replica.yaml:55]
- petmint는 인스턴스 하나에 데이터베이스 둘이다. 데이터베이스와 계정은 초기화 Job(`db.bootstrap`)이 만든다. [code:apps/petmint/mysql/statefulset.yaml:1-2]
- runshoes는 이미지가 빈 데이터 디렉터리에서 처음 뜰 때 데이터베이스 `runshoes`와 계정 `runshoes`를 만든다. 초기화 Job은 없다. [code:apps/runshoes/mysql/statefulset.yaml:2] [code:apps/runshoes/mysql/statefulset.yaml:51-56]
- runshoes가 MySQL을 따로 둔 것은 Secret이 네임스페이스 안에서만 보여 petmint 초기화 Job이 runshoes 계정을 만들 수 없어서다. [docs:history/build_log/07_project_deploy.md:160]
- Primary는 w1, Replica는 w2에 있다. [docs:runbooks/mysql-replica.md:3] [code:cluster/label-nodes.sh:6]
- 복제는 binlog 파일과 위치(ROW)로 한다. GTID는 꺼져 있다. Primary를 다시 시작해야 켤 수 있어 쓰지 않았다. [docs:runbooks/mysql-replica.md:13] [code:apps/petmint/mysql/replica.yaml:3]
- 자동 전환은 없다. Operator(Group Replication, Orchestrator)는 부품과 메모리가 늘어 버리고 Replica와 수동 승격을 골랐다. [docs:history/build_log/08_scale_out.md:132-137]
- 복제 계정은 `repl`@`%`(REPLICATION SLAVE만)이고 암호는 네임스페이스마다 Secret `mysql-repl`(키 `password`)에 있다. 사람이 만들고 저장소에는 없다. [docs:runbooks/mysql-replica.md:15]
- Grafana 데이터소스 둘이 Replica를 읽는다(`mysql-replica.petmint.svc:3306`, `runshoes-mysql-replica.runshoes.svc:3306`). [code:apps/monitoring/grafana/datasource.yaml:26-32] [code:apps/monitoring/grafana/datasource.yaml:43-48]
- petmint 덤프는 매일 03:30 Asia/Seoul에 호스트 NFS `192.168.122.1:/srv/nfs/backup/petmint`로 간다. 호스트 쪽 실제 디렉터리는 `~/backup/mysql/petmint`다. [code:apps/petmint/backup/cronjob.yaml:1] [code:apps/petmint/backup/cronjob.yaml:16-17] [code:apps/petmint/backup/cronjob.yaml:94]
- Harbor DB 백업도 같은 방식이다. `docs/07_registry.md`를 본다. [code:apps/harbor-backup/cronjob.yaml:2]

## 설정 자리

### Primary

- `apps/petmint/mysql/statefulset.yaml:18-20`, `apps/runshoes/mysql/statefulset.yaml:21-23`: `persistentVolumeClaimRetentionPolicy` Retain. StatefulSet을 지우거나 줄여도 PVC가 남는다. [code:apps/petmint/mysql/statefulset.yaml:18-20] [code:apps/runshoes/mysql/statefulset.yaml:21-23]
- `apps/runshoes/mysql/statefulset.yaml:8`: StorageClass reclaimPolicy가 Delete라 PVC를 지우면 데이터도 지워진다. [code:apps/runshoes/mysql/statefulset.yaml:8]
- `apps/petmint/mysql/statefulset.yaml:21-29`: nodeSelector와 affinity가 없다. local-path PV가 있는 w1에만 뜬다. [code:apps/petmint/mysql/statefulset.yaml:21-29] [code:apps/runshoes/mysql/statefulset.yaml:7]
- `apps/runshoes/mysql/statefulset.yaml:32-38`: `kubernetes.io/hostname In [w1-k8s]` preferred weight 100. [code:apps/runshoes/mysql/statefulset.yaml:32-38]
- `apps/petmint/mysql/statefulset.yaml:33`, `apps/runshoes/mysql/statefulset.yaml:43`: `--innodb-buffer-pool-size=256M`. [code:apps/petmint/mysql/statefulset.yaml:33] [code:apps/runshoes/mysql/statefulset.yaml:43]
- runshoes만 `--default-time-zone=+00:00`, `--performance-schema=OFF`, collation `utf8mb4_unicode_ci`다. petmint collation은 `utf8mb4_0900_ai_ci`. [code:apps/runshoes/mysql/statefulset.yaml:45-47] [code:apps/petmint/mysql/statefulset.yaml:35]
- 탐침은 `mysqladmin ping -h 127.0.0.1`. 인증 없이 응답만 보므로 암호가 프로세스 인자에 남지 않는다. [code:apps/petmint/mysql/statefulset.yaml:45-56]
- 자원: Primary requests cpu 200m, memory 512Mi, limits memory 1Gi. [code:apps/petmint/mysql/statefulset.yaml:57-59] [code:apps/runshoes/mysql/statefulset.yaml:73-75]
- root 암호: petmint는 Secret `mysql-root`, runshoes는 Secret `runshoes-mysql`. [code:apps/petmint/mysql/statefulset.yaml:37-41] [code:apps/runshoes/mysql/statefulset.yaml:49-50]

### Replica

- `--server-id=2`, `--relay-log=relay-bin`. Primary는 기본값 1이다. [code:apps/petmint/mysql/replica.yaml:62-64] [code:apps/runshoes/mysql/replica.yaml:56-58]
- 나머지 인자는 각 Primary와 같은 값을 손으로 맞춰 적었다. [code:apps/petmint/mysql/replica.yaml:65-67] [code:apps/runshoes/mysql/replica.yaml:59-63]
- `read_only`, `super_read_only`는 인자가 아니라 `SET PERSIST`로 건다. 명령줄 인자가 PERSIST보다 앞서서 인자로 걸면 승격 때 풀 수 없다. [code:apps/petmint/mysql/replica.yaml:4-5]
- `nodeSelector: node.ronanlab.dev/role: app`과 Primary 라벨에 대한 required podAntiAffinity(`topologyKey: kubernetes.io/hostname`). app 노드(w1, w2) 중 Primary가 없는 w2에 뜬다. [code:apps/petmint/mysql/replica.yaml:50-58] [code:apps/runshoes/mysql/replica.yaml:44-52]
- `REPL_PASSWORD`는 Secret `mysql-repl`의 `password`를 optional로 받는다. Secret이 없어도 Pod는 뜬다. [code:apps/petmint/mysql/replica.yaml:72-74] [code:apps/runshoes/mysql/replica.yaml:67-68]
- runshoes Replica에는 `MYSQL_DATABASE`, `MYSQL_USER`가 없다. 데이터베이스와 계정은 Primary 덤프로 온다. [code:apps/runshoes/mysql/replica.yaml:4]
- 자원: requests cpu 100m, memory 512Mi, limits memory 1Gi. PVC는 Primary와 같은 크기(petmint 10Gi, runshoes 2Gi). [code:apps/petmint/mysql/replica.yaml:89-103] [code:apps/runshoes/mysql/replica.yaml:83-97]
- petmint Replica만 `argocd.argoproj.io/sync-wave: "0"`이 붙어 있다. runshoes Replica에는 없다. [code:apps/petmint/mysql/replica.yaml:15-16] [code:apps/petmint/mysql/replica.yaml:31-32] [code:apps/runshoes/mysql/replica.yaml:21-27]

### 시드 스크립트 `scripts/mysql-replica-seed.sh`

- 인자: 네임스페이스, Primary Pod, 복제 원본 호스트 이름(`<Pod>.<Service>`), Replica Pod. [code:scripts/mysql-replica-seed.sh:3-4] [code:scripts/mysql-replica-seed.sh:11]
- 넷째 인자에 `replica`가 없거나 둘째 인자에 `replica`가 있으면 멈춘다. [code:scripts/mysql-replica-seed.sh:12-13]
- 1단계: Replica에서 `STOP REPLICA; RESET REPLICA ALL;`, `read_only`와 `super_read_only`를 PERSIST로 끈다. [code:scripts/mysql-replica-seed.sh:17-18]
- 2단계: Primary에서 `mysqldump --all-databases --single-transaction --source-data=2 --routines --triggers --events --flush-privileges --set-gtid-purged=OFF --hex-blob`을 Replica로 바로 흘린다. awk가 `CHANGE REPLICATION SOURCE`나 `CHANGE MASTER` 주석 줄만 따로 적는다. [code:scripts/mysql-replica-seed.sh:20-27]
- 8.0.46 mysqldump는 `--source-data`여도 옛 문법(`MASTER_LOG_FILE`)으로 적어 둘 다 받는다. [code:scripts/mysql-replica-seed.sh:29-31]
- 3단계: `CHANGE REPLICATION SOURCE TO … SOURCE_USER='repl', … GET_SOURCE_PUBLIC_KEY=1; START REPLICA; SET PERSIST super_read_only=ON;` [code:scripts/mysql-replica-seed.sh:36-41]
- 암호는 각 Pod의 환경변수(`MYSQL_ROOT_PASSWORD`, `REPL_PASSWORD`)로만 쓴다. [code:scripts/mysql-replica-seed.sh:9]

### 확인 스크립트 `scripts/mysql-replica-check.sh`

- 복제 상태 줄(`Replica_IO_Running`, `Replica_SQL_Running`, `Seconds_Behind_Source`, `Last_IO_Error`, `Last_SQL_Error`)과 `@@super_read_only`. [code:scripts/mysql-replica-check.sh:10-12]
- 시스템 스키마를 뺀 모든 BASE TABLE의 `COUNT(*)`와 `mysql.user` 목록을 양쪽에서 뽑아 비교한다. 다르면 diff 앞 20줄을 내고 1로 끝난다. [code:scripts/mysql-replica-check.sh:13-20]
- Primary에 `repl_check` 데이터베이스를 만들어 값 하나를 넣고 Replica에서 읽은 뒤 Primary에서 `DROP`한다. 그 DROP이 Replica에도 넘어갔는지 본다. [code:scripts/mysql-replica-check.sh:21-28]

### 백업 `apps/petmint/backup/cronjob.yaml`

- `schedule: "30 3 * * *"`, `timeZone: Asia/Seoul`, `concurrencyPolicy: Forbid`, `startingDeadlineSeconds: 3600`. [code:apps/petmint/backup/cronjob.yaml:16-19]
- Job `backoffLimit: 1`, `activeDeadlineSeconds: 900`. [code:apps/petmint/backup/cronjob.yaml:24-25]
- uid/gid 999로 돈다. NFS가 all_squash라 호스트에서는 kopo17 소유로 써진다. [code:apps/petmint/backup/cronjob.yaml:32-35]
- 암호는 Secret `mysql-root`를 환경변수 `MYSQL_PWD`로 받는다. 명령 인자에 넣지 않는다. [code:apps/petmint/backup/cronjob.yaml:5] [code:apps/petmint/backup/cronjob.yaml:40-42]
- 대상은 `--databases petmint insurance_core`. `mysql` 스키마는 뜨지 않는다. [code:apps/petmint/backup/cronjob.yaml:2-3] [code:apps/petmint/backup/cronjob.yaml:57-58]
- 파일 이름 `petmint-YYYYmmdd-HHMMSS.sql.gz`, `.part`로 쓰고 `gzip -t`와 끝 줄 `-- Dump completed`를 확인한 뒤 이름을 바꾸고 `.sha256`을 만든다. [code:apps/petmint/backup/cronjob.yaml:55-63]
- 보존: `RETAIN_DAYS=30`, `KEEP_MIN=7`. 최신 7개 뒤의 것 중 30일 지난 것만 지운다. [code:apps/petmint/backup/cronjob.yaml:45-48] [code:apps/petmint/backup/cronjob.yaml:65-68]
- PV `petmint-backup`: NFS `192.168.122.1:/srv/nfs/backup/petmint`, `nfsvers=4.2`, ReadWriteMany, Retain, `claimRef` petmint/petmint-backup. 용량 5Gi는 바인딩용 표시다. [code:apps/petmint/backup/cronjob.yaml:81-94]
- 호스트 export 설정은 petmint-rag-chatbot 저장소의 `deploy/scripts/host-nfs-backup-setup.sh`(sudo)다. [code:apps/petmint/backup/cronjob.yaml:79]
- 복구 절차는 petmint-rag-chatbot `docs/02_pipeline/12_data_storage.md` 1-5절에 있다. [code:apps/petmint/backup/cronjob.yaml:8]

## 바꾸거나 다시 만들기

모든 명령은 m-k8s에서 친다. 호스트에서는 `cd ~/k8s-cluster && vagrant ssh m-k8s`로 들어간다. [code:CLAUDE.md:27]

매니페스트를 고치면 push 뒤 ArgoCD 자동 Sync로 들어간다(petmint, runshoes 둘 다 자동). [docs:history/cluster_state_20261116.md:57-58]

복제 계정을 처음 만든다. 네임스페이스마다 한 번이고, Secret이 이미 있으면 그대로 쓴다. 명령 전체는 런북 1절에 있다. [docs:runbooks/mysql-replica.md:17-28]

Replica를 채우거나 다시 만든다. Replica 데이터는 덮인다. [docs:runbooks/mysql-replica.md:32-40]

```bash
bash scripts/mysql-replica-seed.sh petmint  mysql-0          mysql-0.mysql                   mysql-replica-0
bash scripts/mysql-replica-seed.sh runshoes runshoes-mysql-0 runshoes-mysql-0.runshoes-mysql runshoes-mysql-replica-0
```

승격(Primary w1이 돌아오지 않을 때)은 런북 3절, w1을 다시 Primary로 되돌리는 것은 런북 4절을 그대로 따른다. Service selector를 kubectl로 바꾼 뒤 `apps/<앱>/mysql/service.yaml`도 같게 고쳐야 한다. 안 하면 다음 자동 Sync가 되돌린다. [docs:runbooks/mysql-replica.md:42-85]

백업을 지금 한 번 돌린다.

```bash
kubectl -n petmint create job --from=cronjob/mysql-backup mysql-backup-manual-$(date +%s)
```

다음은 사람 승인이 있어야 한다. 운영 DB `DROP`과 데이터 지우기, PVC와 PV 삭제, 네임스페이스 삭제. [code:CLAUDE.md:35-38] PVC를 지우면 local-path reclaimPolicy Delete라 노드의 데이터 디렉터리도 지워진다. [code:apps/runshoes/mysql/statefulset.yaml:8]

## 확인

```bash
bash scripts/mysql-replica-check.sh petmint  mysql-0          mysql-replica-0
bash scripts/mysql-replica-check.sh runshoes runshoes-mysql-0 runshoes-mysql-replica-0
```

기대 결과: [code:scripts/mysql-replica-check.sh:10-28]
- `Replica_IO_Running: Yes`, `Replica_SQL_Running: Yes`, `Seconds_Behind_Source: 0`, `Last_IO_Error`와 `Last_SQL_Error` 빈칸 [code:scripts/mysql-replica-check.sh:10-11]
- `Replica super_read_only=1` [code:scripts/mysql-replica-check.sh:12]
- `같음: 테이블 N개 행 수`로 시작하는 줄(뒤에 계정 수가 붙는다). `다름:`이면 diff가 나오고 1로 끝난다 [code:scripts/mysql-replica-check.sh:20]
- `쓰기 전달:`로 시작하고 `둘 다 Replica 에 넘어감`으로 끝나는 줄

배치:

```bash
kubectl -n petmint  get pod -o wide -l 'app.kubernetes.io/name in (mysql,mysql-replica)'
kubectl -n runshoes get pod -o wide -l 'app.kubernetes.io/name in (runshoes-mysql,runshoes-mysql-replica)'
kubectl get pvc -A | grep mysql
```

기대: Primary Pod는 w1-k8s, Replica Pod는 w2-k8s. [docs:runbooks/mysql-replica.md:8-9]

백업:

```bash
kubectl -n petmint get cronjob mysql-backup
kubectl -n petmint get job -l app.kubernetes.io/name=mysql-backup
kubectl -n petmint logs job/<가장 최근 Job>
```

기대: 로그 끝에 `백업 petmint-….sql.gz <크기>바이트`와 `남은 백업 N개`. 호스트 `~/backup/mysql/petmint`에 `.sql.gz`와 `.sha256`이 짝으로 있다. [code:apps/petmint/backup/cronjob.yaml:64] [code:apps/petmint/backup/cronjob.yaml:69]

## 알려진 한계

- 자동 전환이 없다. w1이 멈추면 승격 전까지 두 앱의 DB 쓰기가 실패한다. [docs:history/build_log/08_scale_out.md:28]
- 두 Primary가 모두 w1에 있다. [code:apps/runshoes/mysql/statefulset.yaml:6-7]
- petmint Primary에는 노드 규칙이 없다. PV를 새로 만들면 어느 노드에 뜰지 정해지지 않는다. [code:apps/petmint/mysql/statefulset.yaml:21-29]
- runshoes는 정기 백업이 없다. 스키마를 바꾸기 전 손 덤프만 있다(`apps/runshoes/runbooks/auth-v3.md` 2절). [code:apps/runshoes/README.md:54]
- Replica는 백업이 아니다. Primary에서 지운 것은 Replica에서도 지워진다. [docs:history/build_log/08_scale_out.md:79]
- petmint 백업에 `mysql` 스키마(계정)가 없다. 계정은 초기화 Job이 다시 만든다. [code:apps/petmint/backup/cronjob.yaml:2-3]
- 백업이 VM을 돌리는 같은 호스트 디스크에 있다. [code:apps/petmint/backup/cronjob.yaml:1]
- Replica 인자는 Primary 인자를 손으로 복사한 것이다. Primary 인자를 바꾸면 replica.yaml도 같이 고친다. [code:apps/petmint/mysql/replica.yaml:61-67]
- 매니페스트 주석 몇 곳이 지금과 다르다. petmint statefulset 머리의 「나중에 runshoes」(runshoes는 따로 MySQL을 둔다), 두 statefulset의 「워커 VM이 4GB」(지금 8GB), runshoes statefulset의 「노드가 3대」(지금 워커 넷). [code:apps/petmint/mysql/statefulset.yaml:1] [code:apps/petmint/mysql/statefulset.yaml:33] [code:apps/runshoes/mysql/statefulset.yaml:7] [docs:history/build_log/08_scale_out.md:3]

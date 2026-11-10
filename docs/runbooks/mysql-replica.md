# 런북 — MySQL Replica · 수동 승격

petmint · runshoes MySQL 각각 Primary(w1) 하나와 Replica(w2) 하나(2026-11-10 가용성 묶음 2). **자동 전환은 없다** — Primary가 죽으면 사람이 이 런북대로 Replica를 승격한다.
Operator(Group Replication · Orchestrator 등)는 자원 제약으로 쓰지 않았다([../02_availability.md](../02_availability.md) 4절).

| | petmint | runshoes |
| --- | --- | --- |
| Primary | StatefulSet `mysql` → Pod `mysql-0`(w1), Service `mysql` | `runshoes-mysql` → `runshoes-mysql-0`(w1), Service `runshoes-mysql` |
| Replica | `mysql-replica` → `mysql-replica-0`(w2), Service `mysql-replica` | `runshoes-mysql-replica` → `runshoes-mysql-replica-0`(w2) |
| 매니페스트 | `apps/petmint/mysql/` (수동 Sync) | `apps/runshoes/mysql/` (자동 Sync) |
| 앱이 보는 곳 | Service `mysql`(Primary만 고른다) | Service `runshoes-mysql` |

- 복제: binlog 파일 · 위치(ROW). GTID는 꺼져 있다 — 켜려면 Primary를 다시 시작해야 해서 쓰지 않았다
- Primary server_id 1(기본값), Replica 2(인자). Replica의 `read_only` · `super_read_only`는 `SET PERSIST`로 건다 — 인자로 걸면 승격 때 풀 수 없다
- 복제 계정 `repl`@`%`(REPLICATION SLAVE만), 비밀번호는 각 네임스페이스 Secret `mysql-repl`(키 `password`) — 사람이 만든다, 저장소에 없다

## 1. 처음 한 번 — 복제 계정

```bash
# m-k8s. 네임스페이스마다(petmint · runshoes). Secret 이 있으면 그대로 쓴다
kubectl -n <ns> create secret generic mysql-repl --from-literal=password="$(head -c 32 /dev/urandom | base64 | tr -dc A-Za-z0-9 | head -c 32)"
# Primary 에 계정 — 비밀번호는 표준 입력으로(명령 인자 · 화면에 남기지 않는다)
P=$(kubectl -n <ns> get secret mysql-repl -o jsonpath='{.data.password}' | base64 -d)
printf "CREATE USER IF NOT EXISTS 'repl'@'%%' IDENTIFIED WITH caching_sha2_password BY '%s';\nGRANT REPLICATION SLAVE ON *.* TO 'repl'@'%%';\n" "$P" \
  | kubectl -n <ns> exec -i <primary-pod> -- sh -c 'MYSQL_PWD=$MYSQL_ROOT_PASSWORD mysql -uroot'; unset P
```

Replica Pod는 Secret을 `REPL_PASSWORD`(optional)로 받는다 — Secret을 나중에 만들었으면 Replica Pod를 한 번 지워 다시 띄운다.

## 2. Replica 채우기 · 다시 만들기

```bash
bash scripts/mysql-replica-seed.sh petmint  mysql-0          mysql-0.mysql                   mysql-replica-0
bash scripts/mysql-replica-seed.sh runshoes runshoes-mysql-0 runshoes-mysql-0.runshoes-mysql runshoes-mysql-replica-0
bash scripts/mysql-replica-check.sh <ns> <primary-pod> <replica-pod>     # 행 수 · 계정 · 쓰기 전달
```

- Primary는 읽기만 한다 — `mysqldump --single-transaction`(잠금 없음) `--source-data=2`, 덤프는 디스크에 남기지 않고 Replica로 바로 흘린다
- `mysql` 스키마(계정)까지 옮긴다 — 승격했을 때 앱 계정이 있어야 한다
- Replica의 데이터는 덮인다. 복제가 깨졌을 때(`Last_SQL_Error`)도, 승격 시험 뒤에도 이것으로 다시 만든다(5초 안팎, 2026-11-10)

## 3. 승격 — Primary(w1)가 죽었을 때

**판단이 먼저다.** Primary가 잠깐 끊긴 것(노드 재부팅 · Pod 재시작)이면 기다리는 편이 낫다 — 승격하면 되돌리는 데 Replica를 다시 만드는 일(4절)이 따른다.
승격은 "w1이 곧 돌아오지 않는다"가 확실할 때만 한다.

```bash
# 0. 상황 — Primary Pod 가 어디서 어떻게 멈췄나
kubectl get node w1-k8s; kubectl -n <ns> get pod <primary-pod> -o wide

# 1. Replica 가 받은 것을 다 적용했는지. Primary 가 죽었으면 IO 는 오류(연결 실패)가 정상, SQL 상태가 아래 문구면 다 적용한 것이다
kubectl -n <ns> exec <replica-pod> -- sh -c 'MYSQL_PWD=$MYSQL_ROOT_PASSWORD mysql -uroot -e "SHOW REPLICA STATUS\G"' \
  | grep -E 'Replica_SQL_Running_State|Seconds_Behind|Last_IO_Error'
#    Replica_SQL_Running_State: Replica has read all relay log; waiting for more updates

# 2. 승격 — 복제를 끊고 쓰기 가능하게(PERSIST — 재시작해도 유지)
kubectl -n <ns> exec <replica-pod> -- sh -c 'MYSQL_PWD=$MYSQL_ROOT_PASSWORD mysql -uroot -e "
  STOP REPLICA; RESET REPLICA ALL; SET PERSIST super_read_only=OFF; SET PERSIST read_only=OFF; SELECT @@read_only;"'

# 3. 앱이 새 Primary 를 보게 — Service selector 를 Replica 라벨로. 먼저 kubectl 로(바로 반영), 그다음 git 에 같은 변경
kubectl -n petmint  patch svc mysql          -p '{"spec":{"selector":{"app.kubernetes.io/name":"mysql-replica"}}}'
kubectl -n runshoes patch svc runshoes-mysql -p '{"spec":{"selector":{"app.kubernetes.io/name":"runshoes-mysql-replica"}}}'
#    git: apps/<앱>/mysql/service.yaml 의 selector 를 같게 고쳐 push — 안 하면 다음 Sync 가 옛 selector 로 되돌린다
#    (runshoes 는 자동 Sync — Jenkins 태그 커밋 하나에 되돌아간다). petmint 는 push 뒤 Sync

# 4. 앱 재시작 — 끊긴 연결을 버리고 새로 붙게(한 Pod 씩, 4단계 배치에서 2개)
kubectl -n petmint  rollout restart deploy/petmint-app && kubectl -n petmint  rollout status deploy/petmint-app
kubectl -n runshoes rollout restart deploy/runshoes    && kubectl -n runshoes rollout status deploy/runshoes

# 5. 확인 — 앱 응답, 쓰기(로그인 · 리뷰 등), 새 Primary 의 @@server_id = 2
```

**옛 Primary가 돌아오면 그대로 쓰지 않는다.** w1이 살아나면 `mysql-0`도 쓰기 가능한 채 뜬다 — 앱은 Service가 바뀌어 그쪽으로 가지 않지만,
그 데이터는 승격 시점에서 멈춘 옛것이다. 둘 다 쓰기 가능한 채 두지 않는다:
`kubectl -n <ns> scale sts <primary-sts> --replicas=0`로 멈춰 두고 4절로 간다.

## 4. 되돌리기 — w1을 다시 Primary로

승격 뒤의 쓰기는 새 Primary(w2)에만 있다. 옛 Primary를 그 위에 다시 만든 뒤 계획된 전환을 한 번 더 한다.

1. 옛 Primary(`mysql-0`)를 새 Primary의 Replica로 — 2절 스크립트를 인자를 바꿔 쓸 수 없다(스크립트는 이름에 `replica`가 든 Pod만 덮는다 — 실수 방지).
   옛 Primary를 덮는 것은 손으로 한다: 옛 Primary의 덤프를 먼저 떠 두고(`apps/petmint/backup`, runbooks/auth-v3.md 2절과 같은 방법),
   새 Primary에서 덤프 → 옛 Primary에 넣기 → `CHANGE REPLICATION SOURCE TO SOURCE_HOST='<새 Primary Pod>.<Service>' …` → `START REPLICA`
2. 따라잡으면 쓰기를 멈추고(앱 replicas 0 또는 점검 화면) 3절을 반대로: 옛 Primary 승격 → Service selector 를 원래대로(git 포함) → 앱 재시작
3. w2 쪽을 2절 스크립트로 다시 Replica로 만든다

## 시험 기록

### 2026-11-10 — 구성 · 승격 시험(운영 트래픽은 옮기지 않음)

- 구성: 두 Primary 모두 binlog ROW · server_id 1이 이미 켜져 있어 Primary를 다시 시작하지 않았다. 시드 6초(runshoes) · 6초(petmint),
  덤프 시점 binlog runshoes `binlog.000004:1015`, petmint `binlog.000006:4461`
- 확인(`mysql-replica-check.sh`): runshoes 테이블 11개 행 수 · 계정 7개 같음, petmint 테이블 19개 · 계정 8개 같음, IO/SQL Yes · 지연 0 · `super_read_only=1`,
  Primary에서 만들고 지운 시험 데이터베이스가 Replica에도 생겼다 사라짐
- **승격 시험(runshoes)**: 운영 Primary · 앱은 그대로 두고 Replica를 실제로 승격했다. 앱 Service와 같은 모양의 시험 Service `mysql-drill`(처음엔 Primary를 가리킴)을 두고 selector를 바꿨다

  | 단계 | 걸린 시간 |
  | --- | --- |
  | 따라잡음 확인 + `STOP REPLICA; RESET REPLICA ALL; read_only 끔` | 0.2초 |
  | Service selector 전환 → 그 이름으로 새 쪽(server_id 2)에 붙음 | 0.1초 |
  | 새 Primary에 쓰기(시험 데이터베이스 만들기 · 넣기 · 지우기) | 합계 0.5초 |
  | 앱 재시작(rollout restart, 2 Pod) | 4단계 배치 고정 뒤 측정 — 아래 |
  | 시험 뒤 Replica 다시 만들기 + 확인 | 10초 |

- 기계가 하는 일은 1초가 안 된다. **승격에 걸리는 시간은 사람이 정한다** — 장애를 알아채고(알림), w1이 돌아오지 않는다고 판단하고, git에 selector를 반영하는 시간.
  앱 트래픽까지 옮기는 진짜 전환은 운영 쓰기를 멈춰야 하고 되돌리는 데 전환이 한 번 더 들어서 이번에는 하지 않았다 — 그때 이 표의 앱 재시작 · 앱 확인 칸을 다시 잰다

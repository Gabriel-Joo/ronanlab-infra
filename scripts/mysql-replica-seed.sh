#!/usr/bin/env bash
# Replica 를 Primary 에서 처음부터 채우고 복제를 시작한다(docs/runbooks/mysql-replica.md 2절). m-k8s 에서:
#   bash scripts/mysql-replica-seed.sh petmint  mysql-0          mysql-0.mysql                    mysql-replica-0
#   bash scripts/mysql-replica-seed.sh runshoes runshoes-mysql-0 runshoes-mysql-0.runshoes-mysql  runshoes-mysql-replica-0
# - Primary 는 읽기만 한다: mysqldump --single-transaction(잠금 없음) --source-data=2(덤프 시점 binlog 위치를 주석으로)
# - 덤프는 디스크에 남기지 않는다 — Primary → Replica 로 바로 흘린다. binlog 위치만 머리에서 뽑는다
# - mysql 스키마(계정)까지 옮긴다 — 승격했을 때 앱 계정이 Replica 에 있어야 한다
# - Replica 의 기존 데이터는 덮인다(다시 만들기에도 쓴다). Primary 를 Replica 로 착각하지 않게 인자를 두 번 본다
# - 비밀번호는 각 Pod 의 환경변수(MYSQL_ROOT_PASSWORD · REPL_PASSWORD)로만 — 명령 인자 · 화면에 내지 않는다
set -euo pipefail
NS=$1 PRIMARY=$2 SOURCE_HOST=$3 REPLICA=$4
[[ $REPLICA == *replica* ]] || { echo "넷째 인자는 Replica Pod 여야 한다: $REPLICA" >&2; exit 1; }
[[ $PRIMARY != *replica* ]] || { echo "둘째 인자는 Primary Pod 여야 한다: $PRIMARY" >&2; exit 1; }
t0=$(date +%s)
R() { kubectl -n "$NS" exec -i "$REPLICA" -- sh -c "MYSQL_PWD=\$MYSQL_ROOT_PASSWORD mysql -uroot $*"; }

# 1. 복제를 멈추고(다시 만들 때) Replica 를 쓰기 가능하게 — 덤프를 넣으려면
R -e "'STOP REPLICA; RESET REPLICA ALL; SET PERSIST super_read_only=OFF; SET PERSIST read_only=OFF;'" 2>&1 | grep -v Warning || true

# 2. 덤프 → Replica. 머리의 CHANGE REPLICATION SOURCE 줄(주석)에서 binlog 위치를 뽑는다
# awk 한 프로세스가 흘려보내면서 위치 줄만 따로 적는다 — tee >(grep -m1) 은 grep 이 먼저 끝나면 tee 가 SIGPIPE 로 끊긴다(2026-11-10 겪음)
COORD=$(mktemp) ERR=$(mktemp)
kubectl -n "$NS" exec "$PRIMARY" -- sh -c 'MYSQL_PWD=$MYSQL_ROOT_PASSWORD mysqldump -uroot --all-databases \
    --single-transaction --source-data=2 --routines --triggers --events --flush-privileges \
    --set-gtid-purged=OFF --hex-blob' 2>"$ERR" \
  | awk -v f="$COORD" '/^-- CHANGE (REPLICATION SOURCE|MASTER) TO/ && !done { print > f; close(f); done=1 } { print }' \
  | R 2>&1 | grep -v Warning || true
grep -v Warning "$ERR" >&2 || true; rm -f "$ERR"
# 8.0.46 mysqldump 는 --source-data 여도 옛 문법(CHANGE MASTER TO MASTER_LOG_FILE=…)으로 적는다 — 둘 다 받는다
FILE=$(sed -nE "s/.*(SOURCE|MASTER)_LOG_FILE='([^']+)'.*/\2/p" "$COORD")
POS=$(sed -nE "s/.*(SOURCE|MASTER)_LOG_POS=([0-9]+).*/\2/p" "$COORD")
rm -f "$COORD"
[[ -n $FILE && $POS =~ ^[0-9]+$ ]] || { echo "binlog 위치를 못 뽑았다" >&2; exit 1; }
echo "덤프 시점 binlog: $FILE $POS ($(( $(date +%s) - t0 ))초)"

# 3. 복제 시작 + 읽기 전용(PERSIST — 재시작해도 유지, 승격 때 같은 방법으로 푼다)
kubectl -n "$NS" exec "$REPLICA" -- sh -c "MYSQL_PWD=\$MYSQL_ROOT_PASSWORD mysql -uroot -e \"
  CHANGE REPLICATION SOURCE TO SOURCE_HOST='$SOURCE_HOST', SOURCE_PORT=3306, SOURCE_USER='repl',
    SOURCE_PASSWORD='\$REPL_PASSWORD', SOURCE_LOG_FILE='$FILE', SOURCE_LOG_POS=$POS, GET_SOURCE_PUBLIC_KEY=1;
  START REPLICA;
  SET PERSIST super_read_only=ON;\"" 2>&1 | grep -v Warning || true
sleep 3
kubectl -n "$NS" exec "$REPLICA" -- sh -c 'MYSQL_PWD=$MYSQL_ROOT_PASSWORD mysql -uroot -e "SHOW REPLICA STATUS\G" 2>/dev/null' \
  | grep -E 'Replica_IO_Running:|Replica_SQL_Running:|Seconds_Behind_Source|Last_IO_Error:|Last_SQL_Error:|Source_Log_File:|Exec_Source_Log_Pos'
echo "끝 $(( $(date +%s) - t0 ))초"

#!/usr/bin/env bash
# Replica 가 Primary 와 같은지 본다(docs/runbooks/mysql-replica.md). m-k8s 에서:
#   bash scripts/mysql-replica-check.sh petmint  mysql-0          mysql-replica-0
#   bash scripts/mysql-replica-check.sh runshoes runshoes-mysql-0 runshoes-mysql-replica-0
# 1) 복제 상태  2) 앱 데이터베이스의 테이블별 정확한 행 수(COUNT(*)) · 계정 목록이 같은지
# 3) 쓰기가 넘어가는지 — Primary 에 시험 데이터베이스 repl_check 를 만들고 Replica 에서 읽은 뒤 Primary 에서 지운다(그 DROP 도 넘어간다)
set -euo pipefail
NS=$1 PRIMARY=$2 REPLICA=$3
Q() { kubectl -n "$NS" exec -i "$1" -- sh -c 'MYSQL_PWD=$MYSQL_ROOT_PASSWORD mysql -uroot -N -B 2>/dev/null'; }
kubectl -n "$NS" exec "$REPLICA" -- sh -c 'MYSQL_PWD=$MYSQL_ROOT_PASSWORD mysql -uroot -e "SHOW REPLICA STATUS\G" 2>/dev/null' \
  | grep -E 'Replica_IO_Running:|Replica_SQL_Running:|Seconds_Behind_Source|Last_(IO|SQL)_Error:'
echo "SELECT @@super_read_only;" | Q "$REPLICA" | sed 's/^/Replica super_read_only=/'
# 행 수 쿼리를 Primary 에서 만든다(앱 데이터베이스 전부 — 시스템 스키마 제외)
GEN="SELECT CONCAT('SELECT ', GROUP_CONCAT(CONCAT('''', table_schema, '.', table_name, ' '', (SELECT COUNT(*) FROM \`', table_schema, '\`.\`', table_name, '\`)') SEPARATOR ' UNION ALL SELECT '), ';')
     FROM information_schema.tables WHERE table_type='BASE TABLE'
       AND table_schema NOT IN ('mysql','sys','performance_schema','information_schema');"
SQL=$( (echo "SET SESSION group_concat_max_len=1000000;"; echo "$GEN") | Q "$PRIMARY")
A=$( (echo "$SQL"; echo "SELECT CONCAT(user,'@',host) FROM mysql.user ORDER BY 1;") | Q "$PRIMARY" | sort)
B=$( (echo "$SQL"; echo "SELECT CONCAT(user,'@',host) FROM mysql.user ORDER BY 1;") | Q "$REPLICA" | sort)
if [ "$A" = "$B" ]; then echo "같음: 테이블 $(echo "$SQL" | grep -o 'UNION ALL' | wc -l | awk '{print $1+1}')개 행 수 · 계정 $(echo "$A" | grep -c '@')개"; else echo "다름:"; diff <(echo "$A") <(echo "$B") | head -20; exit 1; fi
T=$(date +%s)
echo "CREATE DATABASE repl_check; CREATE TABLE repl_check.t (v BIGINT); INSERT INTO repl_check.t VALUES ($T);" | Q "$PRIMARY"
sleep 2
GOT=$(echo "SELECT v FROM repl_check.t;" | Q "$REPLICA")
echo "DROP DATABASE repl_check;" | Q "$PRIMARY"
sleep 2
LEFT=$(echo "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name='repl_check';" | Q "$REPLICA")
[ "$GOT" = "$T" ] && [ "$LEFT" = 0 ] && echo "쓰기 전달: 만들기 · 지우기 둘 다 Replica 에 넘어감" || { echo "쓰기 전달 실패(got=$GOT left=$LEFT)"; exit 1; }

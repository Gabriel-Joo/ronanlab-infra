#!/usr/bin/env bash
# 호스트(GPU 머신)의 Harbor DB 백업 디렉터리를 NFS 쓰기로 공유한다 — 클러스터 CronJob harbor-db-backup(apps/harbor-backup/)이 쓰는 곳.
# sudo로 사람이 한 번 돌린다. 여러 번 돌려도 같다. petmint-rag-chatbot deploy/scripts/host-nfs-backup-setup.sh(MySQL 백업)와 같은 모양이다
# (그 스크립트 · host-nfs-setup.sh를 먼저 돌린 호스트를 전제한다 — NFSv4만 · ufw 2049).
#
#   sudo scripts/host-nfs-harbor-backup-setup.sh
#
# - 실제 파일은 ~/backup/harbor(SUDO_USER의 홈). /srv/nfs/backup/harbor에 bind mount해 그것을 연다 — PV에 홈 경로가 박히지 않는다
# - all_squash + anonuid/anongid = SUDO_USER — Pod의 uid와 상관없이 호스트 사용자 파일로 써진다
# - 사설망(192.168.122.0/24)에만. 다른 export 파일은 건드리지 않는다. nfs-server를 재시작하지 않는다(exportfs -ra만)
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "sudo로 돌린다" >&2; exit 1; }
U=${SUDO_USER:?sudo로 돌려야 SUDO_USER를 안다}
UID_=$(id -u "$U"); GID_=$(id -g "$U")
SRC=$(getent passwd "$U" | cut -d: -f6)/backup/harbor
DST=/srv/nfs/backup/harbor
NET=192.168.122.0/24
FSID=105   # 101~103 약관(ro), 104 petmint MySQL 백업

echo "--- 1. 원본 디렉터리 $SRC"
install -d -o "$U" -g "$U" -m 750 "$SRC"

echo "--- 2. bind mount $DST (rw)"
mkdir -p "$DST"
sed -i "\#[[:space:]]$DST[[:space:]]#d" /etc/fstab
echo "$SRC $DST none bind 0 0" >> /etc/fstab
findmnt -n "$DST" >/dev/null && umount "$DST"
mount "$DST"

echo "--- 3. export ($NET, rw, all_squash → $U)"
echo "$DST $NET(rw,sync,all_squash,anonuid=$UID_,anongid=$GID_,no_subtree_check,sec=sys,fsid=$FSID)" > /etc/exports.d/harbor-backup.exports
exportfs -ra

echo "--- 확인"
exportfs -v | grep -A1 "$DST"
findmnt -n -o TARGET,SOURCE,OPTIONS "$DST"

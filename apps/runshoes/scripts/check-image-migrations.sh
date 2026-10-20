#!/usr/bin/env bash
# Harbor 에 올라간 runshoes 이미지 안의 Flyway 마이그레이션(db/migration/V*.sql) sha256 을 낸다 — 배포 전에 "로컬에서 시험한 그 파일"이 들어갔는지.
# 호스트에서 돌린다(mk 로 m-k8s · w2 에 ssh). 이 호스트의 docker 로는 받을 수 없다 — 공개 경로(harbor.ronanlab.dev → Cloudflare)는
# Cloudflare Access 가 막는다(302 로그인 페이지). 그래서 노드의 containerd 로 받는다: 노드는 /etc/hosts 로 내부 VIP(192.168.122.240)에 붙고,
# kubelet 과 같은 길 · 같은 pull robot(Secret runshoes/harbor-pull)이다. 받은 것은 k8s 와 섞이지 않게 ctr 네임스페이스 rs-check 에 두고 끝나면 지운다.
#
#   apps/runshoes/scripts/check-image-migrations.sh <태그>          # 예: 0f789ad645bc
#   → V1__schema.sql <sha256> … 를 앱 리포의 같은 커밋 파일과 비교한다:
#     git -C <앱 리포> show <커밋>:backend/src/main/resources/db/migration/V3__auth.sql | sha256sum
#
# robot 비밀번호는 파이프로만 넘긴다(화면 · 파일에 남지 않는다). w2 에서 ctr 인자로 잠깐 보인다.
set -euo pipefail
TAG=${1:?태그(커밋 해시 12자리)}
IMG=harbor.ronanlab.dev/runshoes/runshoes:$TAG
MK=${MK:-$HOME/k8s-cluster/backup/2026-10-15-before-metallb/mk}
NODE=${NODE:-w2}

# 노드에서 돌 파이썬 — OCI tar 의 레이어에서 opt/app/app.jar(Dockerfile 4단계)를 찾아 안의 마이그레이션 sha256
read -r -d '' PY <<'EOF' || true
import hashlib, io, json, sys, tarfile, zipfile
outer = tarfile.open(sys.argv[1])
blob = lambda d: outer.extractfile("blobs/sha256/" + d.split(":")[1])
m = json.load(blob(json.load(outer.extractfile("index.json"))["manifests"][0]["digest"]))
if "manifests" in m: m = json.load(blob(m["manifests"][0]["digest"]))
for l in reversed(m["layers"]):
    with tarfile.open(fileobj=blob(l["digest"]), mode="r:*") as t:
        try: f = t.extractfile("opt/app/app.jar")
        except KeyError: continue
        z = zipfile.ZipFile(io.BytesIO(f.read()))
        for n in sorted(x for x in z.namelist() if "/db/migration/V" in x):
            print(n.split("/")[-1], hashlib.sha256(z.read(n)).hexdigest())
        sys.exit(0)
sys.exit("opt/app/app.jar 를 찾지 못했다")
EOF

"$MK" "kubectl -n runshoes get secret harbor-pull -o jsonpath='{.data.\.dockerconfigjson}'" | base64 -d |
  python3 -c 'import json,sys; a=json.load(sys.stdin)["auths"]["harbor.ronanlab.dev"]; print(a["username"]+":"+a["password"])' |
  "$MK" "$NODE" "read -r C; sudo ctr -n rs-check images pull --user \"\$C\" $IMG >/dev/null && unset C && echo \"받음  $IMG\""

printf '%s' "$PY" | "$MK" "$NODE" "cat > /tmp/rs-check.py"
"$MK" "$NODE" "set -e; trap 'sudo rm -f /tmp/rs-check.tar /tmp/rs-check.py; sudo ctr -n rs-check images rm $IMG >/dev/null 2>&1 || true' EXIT
  sudo ctr -n rs-check images export /tmp/rs-check.tar $IMG; sudo chmod 644 /tmp/rs-check.tar
  sudo ctr -n rs-check images ls | awk 'NR>1 {print \"digest\", \$3}'
  python3 /tmp/rs-check.py /tmp/rs-check.tar"

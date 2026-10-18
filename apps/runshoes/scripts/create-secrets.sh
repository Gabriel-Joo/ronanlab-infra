#!/usr/bin/env bash
# runshoes 네임스페이스의 Secret을 클러스터에 직접 만든다 — 값은 저장소·매니페스트에 남지 않는다(apps/petmint/scripts/create-secrets.sh와 같다).
# 지금은 Harbor pull Secret 하나뿐이다(db.json은 파일, Ollama는 사설망 직접 연결이라 자격 증명이 없다). 이미 있으면 건드리지 않는다.
#
#   HARBOR_USER='robot$runshoes+pull' HARBOR_PASSWORD=... apps/runshoes/scripts/create-secrets.sh
#   robot 계정 이름에는 $가 들어 있다 — 작은따옴표로
set -euo pipefail
NS=${NS:-runshoes}

kubectl get namespace "$NS" >/dev/null 2>&1 || kubectl create namespace "$NS"

if kubectl -n "$NS" get secret harbor-pull >/dev/null 2>&1; then
  echo "있음  harbor-pull (그대로 둔다)"
else
  kubectl -n "$NS" create secret docker-registry harbor-pull --docker-server=harbor.ronanlab.dev \
    --docker-username="${HARBOR_USER:?HARBOR_USER 필요}" --docker-password="${HARBOR_PASSWORD:?HARBOR_PASSWORD 필요}" >/dev/null
  echo "만듦  harbor-pull"
fi

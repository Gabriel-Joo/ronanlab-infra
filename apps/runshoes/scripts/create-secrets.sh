#!/usr/bin/env bash
# runshoes 네임스페이스의 Secret을 클러스터에 직접 만든다 — 값은 저장소·매니페스트에 남지 않는다(apps/petmint/scripts/create-secrets.sh와 같다).
# 이미 있는 Secret은 건드리지 않는다 — MySQL root 비밀번호는 데이터 디렉터리를 처음 만들 때만 쓰이므로, 바꾸면 접속이 엇갈린다.
#   runshoes-mysql  MYSQL_ROOT_PASSWORD · MYSQL_PASSWORD(앱 계정 runshoes) — 무작위, 화면에 나오지 않는다
#   harbor-pull     Harbor pull robot — HARBOR_USER · HARBOR_PASSWORD 를 줄 때만(이미 있으면 건너뛴다)
# Ollama는 사설망 직접 연결이라 자격 증명이 없다.
#
#   apps/runshoes/scripts/create-secrets.sh
#   HARBOR_USER='robot$runshoes+pull' HARBOR_PASSWORD=... apps/runshoes/scripts/create-secrets.sh   # harbor-pull 까지
#   robot 계정 이름에는 $가 들어 있다 — 작은따옴표로
set -euo pipefail
NS=${NS:-runshoes}

kubectl get namespace "$NS" >/dev/null 2>&1 || kubectl create namespace "$NS"

rand() { openssl rand -base64 33 | tr -d '/+=\n' | cut -c1-32; }

if kubectl -n "$NS" get secret runshoes-mysql >/dev/null 2>&1; then
  echo "있음  runshoes-mysql (그대로 둔다)"
else
  kubectl -n "$NS" create secret generic runshoes-mysql \
    --from-literal=MYSQL_ROOT_PASSWORD="$(rand)" --from-literal=MYSQL_PASSWORD="$(rand)" >/dev/null
  echo "만듦  runshoes-mysql"
fi

if kubectl -n "$NS" get secret harbor-pull >/dev/null 2>&1; then
  echo "있음  harbor-pull (그대로 둔다)"
elif [[ -z "${HARBOR_USER:-}" ]]; then
  echo "없음  harbor-pull — HARBOR_USER · HARBOR_PASSWORD 를 주고 다시 돌린다"
else
  kubectl -n "$NS" create secret docker-registry harbor-pull --docker-server=harbor.ronanlab.dev \
    --docker-username="${HARBOR_USER:?HARBOR_USER 필요}" --docker-password="${HARBOR_PASSWORD:?HARBOR_PASSWORD 필요}" >/dev/null
  echo "만듦  harbor-pull"
fi

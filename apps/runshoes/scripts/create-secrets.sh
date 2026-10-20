#!/usr/bin/env bash
# runshoes 네임스페이스의 Secret을 클러스터에 직접 만든다 — 값은 저장소·매니페스트에 남지 않는다(apps/petmint/scripts/create-secrets.sh와 같다).
# 이미 있는 Secret은 건드리지 않는다 — MySQL root 비밀번호는 데이터 디렉터리를 처음 만들 때만 쓰이므로, 바꾸면 접속이 엇갈린다.
#   runshoes-mysql  MYSQL_ROOT_PASSWORD · MYSQL_PASSWORD(앱 계정 runshoes) — 무작위, 화면에 나오지 않는다
#   harbor-pull     Harbor pull robot — HARBOR_USER · HARBOR_PASSWORD 를 줄 때만(이미 있으면 건너뛴다)
#   runshoes-auth   로그인(앱 리포 docs/AUTH_DESIGN.md) — JWT_SECRET(서명 키) · SEED_USER_PASSWORD(V3 사용자 30명 공통) · ADMIN_PASSWORD(admin@runshoes.test).
#                   무작위, 화면에 나오지 않는다. 시험 로그인에 쓸 값은 이렇게 본다(화면에 남는다 — 필요할 때만):
#                     kubectl -n runshoes get secret runshoes-auth -o jsonpath='{.data.SEED_USER_PASSWORD}' | base64 -d
#                   비밀번호 둘은 앱이 처음 뜰 때 "비밀번호가 없는 계정"에만 쓴다 — 나중에 Secret 을 바꿔도 이미 채운 계정은 그대로다.
#                   JWT_SECRET 을 바꾸면 발급된 토큰이 전부 무효가 된다(다시 로그인). Secret 을 바꾼 뒤에는 rollout restart
# Ollama는 사설망 직접 연결이라 자격 증명이 없다.
#
#   apps/runshoes/scripts/create-secrets.sh
#   HARBOR_USER='robot$runshoes+pull' HARBOR_PASSWORD=... apps/runshoes/scripts/create-secrets.sh   # harbor-pull 까지
#   robot 계정 이름에는 $가 들어 있다 — 작은따옴표로
set -euo pipefail
NS=${NS:-runshoes}

kubectl get namespace "$NS" >/dev/null 2>&1 || kubectl create namespace "$NS"

rand() { openssl rand -base64 33 | tr -d '/+=\n' | cut -c1-32; }
# 앱의 비밀번호 규칙(영문과 숫자를 함께)에 맞을 때까지 — 32자라 거의 한 번에 된다
password() { local p; while :; do p=$(rand); [[ $p =~ [A-Za-z] && $p =~ [0-9] ]] && { echo "$p"; return; }; done; }

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

if kubectl -n "$NS" get secret runshoes-auth >/dev/null 2>&1; then
  echo "있음  runshoes-auth (그대로 둔다)"
else
  kubectl -n "$NS" create secret generic runshoes-auth \
    --from-literal=JWT_SECRET="$(openssl rand -base64 48 | tr -d '\n')" \
    --from-literal=SEED_USER_PASSWORD="$(password)" --from-literal=ADMIN_PASSWORD="$(password)" >/dev/null
  echo "만듦  runshoes-auth"
fi

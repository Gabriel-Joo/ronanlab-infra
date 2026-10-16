#!/usr/bin/env bash
# ronanlab-infra(private) 의 GitHub deploy key 두 개를 만들어 클러스터 Secret 에 바로 넣는다 — m-k8s 에서 사람이 한 번 돌린다.
#   읽기: ArgoCD 가 apps/ 를 읽는다            → Secret argocd/repo-ronanlab-infra (ArgoCD 저장소 Secret)
#   쓰기: Jenkins 가 이미지 태그를 바꿔 push 한다 → Secret jenkins/ronanlab-infra-deploy-key (키 ssh-privatekey)
# 읽기·쓰기를 나누는 것은 Harbor robot 을 pull·push 로 나눈 것과 같다. 토큰 대신 deploy key — 만료로 배포가 조용히 멈추지 않는다.
#
#   ssh -i <m-k8s 키> vagrant@192.168.122.10 'bash -s' < scripts/make-deploy-keys.sh
#
# 개인 키는 화면에 나오지 않는다. RAM(/dev/shm)에서 만들어 Secret 에 넣고 지운다. 출력은 공개 키와 지문뿐 —
# 공개 키를 GitHub ronanlab-infra → Settings → Deploy keys 에 등록한다(읽기는 Allow write access 끔, 쓰기는 켬).
# 이미 있는 Secret 은 건드리지 않는다. 다시 만들려면 Secret 을 지우고(GitHub 의 옛 키도 지운다) 다시 돌린다.
set -euo pipefail
REPO_SSH=git@github.com:Gabriel-Joo/ronanlab-infra.git
T=$(mktemp -d /dev/shm/deploykeys.XXXXXX)
trap 'shred -u "$T"/* 2>/dev/null || true; rmdir "$T"' EXIT
chmod 700 "$T"

exists() { kubectl -n "$1" get secret "$2" >/dev/null 2>&1; }
fp() { ssh-keygen -lf "$1" | awk '{print $2}'; }

if exists argocd repo-ronanlab-infra; then
  echo "있음  argocd/repo-ronanlab-infra (그대로 둔다)"
else
  ssh-keygen -q -t ed25519 -N "" -C "argocd@ronanlab ronanlab-infra read" -f "$T/argocd"
  kubectl -n argocd create secret generic repo-ronanlab-infra \
    --from-literal=type=git --from-literal=url="$REPO_SSH" --from-file=sshPrivateKey="$T/argocd" >/dev/null
  kubectl -n argocd label secret repo-ronanlab-infra argocd.argoproj.io/secret-type=repository >/dev/null
  echo "만듦  argocd/repo-ronanlab-infra"
  echo "GitHub 등록 — Title: argocd-read, Allow write access: 끔. 다음 한 줄을 그대로 붙인다(앞 공백 없음):"
  awk '{print $1, $2, "argocd-read"}' "$T/argocd.pub"
fi

if exists jenkins ronanlab-infra-deploy-key; then
  echo "있음  jenkins/ronanlab-infra-deploy-key (그대로 둔다)"
else
  ssh-keygen -q -t ed25519 -N "" -C "jenkins@ronanlab ronanlab-infra write" -f "$T/jenkins"
  kubectl -n jenkins create secret generic ronanlab-infra-deploy-key --from-file=ssh-privatekey="$T/jenkins" >/dev/null
  echo "만듦  jenkins/ronanlab-infra-deploy-key"
  echo "GitHub 등록 — Title: jenkins-write, Allow write access: 켬. 다음 한 줄을 그대로 붙인다(앞 공백 없음):"
  awk '{print $1, $2, "jenkins-write"}' "$T/jenkins.pub"
fi

echo "--- Secret 안 키에서 다시 계산한 공개 키 — 이미 있는 Secret 이면 여기 것을 등록한다. 지문은 GitHub Deploy keys 화면의 SHA256 과 같아야 한다"
pub() {  # pub <ns> <secret> <key> <title>
  kubectl -n "$1" get secret "$2" -o jsonpath="{.data.$3}" | base64 -d > "$T/chk"; chmod 600 "$T/chk"
  ssh-keygen -y -f "$T/chk" | awk -v t="$4" '{print $1, $2, t}' > "$T/chk.pub"
  cat "$T/chk.pub"; echo "  지문 $(fp "$T/chk.pub")"
  shred -u "$T/chk"
}
pub argocd  repo-ronanlab-infra       sshPrivateKey   argocd-read
pub jenkins ronanlab-infra-deploy-key ssh-privatekey  jenkins-write

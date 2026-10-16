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
  echo "  ▶ GitHub 등록 — Title: argocd-read   Allow write access: 끔"
  echo "    $(cat "$T/argocd.pub")"
fi

if exists jenkins ronanlab-infra-deploy-key; then
  echo "있음  jenkins/ronanlab-infra-deploy-key (그대로 둔다)"
else
  ssh-keygen -q -t ed25519 -N "" -C "jenkins@ronanlab ronanlab-infra write" -f "$T/jenkins"
  kubectl -n jenkins create secret generic ronanlab-infra-deploy-key --from-file=ssh-privatekey="$T/jenkins" >/dev/null
  echo "만듦  jenkins/ronanlab-infra-deploy-key"
  echo "  ▶ GitHub 등록 — Title: jenkins-write   Allow write access: 켬"
  echo "    $(cat "$T/jenkins.pub")"
fi

echo "--- Secret 안 키의 지문(공개 키에서 계산 — GitHub Deploy keys 화면의 SHA256 과 같아야 한다)"
kubectl -n argocd get secret repo-ronanlab-infra -o jsonpath='{.data.sshPrivateKey}' | base64 -d > "$T/chk1"; chmod 600 "$T/chk1"
ssh-keygen -y -f "$T/chk1" > "$T/chk1.pub"; echo "  argocd-read   $(fp "$T/chk1.pub")"
kubectl -n jenkins get secret ronanlab-infra-deploy-key -o jsonpath='{.data.ssh-privatekey}' | base64 -d > "$T/chk2"; chmod 600 "$T/chk2"
ssh-keygen -y -f "$T/chk2" > "$T/chk2.pub"; echo "  jenkins-write $(fp "$T/chk2.pub")"

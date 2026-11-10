#!/usr/bin/env bash
# ArgoCD 를 w3(infra)에 고정한다(2026-11-10 가용성 묶음 2). m-k8s 에서: bash platform/argocd/pin-infra.sh
# ArgoCD 는 install.yaml(v2.13.2)을 kubectl apply 로 깔았다 — 그 매니페스트는 이 저장소에 없다.
# install.yaml 을 다시 apply(재설치 · 업그레이드)하면 nodeSelector 가 사라진다 → 이 스크립트를 다시 돌린다. 여러 번 돌려도 같다.
# PVC 가 없어(redis 는 emptyDir) 데이터를 옮길 것은 없다. 컨트롤 플레인(m-k8s)에는 처음부터 없었다 — control-plane taint.
set -euo pipefail
P='{"spec":{"template":{"spec":{"nodeSelector":{"node.ronanlab.dev/role":"infra"}}}}}'
for d in argocd-applicationset-controller argocd-dex-server argocd-notifications-controller argocd-redis argocd-repo-server argocd-server; do
  kubectl -n argocd patch deploy "$d" -p "$P"
done
kubectl -n argocd patch sts argocd-application-controller -p "$P"
for d in argocd-applicationset-controller argocd-dex-server argocd-notifications-controller argocd-redis argocd-repo-server argocd-server; do
  kubectl -n argocd rollout status deploy "$d" --timeout=300s
done
kubectl -n argocd rollout status sts argocd-application-controller --timeout=300s
kubectl -n argocd get pods -o wide

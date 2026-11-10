#!/usr/bin/env bash
# 노드 역할 라벨(2026-11-10 가용성 묶음 2) — 배치 고정이 이 라벨을 nodeSelector · nodeAffinity 로 본다.
# 노드를 새로 만들거나 다시 join 하면 라벨이 없다 — 이 스크립트를 다시 돌린다(여러 번 돌려도 같다). m-k8s 에서:
#   bash cluster/label-nodes.sh
#
#   app       w1 · w2   앱(petmint · runshoes) + MySQL(w1 Primary, w2 Replica)
#   infra     w3        Harbor · Jenkins · ArgoCD — 죽으면 배포 · 빌드만 멈춘다
#   platform  w4        모니터링(Prometheus · Grafana · Loki) — 죽으면 모니터링만 멈춘다
set -euo pipefail
K=node.ronanlab.dev/role
kubectl label node w1-k8s "$K=app" --overwrite
kubectl label node w2-k8s "$K=app" --overwrite
kubectl label node w3-k8s "$K=infra" --overwrite
kubectl label node w4-k8s "$K=platform" --overwrite
kubectl get nodes -L "$K"

# ronanlab-infra

GPU 호스트 한 대 위 kubeadm 클러스터(m-k8s + 워커 4대)의 GitOps 저장소. ArgoCD가 `main`을 본다.

```
bootstrap/root-app.yaml   루트 Application(App of Apps) — apps/*/app.yaml 을 읽어 Application 을 만든다
apps/                     ArgoCD 가 배포하는 것 — petmint · runshoes · cloudflared · harbor-backup · monitoring
platform/                 ArgoCD 밖, 사람이 Helm/kubectl 로 넣은 기반 — cert-manager · coredns · ingress-nginx · metallb · harbor · jenkins · argocd ingress
cluster/                  VM 정의(Vagrantfile) · 노드 설치(setup-node.sh) — 호스트 ~/k8s-cluster 의 사본, 고치면 양쪽 다
scripts/                  호스트 · 배포 키 스크립트(host-nfs-harbor-backup-setup.sh 는 sudo)
docs/                     개발자 문서(00~14) · 남은 일 · 기록(history/). 노션 원고는 notion/
```

문서는 [docs/README.md](docs/README.md)부터. 비밀값은 저장소에 없다 — Secret은 각 `apps/<앱>/scripts/create-secrets.sh`가 클러스터에 직접 만든다.

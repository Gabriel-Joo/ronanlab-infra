# 클러스터와 호스트 상태 확인 기록 (2026-11-16)

문서를 새로 쓰기 전에 관리자 세션이 읽기 명령으로만 본 값이다. 코드에 남지 않는 지금 상태의 근거로 쓴다. 숫자는 이 날 본 그대로다.

## 노드

`kubectl get nodes -o wide --show-labels` 결과를 줄였다.

| 노드 | 역할 | 나이 | 판 | InternalIP(eth0) | 역할 라벨 |
| --- | --- | --- | --- | --- | --- |
| m-k8s | control-plane | 40d | v1.35.9 | 192.168.121.64 | 없음 |
| w1-k8s | 워커 | 40d | v1.35.9 | 192.168.121.179 | app |
| w2-k8s | 워커 | 40d | v1.35.9 | 192.168.121.95 | app |
| w3-k8s | 워커 | 40d | v1.35.9 | 192.168.121.158 | infra |
| w4-k8s | 워커 | 5d11h | v1.35.9 | 192.168.121.46 | platform |

다섯 대 모두 Ubuntu 22.04.3 LTS, 커널 5.15.0-91-generic, containerd 2.2.1이다. `vagrant status`로 보면 다섯 대 모두 running(libvirt)이다.

## 랜카드와 경로 (m-k8s)

- eth0: 192.168.121.64/24, DHCP. 기본 경로가 이쪽이다(`default via 192.168.121.1 dev eth0 proto dhcp`)
- eth1: 192.168.122.10/24, 고정
- 다른 노드의 파드 대역으로 가는 경로는 모두 eth1 쪽 주소(192.168.122.11~14)를 다음 홉으로 tunl0(IPIP)을 탄다
- Calico 노드 주소 주석(`projectcalico.org/IPv4Address`)은 eth1 주소다(m-k8s 192.168.122.10/24, w1 192.168.122.11/24)
- calico-node 환경: `IP=autodetect`, `CALICO_IPV4POOL_IPIP=Always`, `CALICO_IPV4POOL_VXLAN=Never`
- kubelet에 `--node-ip`가 없어 InternalIP는 eth0 주소로 잡힌다

호스트의 libvirt 망은 `default`(virbr0, 192.168.122.0/24)와 `vagrant-libvirt`(192.168.121.0/24) 둘이다.

## MetalLB

- IPAddressPool `private`: 192.168.122.240-192.168.122.250, `autoAssign: false`
- L2Advertisement `private`: `interfaces: [eth1]`
- LoadBalancer Service는 `ingress-nginx/ingress-nginx-controller` 하나다. EXTERNAL-IP 192.168.122.240, 80과 443

## Ingress와 인증서

| 네임스페이스 | Ingress | TLS Secret |
| --- | --- | --- |
| argocd | argocd-server | argocd-ingress-tls |
| harbor | harbor-ingress | harbor-tls |
| jenkins | jenkins | jenkins-tls |
| monitoring | grafana | grafana-tls |
| monitoring | prometheus | prometheus-tls |
| petmint | petmint-app | 없음 |
| runshoes | runshoes | 없음 |

Certificate 다섯 개가 모두 READY True다. ClusterIssuer는 `letsencrypt-prod`와 `letsencrypt-staging` 둘이다.

cloudflared ConfigMap의 호스트 일곱 개는 모두 `service: https://ingress-nginx-controller.ingress-nginx.svc.cluster.local:443`과 `noTLSVerify: true`를 쓴다.

## ArgoCD Application

| 이름 | Sync | Health | 자동 Sync |
| --- | --- | --- | --- |
| root | Synced | Healthy | 켜짐 |
| runshoes | Synced | Healthy | 켜짐 |
| petmint | Synced | Healthy | 켜짐 |
| monitoring | Synced | Healthy | 켜짐 |
| harbor-backup | Synced | Healthy | 켜짐 |
| cloudflared | Synced | Healthy | 꺼짐(수동) |

모두 커밋 8c4223b를 보고 있었다.

## helm 릴리스

cert-manager v1.21.2, metallb 0.16.1, harbor 1.19.2(앱 2.15.2), jenkins 5.9.68(앱 2.580.1). 저장소 밖에서 넣은 것의 판은 `platform/versions.yaml`에 옮겨 적었다.

## 실행 중인 이미지

모든 파드 이미지에 판 태그가 붙어 있고 `latest`는 없다. ingress-nginx controller는 digest까지 고정돼 있다. runshoes 앱 파드 두 개는 `0006690d4f97` 태그다. 다른 태그(`2e5e1c7909fe`, `f9ee36e01331`)는 끝난(Succeeded) CronJob 파드에만 남아 있다.

## 호스트

- OS: Ubuntu 26.04.1 LTS, 커널 7.0.0-42-generic, 32코어, 메모리 61GiB
- GPU: NVIDIA GeForce RTX 5070 Ti, 드라이버 595.99.02, 메모리 16303MiB
- 호스트 Docker 컨테이너: ollama(127.0.0.1, 172.17.0.1, 192.168.122.1의 11434), openwebui(127.0.0.1:3000), milvus-standalone과 milvus-etcd, nvidia-gpu-exporter(192.168.122.1:9835), mysql 셋(127.0.0.1에만)
- 실행 중인 서비스 중 이 문서와 닿는 것: cloudflared-ollama, model-service, petmint-search, nfs-server 계열, libvirtd, docker, tigervncserver@2, jupyter-kopo17

파드는 호스트의 Ollama(11434), model-service(8200), Milvus(19530), search(8100)를 eth1 쪽 호스트 주소 192.168.122.1로 부른다(`apps/petmint/app/configmap.yaml`, `apps/runshoes/app/deployment.yaml`).

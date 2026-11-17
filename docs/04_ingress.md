<!--
다루는 곳: platform/metallb/, platform/ingress-nginx/
읽은 커밋: 736d833
-->
# 들어오는 문

원고: → 「들어오는 문」. 바깥 길과 인증서는 `docs/05_public.md`. [code:platform/ingress-nginx/]

## 지금 구성

- ingress-nginx controller v1.11.3, 업스트림 baremetal 매니페스트를 base로, 우리 수정은 overlay로 둔다 [code:platform/ingress-nginx/base/kustomization.yaml:1-4]
- 컨트롤러 이미지는 digest까지 고정돼 있다 [code:platform/ingress-nginx/base/deploy.yaml:445]
- 컨트롤러 replicas 2, `kubernetes.io/hostname` 기준 분산(`ScheduleAnyway`, 선호) [code:platform/ingress-nginx/overlay/deployment-patch.yaml:13-28]
- 메트릭 켬(`--enable-metrics=true`), 포트 10254, Pod 어노테이션 `prometheus.io/scrape` [code:platform/ingress-nginx/overlay/deployment-patch.yaml:16-19] [code:platform/ingress-nginx/overlay/kustomization.yaml:11-18]
- Service `ingress-nginx/ingress-nginx-controller`: `LoadBalancer`, EXTERNAL-IP 192.168.122.240, 80→nodePort 30517, 443→nodePort 31925 [code:platform/ingress-nginx/overlay/service-patch.yaml:5-23] [docs:history/cluster_state_20261116.md:34]
- LoadBalancer Service는 클러스터에 이것 하나다 [docs:history/cluster_state_20261116.md:34]
- MetalLB 0.16.1(helm, 네임스페이스 `metallb-system`), L2 모드, FRR 끔 [code:platform/versions.yaml:39-43] [code:platform/metallb/values.yaml:1-8]
- IPAddressPool `private`: 192.168.122.240-192.168.122.250, `autoAssign: false` [code:platform/metallb/pool.yaml:2-10]
- L2Advertisement `private`: `interfaces: [eth1]` [code:platform/metallb/pool.yaml:13-22]
- libvirt `default` 망의 DHCP 범위는 192.168.122.100~199, 노드 eth1 고정 주소는 .10~.14. 풀은 둘과 겹치지 않는다 [code:platform/metallb/pool.yaml:1] [docs:history/build_log/02_metrics_storage_ingress.md:77]
- Ingress 7개(argocd-server, harbor-ingress, jenkins, grafana, prometheus, petmint-app, runshoes), 모두 `ingressClassName: nginx` [docs:history/cluster_state_20261116.md:38-46]
- `platform/`은 ArgoCD 밖이다. push로 바뀌지 않는다 [code:platform/ingress-nginx/overlay/kustomization.yaml:1]

문에 닿는 길은 셋이다.

| 길 | 주소 | 누가 |
| --- | --- | --- |
| ClusterIP | `ingress-nginx-controller.ingress-nginx.svc.cluster.local:443` | cloudflared, CoreDNS rewrite를 탄 클러스터 안 Pod |
| MetalLB VIP | 192.168.122.240:80/443 | 노드 containerd(`/etc/hosts`), 호스트 |
| NodePort | 노드 주소:30517/31925 | 옛 경로 유지용 |

근거: [code:platform/ingress-nginx/overlay/service-patch.yaml:1-4] [code:apps/cloudflared/configmap.yaml:2] [code:cluster/Vagrantfile:33-36] [code:platform/coredns/configmap.yaml:22-23]

## 설정 자리

| 파일:줄 | 값 | 뜻 |
| --- | --- | --- |
| `platform/metallb/values.yaml:4-8` | `speaker.frr.enabled: false`, `frrk8s.enabled: false` | BGP를 쓰지 않는다. Calico BIRD가 노드마다 179를 쓰고 있어 BGP 데몬을 하나 더 두지 않는다 [code:platform/metallb/values.yaml:2-8] |
| `platform/metallb/pool.yaml:8-9` | 192.168.122.240-250 | VIP 풀 [code:platform/metallb/pool.yaml:8-9] |
| `platform/metallb/pool.yaml:10` | `autoAssign: false` | 아무 LoadBalancer나 주소를 가져가지 않게 한다. Service가 어노테이션으로 풀과 주소를 집어 쓴다 [code:platform/metallb/pool.yaml:10] |
| `platform/metallb/pool.yaml:21-22` | `eth1` | VIP가 eth1 대역(192.168.122.0/24)에 있으니 그 랜카드로만 알린다. eth0은 vagrant-libvirt 관리망(192.168.121.x, DHCP) [code:platform/metallb/pool.yaml:12] [docs:history/human_answers_20261116.md:7] [docs:history/human_answers_20261116.md:13] |
| `platform/ingress-nginx/overlay/service-patch.yaml:10-12` | `metallb.io/address-pool: private`, `metallb.io/loadBalancerIPs: 192.168.122.240` | 풀 이름과 VIP를 집는다 [code:platform/ingress-nginx/overlay/service-patch.yaml:10-12] |
| `platform/ingress-nginx/overlay/service-patch.yaml:15-23` | nodePort 30517/31925, `protocol: TCP` | nodePort 고정. `protocol`을 빼면 병합 키(port+protocol)가 어긋나 nodePort가 사라진다 [code:platform/ingress-nginx/overlay/service-patch.yaml:2-3] |
| `platform/ingress-nginx/overlay/deployment-patch.yaml:13` | `replicas: 2` | 입구가 하나면 재시작 때 끊긴다 [code:platform/ingress-nginx/overlay/deployment-patch.yaml:2-3] |
| `platform/ingress-nginx/overlay/kustomization.yaml:11-18` | args index 8 `test` 후 `replace` | 업스트림 인자 순서가 바뀌면 `test`가 실패해 apply가 멈춘다 [code:platform/ingress-nginx/overlay/kustomization.yaml:10] |
| `platform/ingress-nginx/base/deploy.yaml` | 업스트림 원본 | 손대지 않는다 [code:platform/ingress-nginx/base/kustomization.yaml:1] |

NodePort 대신 MetalLB를 넣은 까닭: Harbor 토큰 주소(`externalURL` + `/service/token`)에 포트가 없어 노드 containerd가 443으로 간다. NodePort로는 닿지 않고, 공개 주소로 나가면 Cloudflare Access에 막힌다 [docs:history/build_log/02_metrics_storage_ingress.md:191-197].

## 바꾸거나 다시 만들기

m-k8s에서(`cd ~/k8s-cluster && vagrant ssh m-k8s -c '…'`). 저장소는 m-k8s에 없으니 해당 폴더를 옮겨 놓고 친다. [docs:history/build_log/02_metrics_storage_ingress.md:389-391]

```bash
# MetalLB(먼저 호스트에서 libvirt DHCP 범위를 .100~.199로 둔다)
helm repo add metallb https://metallb.github.io/metallb && helm repo update
helm install metallb metallb/metallb --version 0.16.1 -n metallb-system --create-namespace -f platform/metallb/values.yaml
kubectl apply -f platform/metallb/pool.yaml        # 컨트롤러 webhook이 Ready가 된 뒤

# ingress-nginx: 늘 overlay. base만 apply하면 Service가 NodePort로 돌아가고 nodePort가 새로 뽑힌다
kubectl diff -k platform/ingress-nginx/overlay
kubectl apply -k platform/ingress-nginx/overlay
```

근거: [docs:history/build_log/02_metrics_storage_ingress.md:138-144] [code:platform/ingress-nginx/overlay/kustomization.yaml:1-2]

ingress-nginx 판을 올릴 때: base의 `deploy.yaml`을 새 태그 원본으로 바꾸고 `kustomization.yaml`의 출처와 sha256을 고친 뒤 `kubectl diff -k`로 본다. 인자 순서가 바뀌었으면 overlay의 index 8 패치를 고친다 [code:platform/ingress-nginx/base/kustomization.yaml:2-4] [code:platform/ingress-nginx/overlay/kustomization.yaml:10].

MetalLB 판을 올리면 `platform/versions.yaml`도 같은 커밋에서 고친다 [code:platform/versions.yaml:6].

ingress-nginx 재시작(`rollout restart`)은 모든 공개 주소와 사설 VIP 경로를 거친다. 하기 전에 알린다.

## 확인

```bash
kubectl -n ingress-nginx get svc ingress-nginx-controller
# LoadBalancer  192.168.122.240  80:30517/TCP,443:31925/TCP
kubectl -n ingress-nginx get pods -o wide
# controller 2개, 서로 다른 노드
kubectl get ipaddresspool,l2advertisement -n metallb-system
# private, AUTO ASSIGN false, 192.168.122.240-192.168.122.250, INTERFACES ["eth1"]
kubectl get svc -A --field-selector spec.type=LoadBalancer
# ingress-nginx-controller 한 줄
helm -n metallb-system list
# metallb 0.16.1
```

호스트에서:

```bash
curl -sk -o /dev/null -w '%{http_code}\n' --resolve harbor.ronanlab.dev:443:192.168.122.240 https://harbor.ronanlab.dev/api/v2.0/ping   # 200
```

근거: [docs:history/build_log/02_metrics_storage_ingress.md:389-430] [docs:history/cluster_state_20261116.md:30-34]

## 알려진 한계

- L2 모드는 VIP를 노드 한 대가 알린다. 그 노드가 죽으면 다른 speaker가 넘겨받을 때까지 VIP가 끊긴다 [docs:history/build_log/02_metrics_storage_ingress.md:385]
- 컨트롤러 2개여도 롤링 재시작 때 짧은 끊김이 있었다 [docs:history/build_log/02_metrics_storage_ingress.md:384]
- MetalLB, ingress-nginx는 ArgoCD 밖이라 저장소와 클러스터가 어긋나도 알림이 없다. `kubectl diff`로 손수 본다 [code:platform/ingress-nginx/overlay/kustomization.yaml:1]

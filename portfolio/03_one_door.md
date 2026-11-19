<!--
다루는 곳: platform/metallb/, platform/ingress-nginx/
읽은 커밋: ddbaadf
-->
# 문은 하나만: MetalLB와 ingress-nginx

> 이 글은 클러스터로 들어오는 요청이 지나는 문을 하나로 정하고, 그 문에 사설망 주소를 붙인 결정을 다룹니다.

**앱과 운영 도구 일곱 곳이 모두 ingress-nginx라는 문 하나로 들어오고, 그 문에만 사설망 고정 주소를 하나 붙였습니다. 주소를 나눠 주는 MetalLB는 아무 서비스에나 주소를 주지 않도록 막아 두었습니다.**

## 상황

쿠버네티스 위에 서비스를 올리면 바깥에서 그 서비스에 닿을 길이 있어야 합니다. 이 클러스터에는 공개 앱 둘(petmint, runshoes)과 운영 도구 다섯(ArgoCD, Harbor, Jenkins, Grafana, Prometheus)이 있고, 모두 바깥이나 사설망에서 열어 봐야 하는 화면입니다 [docs:history/cluster_state_20261116.md:36-46].

클라우드에서는 서비스 종류를 LoadBalancer(클러스터 바깥에서 닿는 고정 주소를 받는 서비스 종류)로 적기만 하면 클라우드 회사가 부하 분산 장치와 주소를 붙여 줍니다. 이 클러스터는 사무실 서버 위의 VM이라 그렇게 빌려 올 장치가 없습니다. 그래서 처음에는 직접 세운 서버용 설치 파일을 써서, 노드마다 높은 번호의 포트로 문을 여는 방식(NodePort)으로 지냈습니다 [docs:history/build_log/02_metrics_storage_ingress.md:185-187].

이 방식이 막힌 곳은 노드가 사설 이미지 저장소 Harbor에서 이미지를 받을 때였습니다. Harbor는 로그인용 주소를 포트 없이 알려 주기 때문에 노드는 HTTPS 기본 포트로 찾아가는데, 높은 번호의 포트로 열린 문에는 닿지 않았습니다. 공개 주소로 돌아 나가면 Cloudflare의 로그인 관문에 막혔습니다 [docs:history/build_log/02_metrics_storage_ingress.md:191].

## 고른 것

문은 하나만 둡니다. ingress-nginx는 Ingress(호스트 이름과 경로에 따라 요청을 어느 서비스로 보낼지 적은 규칙)를 읽어 실제로 요청을 나눠 주는 프로그램입니다. 앱마다 따로 문을 열지 않고, 모든 요청을 이 프로그램이 받아 호스트 이름을 보고 알맞은 서비스로 넘깁니다. 지금 이 문에 걸린 Ingress가 일곱 개입니다 [docs:history/cluster_state_20261116.md:36-46].

그 문에 사설망 주소를 붙이는 일은 MetalLB에게 맡겼습니다. MetalLB는 클라우드의 부하 분산 장치가 하던 일, 곧 LoadBalancer 서비스에 주소를 붙여 주는 일을 사설망 안에서 대신하는 프로그램입니다. 이 주소를 VIP(특정 기계에 묶이지 않고 여러 노드 가운데 하나가 맡아 받는 주소)라고 부릅니다. 지금 클러스터에서 LoadBalancer 서비스는 ingress-nginx 하나뿐이고, 받은 주소는 노드들이 쓰는 사설 고정 대역 안의 주소 하나입니다 [docs:history/cluster_state_20261116.md:30-34].

MetalLB에는 세 가지 제한을 걸었습니다.

첫째, 주소 묶음에서 자동 배정을 껐습니다. 켜 두면 누군가 LoadBalancer 서비스를 하나 만들기만 해도 묶음에서 주소를 가져갑니다. 꺼 두면 서비스 쪽에서 묶음 이름과 원하는 주소를 직접 적어야만 주소를 받습니다. ingress-nginx는 자기 설정에 그 이름과 주소를 적어 집어 갑니다 [code:platform/metallb/pool.yaml:10] [code:platform/ingress-nginx/overlay/service-patch.yaml:10-12].

둘째, 주소를 알리는 랜카드를 eth1 하나로 고정했습니다. MetalLB는 L2 방식(노드 한 대가 같은 망 안에 「이 주소는 나에게 있다」고 알리는 방식)으로 동작합니다. 노드마다 랜카드가 둘인데, eth0은 VM 관리 도구가 붙이는 관리망이고 eth1이 클러스터용 사설 고정망입니다 [code:platform/metallb/pool.yaml:12-22]. 랜카드를 둘로 나눈 까닭은 → 「랜카드 둘: 관리망과 고정망」에서 다룹니다.

셋째, BGP용 부품을 껐습니다. MetalLB에는 L2 말고 BGP(라우터끼리 길을 주고받는 규약) 방식도 있고, 쓰는 판에서는 BGP용 부품(FRR)이 기본으로 켜져 옵니다. 이 클러스터는 BGP를 쓰지 않으므로 그 부품을 모두 껐습니다 [code:platform/metallb/values.yaml:1-8].

## 까닭

문을 하나로 둔 것은 새 앱을 내놓을 때 문을 새로 만들지 않고 Ingress 하나만 더하면 되게 하려는 것입니다. 바깥에서 오는 터널도 앱 하나하나가 아니라 이 문 하나만 가리키면 됩니다 [docs:history/build_log/03_cloudflare_tunnel.md:143-153].

MetalLB를 고르기 전에 다른 길도 따져 봤습니다. 노드마다 표준 포트를 높은 번호로 넘겨 주는 장치를 두면 인증서 확인을 건너뛰어야 하고, 설정이 노드 OS에 흩어져 저장소 밖에 남습니다. Harbor가 알려 주는 주소를 내부 주소로 바꾸면 웹 화면과 바깥 로그인까지 내부 주소를 가리키게 됩니다. MetalLB는 프로그램이 하나 늘지만, 사설망 안의 누구나 표준 포트로 문에 닿고 설정이 매니페스트로 남습니다 [docs:history/build_log/02_metrics_storage_ingress.md:193-197].

자동 배정을 끈 까닭은 설정 파일의 주석에 적혀 있습니다. 아무 LoadBalancer나 주소를 가져가지 않게 하고, 서비스가 이름으로 집어 쓰게 하려는 것입니다 [code:platform/metallb/pool.yaml:10]. 묶음은 VM 관리 도구가 자동으로 나눠 주는 구간과 노드 고정 주소를 피해 잡은 작은 구간이라, 어느 서비스가 어느 주소를 쓰는지 사람이 정해 두는 편을 택했습니다 [code:platform/metallb/pool.yaml:1].

eth1로만 알리는 까닭은 VIP가 고정 주소 대역에 있기 때문입니다. 그 대역이 붙은 랜카드로만 알려야 같은 망의 기계들이 그 주소를 찾아올 수 있습니다 [docs:history/human_answers_20261116.md:13].

BGP 부품을 끈 까닭은 파드 망을 맡는 Calico가 이미 노드마다 BGP 프로그램(BIRD)을 띄우고 있어서입니다. 같은 일을 하는 프로그램을 하나 더 두지 않았습니다 [code:platform/metallb/values.yaml:2-3].

## 치른 값

- 모든 요청이 한 문을 지나므로 ingress-nginx가 멈추면 모든 서비스가 같이 멈춥니다. 그래서 컨트롤러를 두 벌 띄우고 서로 다른 노드에 뜨도록 했습니다. 다만 강제가 아니라 선호로 두어, 노드가 모자라면 한 노드에 둘이 같이 뜰 수 있습니다 [code:platform/ingress-nginx/overlay/deployment-patch.yaml:1-2] [code:platform/ingress-nginx/overlay/deployment-patch.yaml:21-24]
- L2 방식에서는 VIP를 노드 한 대가 맡아 알립니다. 그 노드가 죽으면 다른 노드가 넘겨받을 때까지 VIP로 가는 요청이 잠깐 끊깁니다 [docs:history/build_log/02_metrics_storage_ingress.md:385]
- MetalLB와 ingress-nginx가 GitOps 밖에 있어 사람이 손으로 넣는 것은 여러 결정에 걸려 → 「알려진 한계」에 모았습니다
- 예전 노드 쪽 높은 번호 포트 길도 끊지 않으려고 그 번호를 그대로 고정해 두었습니다. 문에 닿는 길이 하나 더 남아 있는 셈입니다 [code:platform/ingress-nginx/overlay/service-patch.yaml:2]

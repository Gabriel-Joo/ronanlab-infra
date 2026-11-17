<!--
다루는 곳: platform/metallb/, platform/ingress-nginx/
읽은 커밋: e8e24ea
-->
# 04 들어오는 문

클러스터 안에서 도는 앱과 운영 도구는 모두 한 곳을 거쳐 들어온다. 그 문이 ingress-nginx다. ingress-nginx는 Ingress(바깥 요청을 주소와 경로에 따라 알맞은 서비스로 나눠 주는 규칙)를 읽어 실제로 요청을 나눠 주는 프로그램이고, 이런 프로그램을 Ingress 컨트롤러라고 부른다. 이 편은 그 문이 어떻게 서 있는지, 그리고 문에 붙은 주소를 누가 어떻게 알리는지를 다룬다. 문 앞까지 오는 바깥 길과 인증서는 → 「바깥 공개와 인증서」에서 다룬다.

## 문은 하나다

앱마다 따로 문을 열지 않고 ingress-nginx 하나가 모든 요청을 받는다. 요청이 들어오면 ingress-nginx는 요청에 실린 호스트 이름(브라우저가 어느 주소로 왔는지 적어 보내는 값)과 경로를 보고, 그 이름을 가진 Ingress가 가리키는 서비스로 넘긴다. 그래서 새 앱을 내놓을 때는 문을 새로 만들지 않고 Ingress 하나만 더하면 된다. 지금 Ingress는 일곱 개이고, 운영 도구 다섯(ArgoCD, Harbor, Jenkins, Grafana, Prometheus)과 공개 앱 둘(petmint, runshoes)이다. [docs:history/cluster_state_20261116.md:36-46]

모든 요청이 지나가는 자리라 ingress-nginx가 멈추면 모든 서비스가 같이 멈춘다. 그래서 컨트롤러를 두 벌 띄우고, 두 벌이 되도록 서로 다른 노드에 뜨게 했다. 하나가 죽어도 다른 하나가 받는다. 노드를 나누는 규칙은 강제가 아니라 선호로 두었다. 노드가 모자라면 한 노드에 둘이 같이 뜨더라도 둘 다 뜨는 편이 낫기 때문이다. [code:platform/ingress-nginx/overlay/deployment-patch.yaml:1-2] [code:platform/ingress-nginx/overlay/deployment-patch.yaml:13-28]

ingress-nginx는 지표도 내놓는다. 앱들이 자기 요청 수를 따로 내놓지 않아서, 호스트별 요청 수, 응답 상태, 지연 시간을 이 문에서 얻는다. 업스트림 원본은 지표를 꺼 둔 채로 오기 때문에 우리 쪽에서 켰다. 모으는 쪽은 → 「모니터링」에서 다룬다. [code:platform/ingress-nginx/overlay/deployment-patch.yaml:4-5] [code:platform/ingress-nginx/base/deploy.yaml:433]

## 업스트림 원본과 우리 손을 나눈다

ingress-nginx는 프로젝트가 내놓은 설치 파일 하나로 깐다. 그 파일을 `platform/ingress-nginx/base`에 손대지 않고 그대로 두었고, 우리가 바꾼 것은 `overlay`에만 얹었다. 이렇게 나누면 판을 올릴 때 원본 파일만 새 판으로 갈아 끼우고, 바뀐 차이를 따로 볼 수 있다. 원본과 우리 수정이 한 파일에 섞여 있으면 판을 올릴 때마다 무엇이 우리 손인지 다시 찾아야 한다. [code:platform/ingress-nginx/base/kustomization.yaml:1-4] [docs:history/build_log/02_metrics_storage_ingress.md:211-213]

설치 파일은 클라우드용과 직접 세운 서버용(baremetal)이 따로 있다. 클라우드용은 클라우드 회사의 부하 분산 장치를 자동으로 빌려 오는데, 이 클러스터는 사무실 서버 위의 VM이라 빌려 올 장치가 없다. 그래서 직접 세운 서버용 원본을 썼다. 이 원본은 문을 노드마다 높은 번호의 포트로 여는 방식(NodePort)으로 온다. [docs:history/build_log/02_metrics_storage_ingress.md:185-187] [code:platform/ingress-nginx/base/deploy.yaml:366]

overlay가 바꾸는 것은 셋이다. 문의 종류를 LoadBalancer(클러스터 바깥에서 닿는 고정 주소를 받는 문)로 바꾸고, 컨트롤러를 두 벌로 늘려 노드에 나누고, 지표를 켠다. 지표를 켜는 수정은 원본의 인자 목록에서 한 자리를 바꾸는데, 바꾸기 전에 그 자리에 예상한 값이 있는지 먼저 확인하게 했다. 원본 판이 올라 인자 순서가 바뀌면 확인이 실패해 적용 자체가 멈춘다. 엉뚱한 인자를 덮어쓰는 것보다 멈추는 편이 안전하다. [code:platform/ingress-nginx/overlay/kustomization.yaml:5-18]

이 때문에 클러스터에 적용하는 것은 늘 overlay다. 원본만 적용하면 문이 다시 NodePort로 돌아가고 노드 쪽 포트 번호도 새로 뽑혀, 그 번호로 붙던 길이 끊긴다. 지금 노드 쪽 포트 번호는 예전 번호 그대로 고정해 두었다. [code:platform/ingress-nginx/overlay/kustomization.yaml:1-2] [code:platform/ingress-nginx/overlay/service-patch.yaml:2]

## 고정 주소를 붙인 까닭

처음에는 NodePort만으로 지냈다. 막힌 것은 노드가 사설 이미지 저장소(Harbor)에서 이미지를 받을 때였다. Harbor는 로그인용 주소를 포트 없이 알려 주기 때문에 노드는 HTTPS 기본 포트로 찾아간다. 높은 번호의 포트로 열린 문에는 닿지 않는다. 공개 주소로 돌아 나가면 Cloudflare의 로그인 관문에 막힌다. [docs:history/build_log/02_metrics_storage_ingress.md:191]

다른 길도 따져 봤다. 노드마다 표준 포트를 높은 번호로 넘겨 주는 장치를 두면 인증서 확인을 꺼야 하고, 설정이 노드 OS에 흩어져 저장소 밖에 남는다. Harbor가 알려 주는 주소를 내부 주소로 바꾸면 웹 화면과 바깥 로그인까지 내부 주소를 가리키게 된다. 그래서 클라우드의 부하 분산 장치가 하던 일을 사설망 안에서 대신해 주는 MetalLB를 넣었다. 프로그램이 하나 늘지만, 사설망 안의 누구나 표준 포트로 문에 닿고 설정이 매니페스트로 남는다. [docs:history/build_log/02_metrics_storage_ingress.md:193-197]

## MetalLB가 주소를 나눠 주는 방식

MetalLB는 미리 정해 둔 주소 묶음(풀)에서 주소를 하나 꺼내 LoadBalancer 문에 붙인다. 풀은 노드들이 쓰는 사설 고정 대역 안의 작은 구간이고, VM 관리 도구가 자동으로 나눠 주는 구간과 노드 고정 주소를 피해서 잡았다. 지금 이 풀에서 주소를 받은 것은 ingress-nginx 하나뿐이고, 받은 주소는 사설 고정 대역의 주소 하나다. 아래에서는 이 주소를 사설 VIP라고 부른다. [code:platform/metallb/pool.yaml:1-9] [docs:history/cluster_state_20261116.md:30-34]

풀에는 자동 배정을 꺼 두었다. 켜 두면 누군가 LoadBalancer 문을 하나 만들기만 해도 풀에서 주소를 가져간다. 꺼 두면 문 쪽에서 풀 이름과 원하는 주소를 직접 적어야만 주소를 받는다. ingress-nginx 문은 overlay에서 풀 이름과 주소를 적어 집어 간다. 주소가 몇 개 없는 풀이라, 실수로 만든 문이 주소를 차지하거나 ingress-nginx의 주소가 바뀌는 일을 막으려는 것이다. [code:platform/metallb/pool.yaml:10] [code:platform/ingress-nginx/overlay/service-patch.yaml:10-12]

MetalLB는 L2 방식으로 동작한다. 노드 한 대가 「이 주소는 나에게 있다」고 같은 망에 알리고, 그 주소로 오는 요청을 받아 ingress-nginx로 넘긴다. 알리는 랜카드는 eth1 하나로 고정했다. 노드마다 랜카드가 둘인데, eth0은 VM 관리 도구가 붙이는 관리용 망이고 eth1이 클러스터용 사설 고정 망이다. 관리용 망은 주소를 그때그때 나눠 받는 망이라 노드끼리의 통신에 쓰지 않는다. 사설 VIP는 고정 망 대역에 있으니 그 대역이 붙은 랜카드로만 알려야 한다. [code:platform/metallb/pool.yaml:12-22] [docs:history/human_answers_20261116.md:7-9] [docs:history/human_answers_20261116.md:13]

MetalLB에는 L2 말고 BGP(라우터끼리 길을 주고받는 규약) 방식도 있고, 판에 따라 BGP용 부품(FRR)이 기본으로 켜져 온다. 우리는 BGP를 쓰지 않으니 그 부품을 모두 껐다. 파드 망을 맡는 Calico가 이미 노드마다 BGP 프로그램(BIRD)을 띄우고 있어서, 같은 일을 하는 프로그램을 하나 더 두면 서로 겹친다. [code:platform/metallb/values.yaml:1-8]

## 문에 닿는 세 길

정리하면 ingress-nginx 문에는 세 길로 닿는다. 클러스터 안의 프로그램은 클러스터 내부 주소로 바로 문에 닿는다. Cloudflare 터널을 받는 cloudflared가 이 길을 쓴다. 사설망에 있는 호스트와 노드는 사설 VIP로 표준 포트를 써서 닿는다. 그리고 예전부터 쓰던 노드 쪽 높은 번호 포트도 열어 두었다. 세 길 모두 같은 ingress-nginx, 같은 Ingress 규칙에 닿는다. 어느 길로 무엇이 들어오는지는 → 「공개 경로와 내부 경로」에서 다룬다. [code:platform/ingress-nginx/overlay/service-patch.yaml:1-4] [code:platform/ingress-nginx/overlay/service-patch.yaml:14-23]

`platform/` 아래 것은 GitOps 밖이다. 저장소에 올려도 클러스터는 바뀌지 않고, 사람이 helm과 kubectl로 직접 넣는다. MetalLB와 ingress-nginx의 판은 버전 기록 파일과 원본 파일 머리에 적혀 있다. [code:platform/versions.yaml:39-43] [code:platform/ingress-nginx/base/kustomization.yaml:1]

## 알려진 한계

- L2 방식에서는 사설 VIP를 노드 한 대가 맡아 알린다. 그 노드가 죽으면 다른 노드가 넘겨받을 때까지 사설 VIP로 가는 요청이 잠깐 끊긴다 [docs:history/build_log/02_metrics_storage_ingress.md:385]
- 컨트롤러가 두 벌이어도 재시작할 때 아주 짧게 끊길 수 있다 [docs:history/build_log/02_metrics_storage_ingress.md:384]
- 원본 판을 올리면 지표를 켜는 수정이 인자 자리를 다시 맞춰야 한다. 맞지 않으면 적용이 멈춘다(의도한 멈춤이다) [code:platform/ingress-nginx/overlay/kustomization.yaml:10]
- MetalLB와 ingress-nginx는 저장소에 올려도 들어가지 않는다. 바꾼 사람이 직접 넣어야 하고, 넣지 않으면 저장소와 클러스터가 어긋난다 [code:platform/ingress-nginx/overlay/kustomization.yaml:1]

## 용어 풀이

- Ingress: 호스트 이름과 경로에 따라 요청을 어느 서비스로 보낼지 적은 규칙
- Ingress 컨트롤러: Ingress를 읽어 실제로 요청을 나눠 주는 프로그램. 여기서는 ingress-nginx
- NodePort: 모든 노드에서 높은 번호의 포트 하나로 서비스를 여는 방식
- LoadBalancer: 클러스터 바깥에서 닿는 고정 주소를 받는 서비스 종류. 클라우드에서는 클라우드가, 여기서는 MetalLB가 주소를 준다
- VIP: 특정 기계에 묶이지 않고 여러 노드 중 하나가 맡아 받는 주소
- L2 광고: 같은 망 안에 「이 주소는 이 랜카드에 있다」고 알리는 것 [code:platform/metallb/pool.yaml:13-22]
- overlay: 업스트림 원본 위에 얹는 우리 쪽 수정 묶음

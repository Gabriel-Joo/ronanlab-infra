<!--
다루는 곳: apps/cloudflared/
읽은 커밋: 736d833
-->
# 05-01 공개 경로와 내부 경로

요청이 ingress-nginx 문에 닿는 길은 크게 둘이다. 바깥 인터넷에서 오는 요청은 Cloudflare 터널을 거쳐 들어오고, 사설망 안의 호스트와 노드는 터널을 거치지 않고 사설 VIP로 곧장 문에 닿는다. 두 길은 같은 문, 같은 Ingress 규칙에 닿지만 거치는 관문이 다르다. 이 편은 두 길을 차례로 따라가고, 왜 이렇게 나눴는지를 적는다.

## 바깥에서 오는 길

바깥 사용자가 공개 주소를 열면 요청은 먼저 Cloudflare 엣지(Cloudflare가 세계 곳곳에 둔 서버)에 닿는다. 엣지는 그 주소가 어느 터널에 묶여 있는지 보고, 터널을 따라 클러스터 안의 cloudflared에게 요청을 넘긴다. cloudflared는 받은 요청을 ingress-nginx의 클러스터 내부 주소로 보내고, ingress-nginx가 호스트 이름을 보고 알맞은 앱으로 넘긴다. [code:apps/cloudflared/configmap.yaml:1-2] [code:apps/cloudflared/configmap.yaml:13-17]

터널은 방향이 거꾸로다. 서버 쪽 cloudflared가 Cloudflare로 나가는 연결을 먼저 맺어 두고, 바깥 요청은 그 연결을 거꾸로 타고 들어온다. 공유기에 구멍을 뚫어 바깥 요청을 서버로 넘기는 흔한 방식(포트포워딩)은 회선 주소가 바뀌면 끊기고, 열어 둔 구멍으로 누구나 들어오려 할 수 있다. 터널은 서비스용으로 들어오는 포트를 하나도 열지 않아 이 문제가 없다. [docs:history/build_log/03_cloudflare_tunnel.md:79-89] 이 사무실의 공유기 포트포워딩은 관리용 SSH 하나에만 쓰고, 웹 서비스에는 쓰지 않는다. [docs:history/notion_hardware_20261116.md:11]

cloudflared는 서버 호스트의 프로세스가 아니라 클러스터 안의 파드로 띄웠다. 파드로 두면 죽었을 때 쿠버네티스가 다시 띄우고, 두 벌로 늘리는 것도 설정 한 줄이며, 설정이 저장소에 남는다. 지금 cloudflared는 cloudflared 네임스페이스에 두 벌이 떠 있고 둘 다 같은 터널에 붙는다. 하나가 죽어도 다른 하나가 받는다. [docs:history/build_log/03_cloudflare_tunnel.md:129-139] [code:apps/cloudflared/deployment.yaml:1] [code:apps/cloudflared/deployment.yaml:13]

터널이 앱을 하나하나 가리키지 않고 ingress-nginx 하나만 가리키게 한 것도 일부러 고른 것이다. 터널 설정의 공개 주소 일곱 개는 모두 같은 목적지, ingress-nginx로 간다. 어느 앱으로 갈지는 ingress-nginx가 호스트 이름을 보고 고른다. 앱이 바뀌거나 늘어도 길을 나누는 일은 Ingress가 맡고, 터널은 손댈 것이 적다. 다만 이 터널은 설정 파일 방식이라 새 공개 주소를 더할 때는 터널 설정에 주소 한 줄을 더하고, Cloudflare 쪽에서 그 이름을 터널에 잇는 DNS 기록도 사람이 따로 만든다. 설정에 없는 주소로 온 요청은 마지막 규칙에서 「없음」으로 돌려보낸다. [code:apps/cloudflared/configmap.yaml:13-44] [docs:history/build_log/03_cloudflare_tunnel.md:143-153] [code:apps/cloudflared/README.md:46]

## 터널 앞의 관문

터널은 길을 암호화해서 이어 줄 뿐, 누가 들어와도 되는지는 따지지 않는다. 그래서 운영 도구 앞에는 Cloudflare Access라는 로그인 관문을 둔다. ArgoCD, Harbor, Jenkins, Grafana, Prometheus는 「운영도구」라는 하나의 Access 앱으로 묶여 있어, 허락된 사람이 로그인해야 터널 안으로 들어온다. [docs:history/build_log/03_cloudflare_tunnel.md:175] [code:apps/monitoring/ingress.yaml:2-3] [code:apps/cloudflared/configmap.yaml:35]

도구마다 관문의 무게가 다르다. Prometheus는 자체 로그인이 없어서 바깥에서는 Access가 유일한 문이다. 그래서 Access를 먼저 걸고 나서 공개 주소를 열었다. Grafana는 자체 로그인과 Access가 두 겹으로 지킨다. Jenkins는 GitHub가 보내는 알림을 받는 경로 하나만 Access를 비켜 두었고, 그 경로는 GitHub와 나눠 가진 비밀로 만든 서명이 맞는지로 지킨다. [code:apps/monitoring/ingress.yaml:5-7] [code:platform/jenkins/values.yaml:92-93]

공개 앱 runshoes에는 Access가 없다. 누구나 보는 사이트이기 때문이다. Access 설정은 저장소가 아니라 Cloudflare 대시보드에서 사람이 하므로, 어느 주소에 어떤 관문이 걸려 있는지는 저장소의 주석으로만 알 수 있다. [code:apps/cloudflared/configmap.yaml:30] [code:apps/monitoring/ingress.yaml:3]

## 사설망 안의 길

사설망은 서버 호스트와 그 위의 VM들만 있는 망이다. 이 안에서는 터널을 거치지 않고 사설 VIP로 ingress-nginx 문에 바로 닿는다. 닿는 곳은 바깥 길과 같은 Ingress이고, 같은 호스트 이름을 쓴다. 다른 점은 Cloudflare를 거치지 않으니 Access 관문도 없다는 것이다. [code:apps/monitoring/ingress.yaml:4-6] [code:platform/ingress-nginx/overlay/service-patch.yaml:1]

이 길이 꼭 있어야 하는 곳이 노드다. 노드의 containerd(파드의 이미지를 받아 와 돌리는 프로그램)는 사설 이미지 저장소 Harbor에서 이미지를 받는다. Harbor의 공개 이름을 Cloudflare로 풀면 Access 관문에 막히니, 노드마다 그 이름을 사설 VIP로 풀도록 고정해 두었다. 그래서 노드는 공개 주소와 같은 이름으로, 같은 인증서를 확인하면서 사설 VIP를 통해 Harbor에 닿는다. 클러스터 안의 파드가 Harbor를 부를 때는 클러스터 DNS가 같은 이름을 ingress-nginx의 내부 주소로 바꿔 준다. 노드 쪽 설정은 → 「VM 다섯 대와 랜카드 둘」, 클러스터 DNS 쪽은 → 「쿠버네티스 설치와 파드 망」에서 다룬다. [code:cluster/Vagrantfile:33-36] [code:platform/harbor/values.yaml:4] [code:platform/coredns/configmap.yaml:1-7]

이 길은 터널이 깨졌을 때 숨구멍이 되기도 한다. 터널이 멈추면 바깥에서는 ArgoCD 화면도 Grafana 화면도 보이지 않는다. 그때도 서버 호스트에서는 사설 VIP로 운영 도구 화면을 열 수 있고, m-k8s에 들어가 kubectl로 고칠 수 있다. [code:apps/cloudflared/README.md:24-25]

## 터널 설정을 바꿀 때

터널 설정은 저장소의 `apps/cloudflared`에 있고 ArgoCD가 클러스터에 넣는다. 그런데 다른 앱과 달리 이 앱은 자동 반영을 꺼 두었다. 저장소에 올라간 커밋이 곧바로 클러스터에 들어가지 않고, 사람이 ArgoCD에서 반영을 누르고 바뀌는 과정을 지켜본다. 이 터널이 깨지면 공개 주소 일곱 개가 한꺼번에 사라지고, 고칠 도구(ArgoCD 화면)와 볼 도구(Grafana)도 같이 사라진다. 그 상태에서는 m-k8s의 kubectl로만 되돌릴 수 있다. 잘못된 커밋 하나가 사람 손을 거치지 않고 이 상태를 만들게 두지 않으려는 것이다. [code:apps/cloudflared/app.yaml:4-8] [code:apps/cloudflared/README.md:21-23] [docs:history/cluster_state_20261116.md:61]

같은 까닭으로 이 앱은 저장소에서 지운 것을 클러스터에서 같이 지우지 않고, ArgoCD 쪽 앱을 지워도 터널 파드는 남는다. 네임스페이스와 터널 자격 증명은 사람이 직접 만든다. 자격 증명을 저장소에 평문으로 둘 수 없어서다. [code:apps/cloudflared/app.yaml:9-11] [code:apps/cloudflared/kustomization.yaml:6]

반영을 눌러도 끝이 아니다. cloudflared는 설정 파일을 켜질 때 한 번만 읽는다. 반영하면 설정 파일만 바뀌고, 떠 있는 cloudflared는 옛 설정으로 계속 돈다. 그래서 반영한 뒤 cloudflared를 차례로 다시 띄우는(rollout restart) 단계까지 해야 새 설정이 들어간다. [code:apps/cloudflared/configmap.yaml:3] [code:apps/cloudflared/README.md:43-44]

다시 띄우는 과정은 끊기지 않게 짜여 있다. 새 cloudflared가 Cloudflare와 연결을 하나라도 맺어 준비가 되어야 옛 것을 하나 내린다. 새 설정이 깨져 있으면 새 것이 끝내 준비되지 않고 교체가 거기서 멈추며, 옛 두 벌이 계속 요청을 받는다. 그 사이 커밋을 되돌리고 다시 반영하면 된다. [code:apps/cloudflared/deployment.yaml:2-4] [code:apps/cloudflared/README.md:45]

## 알려진 한계

- 터널 하나에 공개 주소 일곱 개가 몰려 있다. 터널이 깨지면 공개 앱과 운영 도구가 한꺼번에 보이지 않는다 [code:apps/cloudflared/app.yaml:5-6]
- Cloudflare 쪽 DNS 기록과 Access 정책은 저장소에 없다. 대시보드에서 정책이 빠져도 저장소만으로는 알 수 없다 [docs:history/build_log/03_cloudflare_tunnel.md:699]
- 설정을 바꾸고 반영만 한 채 다시 띄우기를 빠뜨리면 새 설정이 들어가지 않는다 [code:apps/cloudflared/configmap.yaml:3]
- 사설망 안에서는 Access 없이 운영 도구에 닿는다. 자체 로그인이 없는 Prometheus도 사설망에서는 그대로 열린다 [code:apps/monitoring/ingress.yaml:5-6]

## 용어 풀이

- Cloudflare 엣지: Cloudflare가 세계 곳곳에 둔 서버. 공개 주소로 온 요청을 처음 받는다
- 터널: 서버 안쪽에서 Cloudflare로 먼저 맺어 둔 연결. 바깥 요청이 이 연결을 거꾸로 타고 들어온다
- cloudflared: 터널의 서버 쪽 끝을 맡는 프로그램
- Cloudflare Access: 공개 주소 앞에 세우는 로그인 관문
- 사설 VIP: MetalLB가 ingress-nginx에 붙인 사설 고정 대역의 주소
- rollout restart: 파드를 한 벌씩 새로 띄워 바꾸는 명령

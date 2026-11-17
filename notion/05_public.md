<!--
다루는 곳: apps/cloudflared/, platform/cert-manager/
읽은 커밋: 6290346
-->
# 05 바깥 공개와 인증서

클러스터는 사무실 서버 위의 VM 안에 있다. 바깥 인터넷에서 이 안으로 들어오는 포트는 하나도 열지 않았다. 대신 클러스터 안에서 도는 cloudflared가 Cloudflare 쪽으로 먼저 연결을 맺고, 바깥 요청은 Cloudflare가 그 연결을 거꾸로 타고 들여보낸다. 이것을 Cloudflare 터널이라고 부른다. 터널 하나가 공개 주소 일곱 개를 모두 받고, 받은 요청은 전부 → 「들어오는 문」에서 다룬 ingress-nginx로 넘긴다. [code:apps/cloudflared/configmap.yaml:1-2] [docs:history/build_log/03_cloudflare_tunnel.md:87]

공개 주소 일곱 개는 성격이 둘로 나뉜다. 누구나 보는 공개 앱 둘(petmint, runshoes)과 운영하는 사람만 쓰는 운영 도구 다섯(ArgoCD, Harbor, Jenkins, Grafana, Prometheus)이다. 운영 도구는 Cloudflare Access라는 로그인 관문 뒤에 있고, 사설망 안에서는 터널을 거치지 않고 사설 VIP로 같은 문에 닿는 길이 따로 있다. 두 길이 어떻게 나뉘고 왜 그렇게 나눴는지는 → 「공개 경로와 내부 경로」에서 다룬다. [code:apps/monitoring/ingress.yaml:2-6]

브라우저와 서버 사이의 암호화(TLS)를 어디서 푸는지도 두 무리가 다르다. 공개 앱은 Cloudflare 엣지에서 풀리고, 운영 도구는 cert-manager가 Let's Encrypt에서 받아 온 인증서로 ingress-nginx가 푼다. 어느 구간이 어떤 인증서로 암호화되는지는 → 「TLS가 끝나는 곳」에서 다룬다. [docs:history/cluster_state_20261116.md:36-48]

터널 설정은 GitOps로 관리하지만 자동 반영을 일부러 꺼 두었다. 이 터널이 깨지면 공개 주소 일곱 개가 한꺼번에 사라지고, 고칠 도구인 ArgoCD와 볼 도구인 Grafana도 같이 사라지기 때문이다. 그 까닭과 설정을 바꿀 때 주의할 점은 → 「공개 경로와 내부 경로」에 적었다. [code:apps/cloudflared/app.yaml:4-8]

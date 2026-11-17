<!--
다루는 곳: apps/cloudflared/, apps/monitoring/ingress.yaml
읽은 커밋: ddbaadf
-->
# 포트포워딩 없이 공개하기

> 이 글은 사무실 서버 안의 서비스를 인터넷에 내놓을 때 공유기 포트포워딩 대신 Cloudflare Tunnel을 고른 결정을 다룹니다.

**웹 서비스는 공유기에 구멍을 뚫지 않고, 클러스터 안에서 도는 cloudflared가 Cloudflare 쪽으로 먼저 맺어 둔 연결을 타고 들어옵니다. 터널 하나가 공개 주소 일곱 개를 모두 받고, 운영 도구는 그 앞에 로그인 관문을 하나 더 둡니다.**

## 상황

클러스터는 사무실 서버 위의 VM 안에 있습니다. 바깥 인터넷과 서버 사이에는 공유기가 있고, 서버를 바깥에 내놓는 흔한 방법은 포트포워딩(공유기에 「이 포트로 오는 요청은 이 서버로 보내라」고 적어 두는 것)입니다 [docs:history/build_log/03_cloudflare_tunnel.md:79].

포트포워딩에는 기록해 둔 문제가 있었습니다. 일반 회선은 다시 접속하면 주소가 바뀔 수 있고, 공유기에 뚫어 둔 구멍으로는 누구나 들어오려 할 수 있으며, 학교나 회사 망에서는 애초에 그 설정을 할 권한이 없기도 합니다 [docs:history/build_log/03_cloudflare_tunnel.md:81-85].

내놓아야 할 것은 공개 앱 둘(petmint, runshoes)과 운영 도구 다섯(ArgoCD, Harbor, Jenkins, Grafana, Prometheus)입니다 [code:apps/cloudflared/app.yaml:5].

## 고른 것

Cloudflare Tunnel을 씁니다. 터널은 방향이 거꾸로입니다. 서버 쪽 프로그램 cloudflared가 Cloudflare로 나가는 연결을 먼저 맺어 두고, 바깥 요청이 오면 Cloudflare가 그 연결을 거꾸로 태워 들여보냅니다 [docs:history/build_log/03_cloudflare_tunnel.md:87]. 그래서 웹 서비스를 위해 들어오는 포트를 열지 않습니다 [docs:history/human_answers_20261117.md:12].

포트포워딩이 아주 없어진 것은 아닙니다. 서버를 관리하는 SSH 하나에는 지금도 공유기 포트포워딩을 씁니다. 웹 서비스 공개에만 쓰지 않습니다 [docs:history/human_answers_20261117.md:13] [docs:history/notion_hardware_20261116.md:11].

cloudflared는 서버 호스트의 프로세스가 아니라 클러스터 안의 파드(쿠버네티스가 띄우고 관리하는 실행 단위)로 띄웠습니다. 두 벌이 같은 터널에 붙어 있어 하나가 죽어도 다른 하나가 받습니다 [code:apps/cloudflared/deployment.yaml:1] [code:apps/cloudflared/deployment.yaml:13].

터널은 앱을 하나하나 가리키지 않습니다. 공개 주소 일곱 개가 모두 같은 목적지, 클러스터 안의 ingress-nginx로 가고, 어느 앱으로 보낼지는 ingress-nginx가 호스트 이름을 보고 고릅니다 [code:apps/cloudflared/configmap.yaml:1-2]. 그 문은 → 「문은 하나만: MetalLB와 ingress-nginx」에서 다룹니다.

터널은 길을 이어 줄 뿐 누가 들어와도 되는지는 따지지 않습니다. 그래서 운영 도구 앞에는 Cloudflare Access(공개 주소 앞에 세우는 로그인 관문)를 둡니다. 운영 도구는 「운영도구」라는 하나의 Access 앱으로 묶여 있고, 공개 사이트인 runshoes에는 Access가 없습니다 [docs:history/build_log/03_cloudflare_tunnel.md:175] [code:apps/monitoring/ingress.yaml:2-3] [code:apps/cloudflared/configmap.yaml:30]. Prometheus는 자체 로그인이 없어 바깥에서는 Access가 유일한 문이므로, Access를 먼저 걸고 나서 공개 주소를 열었습니다 [code:apps/monitoring/ingress.yaml:5].

## 까닭

터널을 고른 까닭으로 기록에 남은 것은 서비스용으로 들어오는 포트를 열지 않는다는 점입니다 [docs:history/human_answers_20261117.md:12]. 서버 주소를 숨기려고 고른 것은 아닙니다. 다만 결과로, 바깥에서 공개 주소를 찾아보면 보이는 것은 서버 주소가 아니라 Cloudflare의 주소입니다 [docs:history/human_answers_20261117.md:12].

cloudflared를 파드로 띄운 까닭은 운영을 쿠버네티스에 맡기기 위해서입니다. 호스트 프로세스라면 죽었을 때 사람이 다시 띄우고, 여러 벌로 늘리는 것도 손으로 해야 하며, 설정이 호스트 파일에 남습니다. 파드로 두면 쿠버네티스가 상태를 보고 다시 띄우고, 두 벌은 설정 한 줄이며, 설정이 저장소에 남습니다 [docs:history/build_log/03_cloudflare_tunnel.md:129-139].

터널이 ingress-nginx 하나만 가리키게 한 까닭은 앱이 늘 때마다 터널을 고치지 않으려는 것입니다. 새 앱은 Ingress 규칙만 더하면 됩니다. 다만 이 터널은 설정 파일 방식이라 공개 주소를 더할 때는 설정에 주소 한 줄과 Cloudflare 쪽 DNS 기록도 같이 더합니다 [docs:history/build_log/03_cloudflare_tunnel.md:143-153].

## 치른 값

- 터널 하나에 공개 주소 일곱 개가 몰려 있습니다. 터널이 깨지면 공개 앱만이 아니라 고칠 도구(ArgoCD 화면)와 볼 도구(Grafana)도 바깥에서 한꺼번에 사라집니다 [code:apps/cloudflared/app.yaml:5-6]
- 그래서 cloudflared는 저장소 변경이 자동으로 반영되지 않는 유일한 앱입니다. 다른 앱은 커밋이 곧 배포로 이어지지만, 이 앱은 사람이 반영을 누르고 교체 과정을 지켜봅니다. 잘못된 커밋 하나가 사람 손을 거치지 않고 바깥 길 전체를 끊게 두지 않으려는 것입니다 [code:apps/cloudflared/app.yaml:4-8] [docs:history/cluster_state_20261116.md:56-61]
- 터널이 끊겼을 때를 위한 길을 남겨 두었습니다. 서버 호스트에서는 터널을 거치지 않고 ingress-nginx의 사설망 고정 주소(VIP)로 운영 도구 화면을 열 수 있고, 관리 노드에 들어가 명령으로 되돌릴 수 있습니다 [code:apps/cloudflared/README.md:24-25]
- 그 사설망 길에는 Access가 없습니다. 자체 로그인이 없는 Prometheus도 사설망 안에서는 그대로 열립니다 [code:apps/monitoring/ingress.yaml:6]
- cloudflared는 설정을 켜질 때 한 번만 읽습니다. 설정을 반영한 뒤 파드를 차례로 다시 띄우는 단계까지 해야 새 설정이 들어갑니다. 새 설정이 깨져 있으면 새 파드가 준비되지 못해 교체가 멈추고, 옛 두 벌이 계속 받습니다 [code:apps/cloudflared/configmap.yaml:3] [code:apps/cloudflared/deployment.yaml:3-4]

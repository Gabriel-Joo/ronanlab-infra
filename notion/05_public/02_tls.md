<!--
다루는 곳: platform/cert-manager/
읽은 커밋: 736d833
-->
# 05-02 TLS가 끝나는 곳

TLS는 브라우저와 서버 사이의 내용을 암호화하고, 상대가 진짜 그 주소의 주인인지 인증서로 확인하는 규약이다. 주소창의 자물쇠가 이것이다. 요청은 브라우저에서 앱까지 여러 구간을 지나는데, 구간마다 암호화를 풀고 다시 싸는 자리가 다르다. 암호화를 푸는 자리를 「TLS가 끝나는 곳」이라고 부른다. 이 클러스터에서는 공개 앱과 운영 도구가 서로 다른 자리에서 TLS를 끝낸다. 길 자체는 → 「공개 경로와 내부 경로」에서 다뤘다.

## 공개 앱: Cloudflare 엣지에서 끝난다

petmint와 runshoes의 Ingress에는 인증서 칸(tls)이 없다. 우리 쪽은 이 두 주소의 인증서를 갖고 있지 않다는 뜻이다. 그래서 브라우저가 맺은 TLS는 Cloudflare 엣지에서 끝난다. 브라우저가 보는 자물쇠는 Cloudflare가 내놓은 것이다. [code:apps/petmint/app/ingress.yaml:1] [code:apps/runshoes/app/ingress.yaml:1] [docs:history/cluster_state_20261116.md:45-46]

엣지에서 클러스터 안 cloudflared까지는 터널이 잇는다. 터널은 그 자체가 암호화된 통로다. cloudflared에서 ingress-nginx까지는 다시 HTTPS로 간다. 터널 설정이 원점을 HTTPS로 적고 있어서다. [code:apps/cloudflared/configmap.yaml:13-17] 이 설정은 학교 클러스터 시절에서 왔다. 그때 원점은 다른 문 프로그램(traefik)이었고, HTTP로 들어온 요청을 HTTPS로 다시 오라고 돌려보내 그 응답이 터널을 거쳐 같은 자리를 맴돌 수 있었다. [docs:history/build_log/03_cloudflare_tunnel.md:157-159] 지금 Ingress 일곱 개는 모두 그 돌려보내기를 꺼 두었으므로, 이 걱정은 지금 문에는 해당하지 않는다. [code:apps/petmint/app/ingress.yaml:11-12] [code:apps/runshoes/app/ingress.yaml:11] [code:platform/argocd/ingress.yaml:15] [code:platform/harbor/values.yaml:16] [code:platform/jenkins/values.yaml:10] [code:apps/monitoring/ingress.yaml:39] [code:apps/monitoring/ingress.yaml:66]

다만 이 HTTPS 구간에서 cloudflared는 ingress-nginx의 인증서를 확인하지 않는다. 일곱 주소 모두 확인을 끄는 설정(noTLSVerify)을 달았다. [code:apps/cloudflared/configmap.yaml:13-43] [docs:history/cluster_state_20261116.md:50]

확인을 켜면 일곱 주소 모두 실패한다. 터널 설정은 원점을 클러스터 안 서비스 이름으로 적었고, 따로 정하지 않으면 cloudflared는 원점 인증서에 그 서비스 이름이 적혀 있기를 기대한다. [code:apps/cloudflared/configmap.yaml:13-17] [docs:history/notls_check_20261117.md:16-18] 그런데 ingress-nginx가 내놓는 인증서에는 그 이름이 없다. 서비스 이름으로 물으면 스스로 만든 임시 인증서를 내놓는다. 공개 주소로 물으면 운영 도구는 그 공개 주소 이름의 인증서를, 인증서가 없는 공개 앱은 역시 임시 인증서를 내놓는다. [docs:history/notls_check_20261117.md:9-14] 어느 쪽이든 기대한 이름과 맞지 않는다. [docs:history/notls_check_20261117.md:20-24]

ingress-nginx에서 앱 파드까지는 암호화하지 않은 HTTP다. ingress-nginx는 따로 말하지 않으면 뒤쪽 서비스에 HTTP로 요청하고, 두 앱의 Ingress는 그 설정을 바꾸지 않는다. [code:apps/petmint/app/ingress.yaml:10-28] [docs:history/build_log/04_argocd.md:176]

## 운영 도구: ingress-nginx에서 끝난다

운영 도구 다섯(ArgoCD, Harbor, Jenkins, Grafana, Prometheus)은 Ingress마다 인증서 칸이 있고, 거기 적힌 인증서를 ingress-nginx가 내놓는다. 브라우저의 TLS는 ingress-nginx에서 끝나고, 자물쇠는 우리 인증서다. [docs:history/cluster_state_20261116.md:38-44]

인증서는 cert-manager가 받아 온다. cert-manager는 「이 이름의 인증서를 이 비밀 저장소(Secret)에 넣어 두라」는 요청서(Certificate)를 읽고, 공인 인증 기관 Let's Encrypt에서 인증서를 받아 Secret에 넣는다. ArgoCD, Harbor, Jenkins의 요청서는 `platform/cert-manager`에, Grafana와 Prometheus의 요청서는 모니터링 매니페스트에 있다. 다섯 개 모두 같은 발급자를 쓰고, 다섯 개 모두 발급을 마친 상태다. [code:platform/cert-manager/argocd-certificate.yaml:1] [code:platform/cert-manager/harbor-certificate.yaml:1] [code:platform/cert-manager/jenkins-certificate.yaml:1] [code:apps/monitoring/ingress.yaml:8-30] [docs:history/cluster_state_20261116.md:48]

Let's Encrypt는 인증서를 주기 전에 그 이름의 주인이 맞는지 시험한다. 시험 방법은 두 가지가 흔하다. 하나는 그 주소의 웹 서버에 정해진 파일을 놓게 해 바깥에서 열어 보는 방식(HTTP-01)이고, 다른 하나는 그 이름의 DNS에 정해진 기록을 올리게 해 확인하는 방식(DNS-01)이다. 이 클러스터는 들어오는 포트를 열지 않았고 운영 도구는 Access 뒤에 있어서, Let's Encrypt가 바깥에서 파일을 열어 볼 수 없다. 그래서 DNS-01을 쓴다. cert-manager는 Cloudflare API 토큰으로 DNS 기록을 직접 올린다. 토큰은 저장소에 두지 않고 사람이 Secret으로 넣는다. [code:platform/cert-manager/values.yaml:1] [code:platform/cert-manager/cluster-issuer.yaml:1] [code:platform/cert-manager/cluster-issuer.yaml:21-37]

DNS 기록이 퍼졌는지 확인할 때는 공개 DNS 서버에만 묻게 했다. 노드나 클러스터 안의 이름 해석은 사설 VIP로 바꿔 둔 이름이 있어 확인을 흐릴 수 있다. [code:platform/cert-manager/values.yaml:4-7]

발급자는 시험용(staging)과 운영용(prod) 둘이 있다. 운영용은 한 주에 받을 수 있는 수에 한도가 있어서, 처음 받을 때는 시험용으로 절차를 확인한 뒤 운영용으로 바꾼다. 지금 다섯 인증서는 모두 운영용 발급자를 쓴다. [code:platform/cert-manager/cluster-issuer.yaml:2-6] [code:platform/cert-manager/cluster-issuer.yaml:24]

공인 기관이 내준 인증서라 따로 준비할 것이 없다. 노드의 containerd가 Harbor에서 이미지를 받을 때 인증서 확인을 켠 채로 받는데, 노드마다 우리만의 인증 기관을 심어 둘 필요가 없다. [docs:history/build_log/02_metrics_storage_ingress.md:209] [code:platform/harbor/values.yaml:3-4]

## ArgoCD는 한 번 더 싼다

ArgoCD 화면을 내놓는 argocd-server는 자기 인증서로만 HTTPS를 받는다. 그래서 ArgoCD Ingress는 ingress-nginx에서 브라우저의 TLS를 끝낸 뒤, argocd-server로 넘길 때 다시 HTTPS로 싸서 보낸다. 이 설정이 없으면 ingress-nginx가 HTTP로 보내 argocd-server가 받지 않는다. [code:platform/argocd/ingress.yaml:3-4] [code:platform/argocd/ingress.yaml:14] [docs:history/build_log/04_argocd.md:176]

반대로 ingress-nginx가 TLS를 풀지 않고 argocd-server까지 그대로 흘려보내는 방식(통과)은 쓰지 않는다. 통과를 켜면 ingress-nginx가 TLS를 끝내지 않으니 cert-manager가 받아 온 인증서가 쓰이지 않는다. ArgoCD 인증서의 Secret 이름을 argocd-server가 쓰는 이름과 다르게 둔 것도 같은 까닭이다. 그 이름이면 argocd-server가 Secret을 자기 서버 인증서로 가져가 버린다. [code:platform/argocd/ingress.yaml:5-6] [code:platform/cert-manager/argocd-certificate.yaml:2]

## 사설 VIP로 와도 같은 인증서다

사설망에서 사설 VIP로 들어오는 요청도 같은 Ingress에 닿으므로, ingress-nginx는 같은 인증서를 내놓는다. 공개 주소와 같은 이름을 쓰기 때문에 이 인증서는 사설 VIP 길에서도 그대로 확인을 통과한다. 노드의 containerd가 Harbor를 부를 때와 서버 호스트에서 운영 도구 화면을 열 때가 이 경우다. [code:apps/monitoring/ingress.yaml:4] [code:apps/cloudflared/README.md:24-25] [code:platform/harbor/values.yaml:4]

Harbor는 Ingress를 Harbor의 helm 차트가 만든다. 차트에 인증서를 직접 만들지 말고 cert-manager가 넣어 둔 Secret을 쓰라고 적어 두었다. [code:platform/harbor/values.yaml:5-9] [code:platform/harbor/values.yaml:20-21]

## 한눈에

| 누구 | 브라우저 TLS가 끝나는 곳 | 터널에서 문까지 | 사설 VIP로 올 때 |
| --- | --- | --- | --- |
| petmint, runshoes | Cloudflare 엣지 | HTTPS, 확인 끔 | 우리 인증서 없음 |
| Harbor, Jenkins, Grafana, Prometheus | ingress-nginx(Let's Encrypt) | HTTPS, 확인 끔 | 같은 인증서 |
| ArgoCD | ingress-nginx(Let's Encrypt), 뒤로 다시 TLS | HTTPS, 확인 끔 | 같은 인증서 |

## 알려진 한계

- cloudflared는 ingress-nginx의 인증서를 확인하지 않는다. 그 구간에서는 상대가 진짜 ingress-nginx인지 따지지 않는다 [code:apps/cloudflared/configmap.yaml:17]
- 모든 Ingress가 HTTPS로 다시 오라고 돌려보내지 않게 꺼 두었다. 터널은 HTTPS로 오지만, 사설망에서는 암호화하지 않은 HTTP로도 같은 화면에 닿는다 [code:platform/argocd/ingress.yaml:7] [code:platform/argocd/ingress.yaml:15]
- Cloudflare API 토큰이 저장소에 없는 것은 비밀값을 저장소에 두지 않는 결정에서 나와 → 「알려진 한계」에 모았다
- 공개 앱의 인증서는 Cloudflare 쪽에 있어 저장소로는 볼 수 없다 [docs:history/cluster_state_20261116.md:45-46]

## 용어 풀이

- TLS: 오가는 내용을 암호화하고 상대의 인증서를 확인하는 규약
- 인증서: 「이 이름의 주인이 맞다」고 인증 기관이 서명해 준 증명
- Let's Encrypt: 인증서를 무료로 내주는 공인 인증 기관
- cert-manager: 클러스터 안에서 인증서를 받아 오고 Secret에 넣어 두는 프로그램
- Certificate: cert-manager에게 어떤 이름의 인증서를 받아 달라고 적는 요청서
- ClusterIssuer: 어느 인증 기관에서 어떤 방식으로 받을지 정한 발급자 설정
- DNS-01: DNS 기록을 올려 이름의 주인임을 증명하는 방식 [code:platform/cert-manager/cluster-issuer.yaml:30-31]
- noTLSVerify: cloudflared가 원점의 인증서를 확인하지 않게 하는 설정
- Secret: 인증서나 토큰 같은 값을 담아 두는 쿠버네티스 저장 칸

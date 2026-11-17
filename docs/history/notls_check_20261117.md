# cloudflared 원점 인증서 확인 기록 (2026-11-17)

cloudflared 원점 설정의 `noTLSVerify: true`가 일곱 호스트 모두에 왜 필요한지 확인했다. 관리자 세션이 읽기 명령만 썼다(지시 18).

## 클러스터에서 본 것

m-k8s에서 ingress-nginx Service의 ClusterIP 443으로 `openssl s_client -servername <SNI>`를 붙여, ingress-nginx가 SNI마다 내놓는 인증서의 subject와 issuer만 읽었다. cloudflared 이미지는 `cloudflare/cloudflared:2026.10.0`이다.

| 보낸 SNI | 받은 인증서 |
| --- | --- |
| `ingress-nginx-controller.ingress-nginx.svc.cluster.local`(터널 설정의 원점 이름) | `CN = Kubernetes Ingress Controller Fake Certificate`, 발급자도 같음(자체 서명) |
| `argocd.ronanlab.dev` | `CN = argocd.ronanlab.dev`, 발급자 Let's Encrypt |
| `grafana.ronanlab.dev` | `CN = grafana.ronanlab.dev`, 발급자 Let's Encrypt |
| `petmint.ronanlab.dev` | `CN = Kubernetes Ingress Controller Fake Certificate`(자체 서명) |

## Cloudflare 문서

Cloudflare Tunnel origin parameters 문서(developers.cloudflare.com, 2026-11-17 읽음)에 따르면 `originServerName`의 기본값은 비어 있고, 비어 있으면 cloudflared는 원점 인증서에 service URL의 호스트 이름이 적혀 있기를 기대한다. `matchSNItoHost`의 기본값은 false다. 이 저장소의 터널 설정에는 둘 다 없다(`apps/cloudflared/configmap.yaml`).

## 정리

일곱 호스트 모두 원점을 `ingress-nginx-controller.ingress-nginx.svc.cluster.local`로 적었으므로, cloudflared는 인증서에 이 서비스 이름이 있기를 기대한다. ingress-nginx가 내놓는 인증서는 자체 서명 임시 인증서이거나 공개 주소 이름의 Let's Encrypt 인증서라, 어느 쪽에도 이 서비스 이름이 없다. 그래서 확인을 켜면 일곱 호스트 모두 실패한다.

cloudflared가 실제로 보내는 SNI 값은 선 위에서 보지 않았다. 다만 위 정리는 SNI가 무엇이든 성립한다. 서비스 이름을 보내면 자체 서명 인증서를 받고, 공개 주소를 보내면 이름이 다른 인증서를 받기 때문이다.

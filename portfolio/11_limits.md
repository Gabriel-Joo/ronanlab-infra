<!--
다루는 곳: cluster/label-nodes.sh, apps/cloudflared/app.yaml, bootstrap/root-app.yaml, platform/cert-manager/cluster-issuer.yaml
읽은 커밋: 40ca5f3
-->
# 알려진 한계

> 이 글은 이 홈랩을 만들며 고른 결정 가운데 여러 편에 걸치는 것과, 그 결정 때문에 하지 못하게 된 것을 다룹니다.

**앞의 편들은 결정 하나씩 무엇을 골랐고 무엇을 치렀는지를 보였습니다. 그중 여러 결정에 되풀이되는 것만 이 편에 모았고, 한 결정에만 걸리는 것은 그 편의 「치른 값」에 그대로 있습니다. 결정마다 무엇을 왜 골랐는지와 그 값으로 치른 것을 적고, 끝의 하나는 고른 것이 아니라 바꿀 수 없는 조건입니다. 아직 하지 않은 일은 한계가 아니어서 저장소의 할 일 목록에 따로 둡니다 [docs:TODO.md]. 자세한 까닭은 기술문서의 알려진 한계 편에 있습니다.**

## 1. 노드마다 역할을 하나씩 정했습니다

노드가 죽었을 때 무엇이 멈추는지를 노드 이름으로 말할 수 있게 하려고, 워커마다 역할을 정하고 각 구성 요소를 그 역할의 노드에 고정했습니다 [docs:history/build_log/08_scale_out.md:129]. 앱을 맡는 노드는 둘이지만, 이미지 저장소와 빌드 서버와 배포 도구를 맡는 w3, 모니터링을 맡는 w4는 한 대씩입니다 [code:cluster/label-nodes.sh:6-8]. 그 노드가 빠지면 거기 고정한 것은 다른 노드로 옮겨 뜨지 않습니다(→ 「워커를 늘리고 옮기기」).

치른 값은 이렇습니다.

- w3이 죽으면 배포와 빌드가, w4가 죽으면 모니터링이 그 노드가 돌아올 때까지 멈춥니다. 목표로 받아들인 한계입니다 [docs:history/build_log/08_scale_out.md:434]
- 빌드 서버 Jenkins도 본체가 하나이고 w3에 묶여 있어, w3를 정비하는 동안 빌드가 멈춥니다. 이미 떠 있는 앱은 영향이 없습니다 [docs:history/build_log/06_jenkins.md:504]

## 2. 바깥 공개는 터널 하나로 모았습니다

웹 서비스는 공유기 포트포워딩 없이 Cloudflare 터널 하나로 공개하고, 어느 앱으로 보낼지는 클러스터 안의 들어오는 문(ingress-nginx)이 주소를 보고 고릅니다. 앱이 늘 때마다 터널을 새로 만들지 않고, 들어오는 문의 규칙 하나와 터널 설정 한 줄만 더하려는 것입니다 [docs:history/build_log/03_cloudflare_tunnel.md:153]. 그래서 공개 주소가 모두 한 터널을 지납니다(→ 「포트포워딩 없이 공개하기」).

치른 값은 이렇습니다.

- 터널 하나에 공개 주소 일곱 개가 몰려 있습니다. 터널이 깨지면 공개 앱만이 아니라 고칠 도구(ArgoCD 화면)와 볼 도구(Grafana)도 바깥에서 한꺼번에 사라집니다 [code:apps/cloudflared/app.yaml:4-7]

## 3. 기반은 ArgoCD 밖에서 손으로 넣습니다

인증서 관리 도구(cert-manager), 로드밸런서(MetalLB), 들어오는 문(ingress-nginx), Harbor, Jenkins 같은 기반은 ArgoCD(저장소의 내용대로 클러스터를 맞추는 도구) 밖에 있고, 사람이 Helm이나 kubectl로 넣습니다. 기록된 까닭은 이것들이 ArgoCD보다 먼저 깔린 기반이라는 것입니다 [code:bootstrap/root-app.yaml:13] (→ 「사람 손을 타지 않는 배포」).

치른 값은 이렇습니다.

- 기반의 설정을 고쳐 저장소에 올려도 클러스터는 바뀌지 않습니다. 바꾼 사람이 손으로 넣어야 하고, 넣지 않으면 저장소와 클러스터가 어긋납니다 [code:platform/ingress-nginx/overlay/kustomization.yaml:1] [code:bootstrap/root-app.yaml:13]

## 4. 비밀값은 저장소에 두지 않았습니다

비밀번호와 토큰 같은 비밀값은 저장소에 두지 않고, 사람이 클러스터에 직접 만듭니다 [code:CLAUDE.md:47]. 공개 저장소에 올라가는 설정 파일에 실제 값이 박히는 것을 막으려는 것입니다 [docs:history/build_log/03_cloudflare_tunnel.md:188].

치른 값은 이렇습니다.

- 클러스터를 다시 세우면 비밀값은 저장소에서 돌아오지 않아, 사람이 다시 넣어야 합니다 [code:CLAUDE.md:47]
- 인증서 발급에 쓰는 Cloudflare API 토큰도 그중 하나라, 클러스터를 다시 만들 때 사람이 넣지 않으면 인증서를 받지 못합니다 [code:platform/cert-manager/cluster-issuer.yaml:1] (→ 「TLS가 끝나는 곳과 noTLSVerify를 확인한 일」)

## 5. 조건: 물리 서버 한 대

이것은 고른 것이 아니라 가진 자원입니다. 사무실 서버 가운데 이 프로젝트가 쓰는 것은 한 대이고 [docs:history/notion_hardware_20261116.md:12], 쿠버네티스 VM 다섯 대가 같은 서버, 같은 디스크 위에 있습니다 [docs:history/build_log/01_cluster.md:699]. 노드를 여럿으로 나눈 것은 VM 하나나 노드 프로그램 하나가 죽는 장애까지만 막습니다 [docs:history/build_log/08_scale_out.md:436]. 그래서 여러 벌로 늘려도 서버와 함께 꺼지는 것은 들이지 않았습니다. 컨트롤 플레인을 한 대로 둔 것이 그렇습니다(→ 「손으로 세운 여러 노드 클러스터」).

- 서버가 꺼지면 클러스터, 운영 도구, 호스트의 추론 서버와 벡터 DB, model-service가 함께 멈춥니다 [code:cluster/Vagrantfile:3-10] [docs:history/build_log/kubernetes_install.md:198]
- 앱을 맡는 노드도 둘뿐이라, 하나가 빠지면 각 앱이 파드 하나로 버팁니다 [docs:history/build_log/08_scale_out.md:433] [c:44860df]

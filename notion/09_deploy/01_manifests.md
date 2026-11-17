<!--
다루는 곳: apps/petmint/app/, apps/runshoes/app/
읽은 커밋: 736d833
-->
# 09-01 매니페스트의 꼴

앱 하나는 매니페스트(쿠버네티스에 「이런 것을 이렇게 띄워라」라고 적은 YAML 파일) 여러 장으로 이루어진다. 두 앱 모두 `apps/<앱>/kustomization.yaml`이 그 목록이고, 목록의 모든 리소스에 네임스페이스와 소속 라벨을 한꺼번에 붙인다. 소속 라벨은 파드를 고르는 선택자에는 넣지 않고 리소스에만 붙인다. [code:apps/petmint/kustomization.yaml:4-28] [code:apps/runshoes/kustomization.yaml:4-23] 목록에 네임스페이스 자체와 Secret은 없다. 그 까닭은 → 「처음 배포와 시크릿」에서 다룬다.

## 앱 파드: Deployment

두 앱 모두 앱 파드를 둘 띄운다. 세션과 상태가 데이터베이스에 있어 파드를 늘려도 되기 때문이다. [code:apps/petmint/app/deployment.yaml:1-3] [code:apps/petmint/app/deployment.yaml:17] 둘은 앱 역할 라벨이 붙은 노드(w1, w2)에만 뜨고, 같은 노드에 둘이 함께 뜨지 못하게 막아 두었다(required anti-affinity). 노드 하나가 죽어도 다른 노드의 파드가 요청을 받는다. [code:apps/petmint/app/deployment.yaml:43-51]

새 이미지로 바꿀 때는 옛 파드 하나를 먼저 내리고 그 자리에 새 파드를 띄운다(`maxSurge 0`, `maxUnavailable 1`). 보통은 새 파드를 먼저 띄우고 옛 파드를 내리는 쪽이 안전하지만, 앱 노드가 둘뿐이고 같은 노드에 둘을 두지 못하니 세 번째 파드가 갈 곳이 없어 롤링이 멈춘다. 그래서 롤링 동안 잠깐 파드가 하나로 줄어드는 것을 받아들였다. [code:apps/petmint/app/deployment.yaml:4-7] [code:apps/petmint/app/deployment.yaml:19-23] 새 파드가 준비되지 못하면 롤링이 거기서 멈추고 남은 옛 파드 하나가 계속 받는다. 배포가 잘못돼도 서비스가 통째로 끊기지 않는 것은 이 덕분이다. [code:apps/runshoes/README.md:34]

파드가 내려갈 때는 종료 직전에 5초를 기다린다(preStop). 그사이 Ingress가 이 파드를 받을 곳 목록에서 빼므로, 이미 내려가는 파드로 새 요청이 가지 않는다. [code:apps/petmint/app/deployment.yaml:96-99] 열려 있던 웹소켓 연결은 이때 한 번 끊기고, 화면이 다음 질문 때 새 파드로 다시 붙는다. [code:apps/petmint/app/deployment.yaml:40-42] [code:apps/runshoes/README.md:31-33]

파드가 살아 있는지는 세 가지 검사로 본다. 기동 검사(startupProbe)가 통과할 때까지는 생존 검사(livenessProbe)가 파드를 죽이지 않는다. 앱이 처음 뜨면서 데이터를 확인하거나 스키마를 넣는 동안 「응답이 없다」고 잘못 재시작되지 않게 하려는 것이다. 준비 검사(readinessProbe)가 통과해야 요청이 들어온다. [code:apps/petmint/app/deployment.yaml:84-95] 런슈즈의 준비 검사는 데이터베이스 연결까지 본다. 검사 경로는 이미지가 제공하는 것이라, 그 경로가 없던 옛 이미지로 되돌리면 파드가 준비되지 못한다. 이미지를 되돌릴 때 검사 경로도 함께 되돌려야 하는 까닭이다. [code:apps/runshoes/app/deployment.yaml:3] [code:apps/runshoes/app/deployment.yaml:117-130]

앱보다 먼저 도는 컨테이너(initContainer)도 있다. 펫퍼민트는 초기화 Job이 스키마와 원장 시드를 다 넣을 때까지 기다린다. 앱도 기동할 때 같은 것을 확인하고 실패하지만, 그러면 재시작이 쌓이기 때문이다. [code:apps/petmint/app/deployment.yaml:52-56] 런슈즈는 MySQL이 열릴 때까지 기다린다. 노드를 다시 켰을 때 앱이 MySQL보다 먼저 뜨면 Flyway가 데이터베이스에 붙지 못하고 앱이 스스로 끝나 버린 일이 있었다. 기다림은 3분이 넘으면 실패하고, 그러면 쿠버네티스가 간격을 두고 다시 시도한다. [code:apps/runshoes/app/deployment.yaml:57-73]

컨테이너는 root가 아닌 사용자로 돌고, 루트 파일 시스템을 읽기 전용으로 두며, 리눅스 특권(capability)을 모두 버린다. [code:apps/petmint/app/deployment.yaml:35-39] [code:apps/petmint/app/deployment.yaml:103-106] 이미지는 사설 이미지 저장소에서 받으므로 받기 전용 자격 증명(`harbor-pull`)을 붙인다. [code:apps/petmint/app/deployment.yaml:32-34]

런슈즈는 한 파드에 컨테이너가 둘이다. Spring 앱과 웹소켓 챗봇 사이드카(같은 파드에 붙어 함께 뜨는 보조 컨테이너)이고, 둘은 같은 앱 커밋에서 같은 태그로 빌드된다. [code:apps/runshoes/app/deployment.yaml:1-4] [code:apps/runshoes/app/deployment.yaml:138-139] 앱 컨테이너의 지표는 바깥에 열지 않는 관리용 포트로 내고, Prometheus가 파드 주소로 바로 긁어 간다. 이 포트는 Service와 Ingress에 없어 바깥에서 닿지 않는다. [code:apps/runshoes/app/deployment.yaml:36-42]

## 바깥과 잇기: Service, Ingress, PDB

Service는 앱 파드 둘을 하나의 이름으로 묶는다. 런슈즈 Service는 앱과 챗봇 두 갈래를 열고, Ingress가 경로로 나눈다. 챗봇 웹소켓 경로는 사이드카로, 나머지는 앱으로 간다. [code:apps/runshoes/app/service.yaml:1] [code:apps/runshoes/app/ingress.yaml:2] [code:apps/runshoes/app/ingress.yaml:17-33]

Ingress(바깥 요청을 주소와 경로에 따라 알맞은 서비스로 나눠 주는 규칙)는 ingress-nginx를 쓴다. TLS(전송 암호화)는 Cloudflare 가장자리에서 끝나고 터널이 HTTPS로 받은 요청을 넘겨주므로, HTTPS로 돌려보내는 설정을 껐다. 다른 공개 호스트도 같다. [code:apps/petmint/app/ingress.yaml:1] [code:apps/petmint/app/ingress.yaml:12] 상담 한 번이 웹소켓으로 길게 이어지므로 프록시의 읽기와 쓰기 제한을 1시간으로 늘렸다. 기본값 60초로는 대화 중에 연결이 끊긴다. [code:apps/petmint/app/ingress.yaml:2-3] [code:apps/petmint/app/ingress.yaml:13-14] 펫퍼민트는 답을 조금씩 흘려 보내는 응답을 모아 두지 않게 버퍼링도 껐다. [code:apps/petmint/app/ingress.yaml:15] 바깥 공개 경로 전체는 → 「공개 경로와 내부 경로」에서 다룬다.

PDB(PodDisruptionBudget, 노드 정비로 파드를 내보낼 때 최소 몇 개는 남기라는 약속)는 두 앱 모두 하나 이상을 남기게 했다. 노드를 비우는 작업이 앱 파드 둘을 한꺼번에 내보내지 않는다. [code:apps/petmint/app/pdb.yaml:1] [code:apps/petmint/app/pdb.yaml:11]

## 설정과 비밀값

비밀이 아닌 접속 정보는 ConfigMap에, 비밀번호는 Secret에 따로 둔다. [code:apps/petmint/app/configmap.yaml:1] 파드는 GPU 호스트의 추론 서버와 검색 서비스를 사설 고정 대역의 호스트 주소로 바로 부른다. 파드 안에서 「자기 자신」 주소는 파드 자신을 뜻하기 때문이다. [code:apps/petmint/app/configmap.yaml:20-26] 펫퍼민트의 검색과 답 동작을 켜고 끄는 값도 ConfigMap에 있다. 코드 기본값을 바꾸지 않고 여기서만 켜 두었으므로 되돌릴 때 이 파일만 고치면 된다. [docs:history/build_log/07_project_deploy.md:493] [code:apps/petmint/app/configmap.yaml:38-39] 다만 ConfigMap은 컨테이너가 시작할 때 한 번 읽히므로, 값만 바꾸면 떠 있는 파드에는 들어가지 않는다. 적용한 뒤 파드를 차례로 다시 띄워야 한다. [code:apps/petmint/app/configmap.yaml:27-28]

런슈즈의 로그인 비밀값은 Secret을 통째로 환경변수로 붙이고, 없어도 되는 것(optional)으로 두지 않았다. Secret이 없으면 새 파드가 시작하지 못하고 롤링이 멈춰 옛 파드가 계속 받는다. 로그인 기능이 서명 키 없이 뜨는 일은 생기지 않는다. [code:apps/runshoes/app/deployment.yaml:108-113]

## 앱 말고 도는 것: Job과 CronJob

펫퍼민트는 데이터베이스와 계정을 만들고 스키마를 맞추고 원장을 채우는 초기화 Job이 있다. 초기화용 이미지를 따로 만들지 않고 앱 이미지로 돈다. [code:apps/petmint/jobs/init-db.yaml:1-7] ArgoCD는 이 Job을 Sync 훅으로 돌린다. 적용 순서(sync-wave)는 MySQL, 볼륨, ConfigMap이 먼저이고, 그다음 Job이 끝까지 돈 뒤에 앱이 바뀐다. [code:apps/petmint/README.md:59-62] [code:apps/petmint/jobs/init-db.yaml:14-17] Job은 한번 만들면 파드 내용을 바꿀 수 없어서 태그만 바꿔 다시 적용하면 실패한다. 그래서 Sync마다 끝난 Job을 지우고 새로 만들게 했다. 여러 번 돌아도 결과가 같도록 짜 두었고, 원장 시드는 비어 있을 때만 넣는다. [code:apps/petmint/README.md:64-66]

런슈즈는 리뷰 요약을 만드는 CronJob이 매일 새벽 한 번 돈다. 웹 파드와 같은 이미지에 배치 프로필만 붙여 돌리고, 태그도 같은 `newTag` 한 줄을 함께 받는다. [code:apps/runshoes/app/cronjob.yaml:1-3] [code:apps/runshoes/app/cronjob.yaml:14-15] 배치 프로필에서는 스키마 변경 도구를 끄고 스키마가 맞는지만 확인한다. 스키마는 웹 파드의 Sync만 바꾸고, 맞지 않으면 배치가 곧바로 실패한다. [code:apps/runshoes/app/cronjob.yaml:3] 회차가 겹치면 뒤에 온 쪽이 데이터베이스 잠금에서 곧바로 끝나고, 실패해도 바로 다시 돌지 않는다. 다시 만들 대상은 앱이 남긴 표시가 정한다. [code:apps/runshoes/app/cronjob.yaml:4-5] [code:apps/runshoes/app/cronjob.yaml:16] [code:apps/runshoes/app/cronjob.yaml:26-27]

## 알려진 한계

- 롤링하는 동안 잠깐 앱 파드가 하나다. 그 사이 남은 파드가 죽으면 끊긴다. [code:apps/petmint/app/deployment.yaml:6]
- 앱 노드 하나가 빠지면 두 번째 파드는 그 노드가 돌아올 때까지 뜨지 못하고, 그동안 롤링도 멈춘다. [code:apps/petmint/app/deployment.yaml:7]
- ConfigMap만 바꾼 Sync는 떠 있는 파드에 들어가지 않는다. 파드를 다시 띄워야 한다. [code:apps/petmint/app/configmap.yaml:28]
- 런슈즈의 검사 경로는 이미지 판과 묶여 있다. 이미지를 옛 판으로 되돌릴 때 검사 경로도 맞춰야 한다. [code:apps/runshoes/app/deployment.yaml:120]
- 롤링 때 열려 있던 웹소켓은 한 번 끊긴다. [code:apps/runshoes/app/deployment.yaml:4]

## 용어 풀이

- 매니페스트: 쿠버네티스에 띄울 것을 적은 YAML 파일
- Deployment: 같은 파드를 정한 수만큼 띄우고 바꿔 끼우는 리소스
- 롤링 업데이트: 파드를 한꺼번에가 아니라 하나씩 새것으로 바꾸는 배포 방식
- anti-affinity: 정한 파드끼리 같은 노드에 놓지 말라는 규칙
- startupProbe, readinessProbe, livenessProbe: 기동이 끝났는지, 요청을 받을 수 있는지, 살아 있는지를 보는 검사
- initContainer: 앱 컨테이너보다 먼저 돌고 끝나야 하는 컨테이너
- 사이드카: 같은 파드 안에서 앱 옆에 붙어 함께 뜨는 컨테이너
- Service: 파드 여러 개를 이름 하나로 묶어 주는 리소스
- PDB: 노드 정비 때 남겨 둘 파드 수의 하한
- ConfigMap, Secret: 설정 값과 비밀값을 파드 밖에 두는 리소스
- Sync 훅: ArgoCD가 적용하는 도중 정한 순서에 따로 돌리는 작업
- CronJob: 정한 시각마다 Job을 띄우는 리소스

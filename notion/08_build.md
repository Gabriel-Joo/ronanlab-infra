<!--
다루는 곳: platform/jenkins/, scripts/make-deploy-keys.sh, apps/*/kustomization.yaml
읽은 커밋: 736d833
-->
# 08 빌드와 태그 고정

이 편은 앱 저장소에 새 코드가 들어온 순간부터 인프라 저장소에 「이 이미지를 띄워라」라는 커밋이 하나 생기기까지를 다룬다. 빌드는 Jenkins가 맡는다. Jenkins는 코드를 받아 컨테이너 이미지를 굽고, 사설 이미지 저장소(Harbor)에 올리고, 인프라 저장소에서 이미지 태그를 적은 한 줄을 고쳐 커밋한다. 그 커밋을 클러스터가 받아 실제로 바꾸는 일은 → 「GitOps」와 → 「앱이 올라가는 길」에서 다룬다. 이 편의 다른 한 축은 태그 고정이다. 클러스터에서 도는 이미지는 모두 판이 정해진 태그로 불리고, 「가장 새것」을 뜻하는 `latest`는 하나도 없다. [docs:history/cluster_state_20261116.md:71]

## Jenkins가 서 있는 자리

Jenkins는 클러스터 안에 helm 차트로 설치했다. 차트 판은 저장소의 판 기록 파일에 적어 두었다. [code:platform/versions.yaml:49-53] 클러스터 밖의 빌드 서비스(GitHub Actions 같은 것)를 쓰면 저장소에 설정 파일 하나만 두면 되지만, 그러면 빌드가 어디서 어떻게 도는지를 다룰 일이 없다. 빌드 파드를 직접 띄우고 권한을 주고 이미지를 밀어 넣는 과정 전체를 손으로 다루려고 Jenkins를 직접 세웠다. [docs:history/build_log/06_jenkins.md:118-122]

Jenkins 본체는 w3(infra 역할) 노드에 고정했다. 작업 기록을 담는 저장 공간이 w3 디스크에 있어 원래도 w3에서만 떴고, 역할 라벨로 그 사실을 분명히 적은 것이다. [code:platform/jenkins/values.yaml:19-22] [code:platform/jenkins/values.yaml:261-264] 이미지를 실제로 굽는 빌드 파드는 본체와 따로, 빌드마다 새로 떴다가 지워진다. 빌드 파드의 모양은 이 저장소가 아니라 앱 저장소의 Jenkinsfile(빌드 절차를 적은 파일)이 정한다. [code:platform/jenkins/values.yaml:20] [code:platform/jenkins/values.yaml:266-267]

빌드 파드는 특권 없이 이미지를 굽는 BuildKit rootless로 짰다. 컨테이너 안에서 이미지를 구우려고 특권 컨테이너를 쓰면 그 파드가 뚫렸을 때 노드 전체가 뚫린다. BuildKit rootless는 특권 없이 사용자 네임스페이스 안에서 빌드하고, 대가로 보안 프로필 두 가지만 푼다. [docs:history/build_log/06_jenkins.md:124-137]

## 설정은 values 한 파일에 있다

Jenkins의 작업(Job), 자격 증명, 웹훅 설정은 모두 `platform/jenkins/values.yaml`의 JCasC 블록이 만든다. 화면에서 만든 작업과 자격 증명은 Jenkins 파드를 다시 만들면 사라지기 때문이다. [docs:history/build_log/06_jenkins.md:43] 그래서 작업 설명에도 「화면에서 고치지 않는다」고 적어 두었다. [code:platform/jenkins/values.yaml:104] 작업은 앱마다 하나씩, 펫퍼민트용 `petmint-app`과 런슈즈용 `runshoes-app` 둘이다. 둘 다 앱 저장소의 main 가지를 보고, 빌드 절차는 앱 저장소의 Jenkinsfile을 읽는다. [code:platform/jenkins/values.yaml:102-127] [code:platform/jenkins/values.yaml:145-170]

빌드는 GitHub 웹훅(저장소에 push가 생기면 GitHub가 Jenkins를 불러 주는 장치)으로 시작한다. 웹훅을 놓쳤을 때를 대비해 Jenkins가 스스로 저장소를 들여다보는 폴링도 15분마다 돈다. [code:platform/jenkins/values.yaml:100-113] 바깥 공개 주소 앞의 인증 관문은 웹훅이 들어오는 경로 하나만 비켜 두었다. 그 경로를 지키는 것은 GitHub와 Jenkins가 나눠 가진 공유 비밀값으로 만든 서명이다. [code:platform/jenkins/values.yaml:92-98]

Jenkins 플러그인도 판을 고정했다. 실행 중이던 73개 전부를 판까지 적었다. 차트 기본값은 재시작할 때마다 의존 플러그인을 최신으로 올려서, 빌드가 깨져도 무엇이 바뀌었는지 알 수 없었다. 지금은 기동할 때마다 플러그인 폴더를 비우고 목록대로 다시 채우므로 설치된 것이 곧 목록이다. [code:platform/jenkins/values.yaml:172-177]

## 자격 증명은 일마다 따로 둔다

Jenkins가 하는 일은 셋이다. 앱 저장소를 읽고, 이미지를 Harbor에 올리고, 인프라 저장소에 태그 커밋을 쓴다. 이 셋에 쓰는 자격 증명을 각각 가장 좁게 나눴다. Harbor에는 프로젝트마다 이미지를 올리는 일만 할 수 있는 로봇 계정을 하나씩 두었다. 관리자 계정을 쓰면 파이프라인이 프로젝트 삭제와 사용자 관리까지 할 수 있게 되기 때문이다. [code:platform/jenkins/values.yaml:30-44] [docs:history/build_log/06_jenkins.md:159-170] 노드가 이미지를 받아 갈 때 쓰는 계정은 받기만 하는 로봇으로 따로 둔다. 이것은 → 「처음 배포와 시크릿」에서 다룬다.

인프라 저장소에는 deploy key(저장소 하나에만 붙는 SSH 키)를 쓴다. 키는 둘이다. ArgoCD가 저장소를 읽는 읽기 전용 키와, Jenkins가 태그 커밋을 올리는 쓰기 키다. 읽기와 쓰기를 나눈 것은 Harbor 로봇을 올리기와 받기로 나눈 것과 같은 생각이다. 토큰 대신 deploy key를 고른 까닭은 만료 때문에 배포가 조용히 멈추는 일을 피하려는 것이다. [code:scripts/make-deploy-keys.sh:2-5] 키를 만드는 스크립트는 개인 키를 화면에 내지 않는다. 메모리 위 임시 폴더에서 키를 만들어 클러스터 Secret에 바로 넣고 지우며, 화면에는 GitHub에 등록할 공개 키와 지문만 나온다. [code:scripts/make-deploy-keys.sh:9-11] 쓰기 키는 저장소 단위라서 두 앱의 태그 커밋에 함께 쓴다. [code:platform/jenkins/values.yaml:131]

Jenkins의 관리자 비밀번호, Harbor 로봇 비밀번호, 웹훅 공유 비밀값은 모두 사람이 클러스터에 직접 만든 Secret에서 읽는다. 저장소에는 그 Secret의 이름과 키만 있다. [code:platform/jenkins/values.yaml:24-52]

## 태그 커밋이 하는 일

빌드가 끝나면 이미지에 앱 커밋 해시의 앞 12자리를 태그로 붙여 Harbor에 올린다. [code:platform/jenkins/values.yaml:104] [code:platform/jenkins/values.yaml:147] 그다음 Jenkins는 인프라 저장소를 받아 `apps/<앱>/kustomization.yaml`의 `newTag` 한 줄을 새 태그로 바꾸고 main에 push한다. [code:apps/petmint/kustomization.yaml:3] [code:apps/runshoes/kustomization.yaml:25-26]

앱 매니페스트의 Deployment, Job, CronJob에는 이미지 이름만 있고 태그가 없다. 태그는 Kustomize(여러 매니페스트를 묶고 공통 값을 덧씌우는 도구)의 `images` 칸이 붙인다. [code:apps/petmint/app/deployment.yaml:73] [code:apps/petmint/kustomization.yaml:30-32] 이렇게 하면 같은 이미지를 쓰는 앱 파드, 펫퍼민트의 초기화 Job, 런슈즈의 요약 CronJob이 한 줄로 함께 바뀐다. 태그를 매니페스트마다 흩어 적으면 Jenkins가 여러 곳을 고쳐야 하고, 하나를 빠뜨릴 수 있다. [docs:history/build_log/07_project_deploy.md:108] [code:apps/runshoes/app/cronjob.yaml:38] 런슈즈는 앱 이미지와 챗봇 이미지가 같은 커밋에서 나오므로 두 `newTag` 줄이 늘 같은 값이다. [code:apps/runshoes/kustomization.yaml:27-31]

Jenkins는 줄을 바꾼 뒤 그 줄이 정말 새 태그가 되었는지 다시 센다. 줄을 바꾸는 명령은 아무것도 못 바꿔도 성공으로 끝나기 때문에, 줄 모양이 달라지면 빌드는 성공인데 배포만 조용히 빠질 수 있다. [docs:history/build_log/07_project_deploy.md:212-220] 그래서 `newTag` 줄 옆에는 「이 줄 모양을 바꾸면 Jenkinsfile도 바꾼다」는 주석이 붙어 있다. [code:apps/petmint/kustomization.yaml:32]

앱 저장소와 매니페스트 저장소를 나눈 것도 이 커밋 때문이다. 한 저장소에 두면 Jenkins가 태그를 바꿔 올린 push가 다시 빌드를 불러 끝없이 돈다. [docs:history/build_log/06_jenkins.md:195] 저장소를 나눠도 Jenkins가 인프라 저장소를 자기 체크아웃 단계로 받으면 폴링이 그 저장소까지 감시해 같은 고리가 생긴다. 그래서 인프라 저장소는 Jenkins가 모르는 일반 복제 명령으로 받는다. [docs:history/build_log/07_project_deploy.md:224-228] 바뀐 파일이 모두 문서뿐인 push는 빌드를 성공으로 끝내되 이미지와 태그 커밋은 건너뛴다. [docs:history/build_log/06_jenkins.md:487]

## 태그를 모두 고정했다

클러스터에서 도는 파드 이미지는 모두 판 태그를 달고 있고 `latest`는 없다. [docs:history/cluster_state_20261116.md:71] 고정하는 방법은 이미지마다 셋으로 나뉜다.

| 이미지 | 고정하는 곳 | 바꾸는 이 |
| --- | --- | --- |
| 펫퍼민트, 런슈즈 앱 | `kustomization.yaml`의 `newTag`(커밋 해시 12자리) [code:apps/petmint/kustomization.yaml:30-32] | Jenkins 태그 커밋 |
| MySQL, cloudflared, 모니터링 도구 | 매니페스트의 이미지 줄에 판 태그 [code:apps/runshoes/mysql/statefulset.yaml:41] [code:apps/cloudflared/deployment.yaml:38] | 사람이 커밋 |
| ingress-nginx | 업스트림 매니페스트 그대로, 판 태그와 digest까지 [code:platform/ingress-nginx/base/deploy.yaml:445] | 사람이 새 매니페스트로 교체 |
| helm 차트로 넣은 것 | 차트 판을 `platform/versions.yaml`에 기록 [code:platform/versions.yaml:32-53] | 사람이 helm으로 |

MySQL은 일부러 Kustomize `images`에 넣지 않았다. 넣으면 Jenkins의 태그 바꾸기가 MySQL 줄까지 건드릴 수 있어서, 이미지 줄에 판 태그를 직접 박았다. [code:apps/runshoes/mysql/statefulset.yaml:41] ingress-nginx는 업스트림이 내놓은 매니페스트를 손대지 않고 받아 두었고, 바꿀 것은 덧씌우는 층(overlay)에만 둔다. 그 매니페스트에 판 태그와 함께 digest(이미지 내용으로 계산한 지문)까지 적혀 있어, ingress-nginx는 digest까지 고정된 채 돈다. 판을 올릴 때는 새 판의 매니페스트를 통째로 다시 받아 바꾼다. [code:platform/ingress-nginx/base/kustomization.yaml:1-4] [code:platform/ingress-nginx/base/deploy.yaml:445]

helm 차트와 매니페스트 주소로 바로 넣은 것(Calico, metrics-server, local-path, ArgoCD)은 저장소에 매니페스트가 없다. 그 판은 클러스터만 알고 있었는데, 다시 만들 때 같은 판을 깔 수 있도록 `platform/versions.yaml`에 적어 두었다. [code:platform/versions.yaml:1-6] [code:platform/versions.yaml:14-30] 클러스터에만 있는 값은 사라지기 쉽고, 그 값이 없으면 같은 환경을 다시 만들 수 없기 때문이다. [docs:history/human_answers_20261116.md:19] Jenkins 본체 이미지는 values에 따로 적지 않았고 차트 판이 정한 기본 이미지를 쓴다. 차트 판이 고정돼 있으니 본체 이미지도 따라 고정된다. [docs:history/build_log/06_jenkins.md:506]

고정하는 까닭은 세 가지다. 첫째, 같은 매니페스트가 늘 같은 이미지를 뜻하게 하려는 것이다. `latest`를 쓰면 롤링(파드를 하나씩 새것으로 바꾸는 배포) 도중 어느 파드가 무엇을 도는지 알 수 없다. [code:apps/petmint/kustomization.yaml:32] 둘째, 태그에서 코드를 거꾸로 찾아갈 수 있다. 태그가 곧 앱 커밋이므로 같은 커밋이면 같은 태그이고, 어느 커밋이 도는지 태그만 보고 안다. [docs:history/build_log/07_project_deploy.md:107] [code:apps/runshoes/kustomization.yaml:26] 셋째, 되돌리기가 단순해진다. 이미지만 되돌릴 때는 인프라 저장소의 태그 커밋 하나를 revert(그 커밋을 거꾸로 적용하는 새 커밋)하면 된다. [code:apps/runshoes/README.md:64] 플러그인을 고정한 까닭도 같다. 저절로 올라가는 판은 깨졌을 때 무엇이 바뀌었는지 알려 주지 않는다. [code:platform/jenkins/values.yaml:172-173]

## 알려진 한계

- Jenkins 본체가 하나이고 한 노드에 묶인 것은 여러 편에 걸리는 한계라 → 「알려진 한계」에 모았다
- Harbor 로봇 계정에 만료가 없다. 기한을 관리할 체계가 없어 두지 않았다. [docs:history/build_log/06_jenkins.md:502]

### 조건

아래는 고른 것이 아니라 바탕이 그러해서 따라오는 것이다.

- 태그 커밋을 revert해도 데이터베이스 마이그레이션은 되돌아가지 않는다. [code:apps/petmint/README.md:27]

## 용어 풀이

- 이미지 태그: 같은 이름의 컨테이너 이미지 가운데 어느 판인지 가리키는 꼬리표
- `latest`: 따로 태그를 주지 않았을 때 붙는 이름. 가리키는 이미지가 그때그때 바뀐다
- digest: 이미지 내용으로 계산한 지문. 내용이 한 글자라도 바뀌면 값이 달라진다
- Kustomize: 여러 매니페스트를 한데 묶고 이미지 태그 같은 공통 값을 덧씌우는 도구
- JCasC: Jenkins 설정을 화면 대신 설정 파일로 적어 두는 방식
- 웹훅: 저장소에 일이 생기면 다른 서비스를 불러 알려 주는 장치
- deploy key: 저장소 하나에만 붙는 SSH 키. 읽기 전용이나 쓰기 가능으로 정해 등록한다
- 로봇 계정: 사람이 아니라 프로그램이 쓰도록 권한을 좁혀 만든 Harbor 계정
- BuildKit rootless: 특권 없이 컨테이너 안에서 이미지를 굽는 빌드 도구
- revert: 앞선 커밋의 변경을 거꾸로 적용하는 새 커밋을 만들어 되돌리는 일

<!--
다루는 곳: platform/jenkins/, scripts/make-deploy-keys.sh, apps/*/kustomization.yaml
읽은 커밋: 6290346
-->
# 빌드와 태그 고정

Jenkins가 앱 이미지를 굽고 Harbor에 올린 뒤 이 저장소의 `newTag`를 커밋하는 데까지, 그리고 클러스터의 모든 이미지 판을 고정한 자리를 적는다. 그 커밋을 ArgoCD가 받아 가는 것은 `docs/06_gitops.md`, 앱 매니페스트와 배포 절차는 `docs/09_deploy.md`다. 구축 이력은 `docs/history/build_log/06_jenkins.md`에 있다. [docs:history/build_log/06_jenkins.md]

## 지금 구성

### Jenkins

- helm 릴리스 `jenkins`, 네임스페이스 `jenkins`, 차트 `jenkins/jenkins` 5.9.68(앱 2.580.1) [code:platform/versions.yaml:49-53]
- ArgoCD 밖이다. push해도 바뀌지 않고 사람이 `helm upgrade`로 넣는다 [code:platform/versions.yaml:32]
- 컨트롤러는 w3(`node.ronanlab.dev/role: infra`)에 고정. PVC `jenkins`(local-path 8Gi)가 w3에 있다 [code:platform/jenkins/values.yaml:19-22] [code:platform/jenkins/values.yaml:261-264]
- 자원: requests cpu 500m, memory 1Gi, limits memory 2Gi [code:platform/jenkins/values.yaml:254-259]
- 주소: `https://jenkins.ronanlab.dev`, Ingress class nginx, TLS Secret `jenkins-tls`(cert-manager) [code:platform/jenkins/values.yaml:1-15]
- 컨트롤러 이미지는 values에 적지 않았다. 차트 기본 이미지를 쓴다 [docs:history/build_log/06_jenkins.md:506]
- 빌드 Pod는 앱 저장소 Jenkinsfile의 Pod 템플릿이 정한다(BuildKit rootless, 특권 없음). 이 저장소에는 없다 [code:platform/jenkins/values.yaml:20] [docs:history/build_log/06_jenkins.md:53-63]

### Job

| Job | 앱 저장소 | 만드는 이미지 | 트리거 |
| --- | --- | --- | --- |
| `petmint-app` | `Gabriel-Joo/petmint-rag-chatbot` `*/main` | `harbor.ronanlab.dev/petmint/petmint-app:<커밋 12자리>` | `githubPush()`, `pollSCM H/15 * * * *` [code:platform/jenkins/values.yaml:102-127] |
| `runshoes-app` | `Gabriel-Joo/runshoes` `*/main` | `harbor.ronanlab.dev/runshoes/runshoes:<12자리>`, `runshoes-chatbot:<같은 태그>` | 같다 [code:platform/jenkins/values.yaml:145-170] |

- 웹훅 주소 `https://jenkins.ronanlab.dev/github-webhook/`. Cloudflare Access는 이 경로만 Bypass, HMAC SHA-256 서명으로 지킨다 [code:platform/jenkins/values.yaml:92-98]
- Job과 자격 증명은 JCasC(`controller.JCasC.configScripts`의 `foreman`, `petmint`, `runshoes` 블록)가 만든다. UI에서 고치지 않는다 [code:platform/jenkins/values.yaml:54-58] [code:platform/jenkins/values.yaml:104]
- `foreman` 블록은 두 Jenkinsfile의 빌드 알림이 `http://192.168.122.1:8001/webhooks/jenkins`에 쓰는 토큰이다 [code:platform/jenkins/values.yaml:56-67]

### 자격 증명

| Jenkins 자격 증명 id | 종류 | 값이 오는 Secret(`jenkins` ns) | 쓰는 곳 |
| --- | --- | --- | --- |
| `harbor-robot-petmint-jenkins` | usernamePassword | `harbor-robot-jenkins`(username, password) | Harbor `robot$petmint+jenkins` push [code:platform/jenkins/values.yaml:73-78] |
| `harbor-robot-runshoes-jenkins` | usernamePassword | `harbor-robot-runshoes-jenkins`(username, password) | Harbor `robot$runshoes+jenkins` push [code:platform/jenkins/values.yaml:137-142] |
| `ronanlab-infra-deploy-key` | SSH | `ronanlab-infra-deploy-key`(ssh-privatekey) | 이 저장소 태그 커밋 push, 두 앱 공용 [code:platform/jenkins/values.yaml:79-86] [code:platform/jenkins/values.yaml:131] |
| `github-webhook-secret` | string | `github-webhook-secret`(secret) | 웹훅 서명 검증 [code:platform/jenkins/values.yaml:87-91] |
| `foreman-webhook-token` | string | `foreman-webhook-token`(token) | 빌드 알림 [code:platform/jenkins/values.yaml:63-67] |
| (admin 계정) | | `jenkins-admin`(jenkins-admin-user, jenkins-admin-password) | 기동마다 JCasC가 이 값으로 admin을 맞춘다 [code:platform/jenkins/values.yaml:24-28] |

- 저장소 deploy key는 둘이다. 읽기 `argocd/repo-ronanlab-infra`(ArgoCD), 쓰기 `jenkins/ronanlab-infra-deploy-key`(Jenkins) [code:scripts/make-deploy-keys.sh:2-5]
- 노드가 이미지를 받는 pull 로봇은 앱 네임스페이스의 `harbor-pull`이다(`docs/09_deploy.md`) [code:apps/petmint/scripts/create-secrets.sh:30-38]

### 플러그인

- `installPlugins` 73개 전부 `이름:버전`. 직접 쓰는 6개와 의존 [code:platform/jenkins/values.yaml:172-252]
- `installLatestPlugins: false`, `overwritePlugins: true`. 기동마다 목록대로 다시 채운다 [code:platform/jenkins/values.yaml:175-176]

### 태그 커밋

- Jenkinsfile이 빌드 뒤 이 저장소를 `sh 'git clone'`으로 받아 `newTag` 줄을 sed로 바꾸고, grep으로 다시 센 뒤 main에 push한다 [docs:history/build_log/07_project_deploy.md:212-228]
- 커밋 제목은 `<앱>: 이미지 태그 <해시>` 꼴이다. 기계가 쓰는 커밋이라 이 저장소의 커밋 메시지 규칙을 따르지 않는다 [code:CLAUDE.md:88]
- 바뀐 파일이 모두 문서뿐인 push는 SUCCESS로 끝내고 이미지와 태그 커밋을 건너뛴다 [docs:history/build_log/06_jenkins.md:487]

### 이미지 판 고정

실행 중인 모든 파드 이미지에 판 태그가 있고 `latest`는 없다. ingress-nginx controller는 digest까지 고정돼 있다 [docs:history/cluster_state_20261116.md:71]

| 대상 | 고정 자리 | 값 꼴 |
| --- | --- | --- |
| petmint 앱(Deployment, initContainer, 초기화 Job) | `apps/petmint/kustomization.yaml` `images` [code:apps/petmint/kustomization.yaml:30-32] | 커밋 해시 12자리, Jenkins가 바꾼다 |
| runshoes 앱, 챗봇, 요약 CronJob | `apps/runshoes/kustomization.yaml` `images` 두 줄 [code:apps/runshoes/kustomization.yaml:27-31] | 두 줄이 같은 값 |
| MySQL(petmint, runshoes, 복제본, 백업 CronJob) | 각 매니페스트 이미지 줄 `mysql:8.0.46` [code:apps/runshoes/mysql/statefulset.yaml:41] [code:apps/petmint/backup/cronjob.yaml:38] | `images`에 넣지 않는다(Jenkins sed가 건드리지 않게) |
| cloudflared | `apps/cloudflared/deployment.yaml:38` [code:apps/cloudflared/deployment.yaml:38] | `cloudflare/cloudflared:2026.10.0` |
| 모니터링 | 각 매니페스트 [code:apps/monitoring/prometheus/statefulset.yaml:32] [code:apps/monitoring/grafana/deployment.yaml:26] | 판 태그 |
| Harbor DB 백업 | `apps/harbor-backup/cronjob.yaml:39` [code:apps/harbor-backup/cronjob.yaml:39] | `goharbor/harbor-db:v2.15.2`(서버와 같은 판) |
| runshoes wait-mysql | `docker.io/library/busybox:1.37.0` [code:apps/runshoes/app/deployment.yaml:62] | 판 태그 |
| ingress-nginx | 업스트림 매니페스트 그대로 [code:platform/ingress-nginx/base/deploy.yaml:445] [code:platform/ingress-nginx/base/deploy.yaml:546] | `v1.11.3@sha256:…`, certgen `v1.4.4@sha256:…` |
| helm 차트(cert-manager, metallb, harbor, jenkins) | `platform/versions.yaml` `helm:` [code:platform/versions.yaml:32-53] | 차트 판 |
| URL로 넣은 매니페스트(calico, metrics-server, local-path, argocd) | `platform/versions.yaml` `manifests:` [code:platform/versions.yaml:14-30] | 판과 출처 URL |

`apps/cloudflared`, `apps/harbor-backup`, `apps/monitoring`의 `kustomization.yaml`에는 `images`가 없다. 태그는 매니페스트에 직접 있다 [code:apps/cloudflared/kustomization.yaml:16-19] [code:apps/harbor-backup/kustomization.yaml:13-14] [code:apps/monitoring/kustomization.yaml:12-37]

## 설정 자리

| 파일:줄 | 값 | 뜻 |
| --- | --- | --- |
| `platform/jenkins/values.yaml:21-22` | `nodeSelector: node.ronanlab.dev/role: infra` | 컨트롤러를 w3에 [code:platform/jenkins/values.yaml:21-22] |
| `platform/jenkins/values.yaml:26-28` | `admin.createSecret: true`, `existingSecret: jenkins-admin` | admin 비밀번호는 사람이 넣은 Secret에서 [code:platform/jenkins/values.yaml:26-28] |
| `platform/jenkins/values.yaml:32-52` | `additionalExistingSecrets` | JCasC가 `${<secret>-<key>}`로 읽는 Secret 목록 [code:platform/jenkins/values.yaml:32-52] |
| `platform/jenkins/values.yaml:108-110` | `githubPush()`, `pollSCM H/15` | 웹훅이 주력, 15분 폴링은 안전망 [code:platform/jenkins/values.yaml:100-110] |
| `platform/jenkins/values.yaml:175-177` | `installLatestPlugins: false`, `overwritePlugins: true` | 설치 = 목록 [code:platform/jenkins/values.yaml:175-177] |
| `platform/jenkins/values.yaml:261-264` | local-path 8Gi | `JENKINS_HOME` PVC [code:platform/jenkins/values.yaml:261-264] |
| `apps/petmint/kustomization.yaml:31-32` | `name`, `newTag: "<12자리>"` | Jenkins sed가 찾는 줄 모양. 바꾸면 Jenkinsfile도 바꾼다 [code:apps/petmint/kustomization.yaml:31-32] |
| `apps/runshoes/kustomization.yaml:28-31` | 두 `newTag` | 같은 값이어야 한다 [code:apps/runshoes/kustomization.yaml:28-31] |
| `scripts/make-deploy-keys.sh:13` | `REPO_SSH` | deploy key를 붙일 저장소 [code:scripts/make-deploy-keys.sh:13] |
| `platform/ingress-nginx/base/kustomization.yaml:2-3` | 출처 URL과 파일 sha256 | 업스트림 판을 바꿀 때 다시 받는다 [code:platform/ingress-nginx/base/kustomization.yaml:2-4] |

## 바꾸거나 다시 만들기

kubectl과 helm은 m-k8s에서 친다(`cd ~/k8s-cluster && vagrant ssh m-k8s`). 클러스터를 만지는 일은 원본 폴더 main에서 한 세션만 한다 [code:CLAUDE.md:23]

Jenkins를 처음부터 세울 때는 Secret을 helm보다 먼저 만든다. values가 Secret 이름을 부르기 때문이다 [docs:history/build_log/06_jenkins.md:67]

```bash
# m-k8s. 비밀값은 read -rs로 받아 표준 입력으로 넘긴다(화면과 명령 인자에 남기지 않는다)
kubectl create namespace jenkins
read -rs P && printf %s "$P" | kubectl -n jenkins create secret generic jenkins-admin \
  --from-literal=jenkins-admin-user=admin --from-file=jenkins-admin-password=/dev/stdin; unset P
read -rs P && printf %s "$P" | kubectl -n jenkins create secret generic harbor-robot-jenkins \
  --from-literal=username='robot$petmint+jenkins' --from-file=password=/dev/stdin; unset P
read -rs P && printf %s "$P" | kubectl -n jenkins create secret generic harbor-robot-runshoes-jenkins \
  --from-literal=username='robot$runshoes+jenkins' --from-file=password=/dev/stdin; unset P
```

명령 출처: [docs:history/build_log/06_jenkins.md:82-95]. `github-webhook-secret`, `foreman-webhook-token`도 같은 문서 82-103줄의 방식으로 만든다.

```bash
# 호스트에서: deploy key 둘(이미 있으면 건너뛴다). 출력된 공개 키를 GitHub ronanlab-infra Deploy keys에 등록(쓰기 키만 Allow write access)
ssh -i <m-k8s 키> vagrant@192.168.122.10 'bash -s' < scripts/make-deploy-keys.sh
```

명령 출처: [code:scripts/make-deploy-keys.sh:7-11]. 다시 만들려면 Secret과 GitHub의 옛 키를 지우고 다시 돌린다 [code:scripts/make-deploy-keys.sh:11]

```bash
# m-k8s, 저장소의 platform/을 옮겨 둔 곳에서
kubectl apply -f platform/cert-manager/jenkins-certificate.yaml
helm repo add jenkins https://charts.jenkins.io && helm repo update
helm install jenkins jenkins/jenkins --version 5.9.68 -n jenkins -f platform/jenkins/values.yaml
```

명령 출처: [docs:history/build_log/06_jenkins.md:105-110]. values를 고친 뒤에는 같은 차트 판과 `-f platform/jenkins/values.yaml`로 `helm upgrade`한다. `--reuse-values`는 앞의 값을 덮을 수 있어 쓰지 않는다 [code:CLAUDE.md:102]

- 플러그인 판을 올릴 때: 올릴 플러그인과 그 의존을 목록에서 같이 고치고 `helm upgrade` [code:platform/jenkins/values.yaml:174]
- Job을 더한 `helm upgrade` 뒤 Job이 안 보이면 관리 → Configuration as Code → Reload 한 번 [code:platform/jenkins/values.yaml:128-130]
- 차트 판을 올리면 `platform/versions.yaml`도 같은 커밋에서 고친다 [code:platform/versions.yaml:6]
- `newTag` 줄 모양을 바꾸면 앱 저장소 Jenkinsfile의 sed도 함께 바꾼다 [code:apps/runshoes/kustomization.yaml:26]
- ingress-nginx 판 올리기: `base/deploy.yaml`을 새 태그로 다시 받아 바꾸고 overlay에서 `kubectl diff -k`로 본다 [code:platform/ingress-nginx/base/kustomization.yaml:4]
- 이미지만 되돌리기: 이 저장소의 태그 커밋을 `git revert`해 push(자동 Sync 앱은 push가 곧 배포다). DB 마이그레이션은 되돌아가지 않는다 [code:apps/runshoes/README.md:64] [code:apps/petmint/README.md:27]

## 확인

```bash
helm list -n jenkins
# jenkins  jenkins  ...  deployed  jenkins-5.9.68  2.580.1
kubectl -n jenkins get pod jenkins-0 -o wide
# jenkins-0  2/2  Running  ...  w3-k8s
kubectl -n jenkins get secret
# 이름만 본다: jenkins-admin, harbor-robot-jenkins, harbor-robot-runshoes-jenkins, ronanlab-infra-deploy-key, github-webhook-secret, foreman-webhook-token, jenkins-tls
```

기대 결과 출처: [docs:history/build_log/06_jenkins.md:513-527]

```bash
# 저장소에서: 플러그인 수
awk '/installPlugins:/{f=1;next} f&&/^  [a-z]/{f=0} f&&/^    - /{n++} END{print n}' platform/jenkins/values.yaml
# 73
```

기대 결과 출처: [docs:history/build_log/06_jenkins.md:531-534]

```bash
# m-k8s: latest나 태그 없는 이미지가 없는지
kubectl get pods -A -o jsonpath='{range .items[*]}{range .spec.containers[*]}{.image}{"\n"}{end}{end}' | sort -u | grep -E ':latest$|^[^:]+$'
# 아무것도 나오지 않아야 한다
```

기대 결과 근거: [docs:history/cluster_state_20261116.md:71]

```bash
# 저장소의 newTag와 실제 이미지가 같은지
grep newTag apps/petmint/kustomization.yaml apps/runshoes/kustomization.yaml
kubectl -n petmint get deploy petmint-app -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
kubectl -n runshoes get deploy runshoes -o jsonpath='{.spec.template.spec.containers[*].image}{"\n"}'
kubectl -n runshoes get cronjob runshoes-summary -o jsonpath='{..image}{"\n"}'
```

명령 출처: [docs:history/build_log/07_project_deploy.md:633-639]

## 알려진 한계

- 컨트롤러가 하나이고 w3에 묶였다. w3 정비 동안 빌드가 멈춘다 [docs:history/build_log/06_jenkins.md:504]
- 빌드 Pod에 nodeSelector가 없다. app 노드에 뜨면 앱과 메모리를 나눈다 [docs:history/build_log/06_jenkins.md:503]
- BuildKit 캐시가 emptyDir라 빌드마다 처음부터 굽는다 [docs:history/build_log/06_jenkins.md:505]
- Harbor 로봇 계정에 만료가 없다 [docs:history/build_log/06_jenkins.md:502]
- CSP가 report-only다 [docs:history/build_log/06_jenkins.md:495-501]
- 컨트롤러 이미지가 차트 기본이라 차트를 올리면 이미지도 함께 바뀐다 [docs:history/build_log/06_jenkins.md:506]
- UI에서 바꾼 Job, 자격 증명, admin 비밀번호는 재시작 때 values로 되돌아간다 [docs:history/build_log/06_jenkins.md:507]
- sed 명령이 앱 저장소 Jenkinsfile에 있어 이 저장소에서 보이지 않는다 [code:apps/petmint/kustomization.yaml:3]
- `platform/versions.yaml`은 설치기가 읽지 않는 기록이라 클러스터와 어긋날 수 있다 [code:platform/versions.yaml:3]

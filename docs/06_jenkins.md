# 06. Jenkins

Jenkins 컨트롤러를 Helm 차트로 클러스터 안(w3)에 세우고, 앱 저장소 push를 받아 BuildKit rootless로 이미지를 굽고 Harbor에 올린 뒤 ronanlab-infra의 이미지 태그를 고치는 CI를 맡겼다. Job · 자격 증명 · 트리거 · 플러그인 73개는 모두 `platform/jenkins/values.yaml` 한 파일이 정한다.

- 날짜: 2026-10-14 설치(helm revision 1), 2026-10-15 파이프라인, 2026-11-03 웹훅 · 플러그인 고정, 2026-11-10 w3 고정(revision 9), 2026-11-12 코드와 맞춤
- 범위: Jenkins 컨트롤러 · 플러그인 · JCasC · Harbor 로봇 계정 · 외부 노출 · 인프라 저장소 ronanlab-infra를 만든 까닭. 배포 흐름 전체(태그 커밋 → ArgoCD)는 [07_project_deploy.md](07_project_deploy.md), 노드 배치는 [08_scale_out.md](08_scale_out.md), 터널 설계는 [03_cloudflare_tunnel.md](03_cloudflare_tunnel.md)
- 코드: `platform/jenkins/values.yaml`, `platform/cert-manager/jenkins-certificate.yaml`, 앱 저장소 `Jenkinsfile`(`~/AI_programming/petmint-rag-chatbot/Jenkinsfile`, `~/AI_programming/runshoes/Jenkinsfile`)

## 1. 지금 구성

2026-11-12 클러스터와 `platform/jenkins/values.yaml`에서 직접 본 값이다.

| 항목 | 값 | 근거 |
| --- | --- | --- |
| Helm 릴리스 | `jenkins`(네임스페이스 `jenkins`), 차트 `jenkins-5.9.68`, 앱 2.580.1, revision 9(2026-11-10 12:03 UTC) | `helm list -A`, `helm -n jenkins history jenkins` |
| 컨트롤러 Pod | `jenkins-0` 2/2 Running, w3-k8s | `kubectl get pod -A -o wide` |
| 이미지 | `docker.io/jenkins/jenkins:2.580.1-jdk25` + 사이드카 `docker.io/kiwigrid/k8s-sidecar:2.11.2` | StatefulSet `jenkins`. values에 태그를 적지 않았다(차트 기본) |
| 배치 | `nodeSelector: node.ronanlab.dev/role: infra`(w3) | values.yaml `controller.nodeSelector`, 라벨은 `cluster/label-nodes.sh` |
| 저장소 | PVC `jenkins` local-path 8Gi, PV가 w3-k8s에 있다 | `kubectl get pvc,pv` |
| 자원 | requests cpu 500m · memory 1Gi, limits memory 2Gi | values.yaml `controller.resources` |
| 주소 | `https://jenkins.ronanlab.dev`, Ingress `jenkins`(class nginx, TLS `jenkins-tls`), Service ClusterIP | values.yaml `controller.ingress`, cert-manager `platform/cert-manager/jenkins-certificate.yaml`(letsencrypt-prod DNS-01) |
| 외부 노출 | 공용 터널(`apps/cloudflared/configmap.yaml`)의 `jenkins.ronanlab.dev` 줄. Cloudflare Access는 운영자만, `/github-webhook/` 경로만 Bypass | `apps/cloudflared/configmap.yaml`, values.yaml 주석 |
| admin 계정 | 사람이 넣은 Secret `jenkins/jenkins-admin`(키 `jenkins-admin-user` · `jenkins-admin-password`, `controller.admin.existingSecret`). 차트 기본 JCasC가 기동마다 이 값으로 admin을 박으므로 UI에서 바꾼 비밀번호는 재시작하면 사라진다 | values.yaml `controller.admin` |
| 에이전트 | `agent.enabled: true`. 빌드마다 Pod를 띄웠다 지운다. 빌드 Pod 모양은 Jenkinsfile이 정한다(배치 고정 없음) | values.yaml, Jenkinsfile |
| RBAC | `rbac.create: true`, ServiceAccount `jenkins`(jenkins 네임스페이스 안으로 제한) | values.yaml |

### 플러그인

`controller.installPlugins` 73개, 전부 `이름:버전`으로 고정했다(2026-11-03).

| 구분 | 개수 | 플러그인 |
| --- | --- | --- |
| 직접 쓰는 것 | 6 | `kubernetes:4560.vc25b_83890c34`, `workflow-aggregator:608.v67378e9d3db_1`, `git:5.11.0`, `configuration-as-code:2136.veb_3a_554550b_f`, `job-dsl:3732.v9a_c49a_61a_313`(JCasC `jobs:`로 Pipeline Job을 만든다), `github:1.47.0`(`/github-webhook/` 서명 검증 · githubPush 트리거) |
| 의존 | 67 | 위 여섯이 끌어오는 것(목록은 values.yaml) |

| values | 값 | 뜻 |
| --- | --- | --- |
| `installLatestPlugins` | `false` | 목록에 없는 의존이 생기면 최신이 아니라 요구 최소 버전을 받는다 |
| `overwritePlugins` | `true` | 기동마다 `JENKINS_HOME/plugins`를 비우고 목록으로 다시 채운다. 설치 = 목록, `helm rollback`이 플러그인 버전까지 되돌린다 |

### JCasC가 만드는 것

UI에서 만든 Job · 자격 증명은 Pod를 다시 만들면 사라지므로 모두 `controller.JCasC.configScripts`에 둔다. 블록 셋(`foreman` · `petmint` · `runshoes`)은 합쳐진다(credentials · jobs 목록이 이어 붙는다).

| 블록 | 자격 증명(id, 종류) | Job · 설정 |
| --- | --- | --- |
| `foreman` | `foreman-webhook-token`(string) | 없음. 두 앱 Jenkinsfile의 `foremanNotify`가 `POST http://192.168.122.1:8001/webhooks/jenkins`에 쓴다(2026-11-03) |
| `petmint` | `harbor-robot-petmint-jenkins`(usernamePassword, Harbor `robot$petmint+jenkins`), `ronanlab-infra-deploy-key`(SSH, ronanlab-infra 쓰기 deploy key), `github-webhook-secret`(string) | `gitHubPluginConfig.hookSecretConfigs`(SHA256). Pipeline Job `petmint-app`: `https://github.com/Gabriel-Joo/petmint-rag-chatbot.git` `*/main`, `Jenkinsfile`, 트리거 `githubPush()` + `pollSCM H/15 * * * *` |
| `runshoes` | `harbor-robot-runshoes-jenkins`(usernamePassword, Harbor `robot$runshoes+jenkins`). deploy key는 petmint 블록 것을 같이 쓴다(저장소 단위 키) | Pipeline Job `runshoes-app`: `https://github.com/Gabriel-Joo/runshoes.git` `*/main`, 트리거는 petmint와 같다 |

자격 증명 값은 사람이 넣은 Secret에서 `controller.additionalExistingSecrets`로 읽는다. 2026-11-12 `jenkins` 네임스페이스에 있는 Secret: `jenkins-admin`, `harbor-robot-jenkins`, `harbor-robot-runshoes-jenkins`, `ronanlab-infra-deploy-key`, `github-webhook-secret`, `foreman-webhook-token`, `jenkins-tls`(cert-manager). 값은 저장소에 없다.

### 빌드 Pod

두 앱 Jenkinsfile 모두 같은 모양이다(2026-11-12 확인).

| 항목 | 값 |
| --- | --- |
| 이미지 | `moby/buildkit:v0.33.1-rootless` |
| 보안 | `privileged` 없음. `runAsUser/runAsGroup 1000`, seccomp · AppArmor만 `Unconfined`, `BUILDKITD_FLAGS=--oci-worker-no-process-sandbox` |
| 자원 | requests cpu 500m · memory 1536Mi, limits memory 3Gi |
| 캐시 | `buildkitd` emptyDir(빌드마다 비어 있다) |
| 옵션 | `disableConcurrentBuilds()`, timeout 30분, 빌드 기록 30개 |

### 처음 한 번 (다시 세울 때)

값은 여기 적지 않는다. 저장소의 `platform/`을 m-k8s로 옮기는 법은 [02_metrics_storage_ingress.md](02_metrics_storage_ingress.md) 「처음 한 번」(아래는 m-k8s `~/platform-apply`에서). Secret은 helm보다 **먼저** 만든다. values가 `existingSecret` · `additionalExistingSecrets`로 이름을 부르기 때문이다.

**클러스터에만 있는 것(2026-11-12 조회, 이름 · 키만)**

| Secret(`jenkins` ns) | 키 | 값은 어디서 | 확인(값 대신 같음 여부) |
| --- | --- | --- | --- |
| `jenkins-admin` | `jenkins-admin-user`, `jenkins-admin-password` | 사람이 정한다 | |
| `harbor-robot-jenkins` | `username`, `password` | Harbor robot `petmint+jenkins`(push). 비밀번호는 robot을 만들 때 한 번만 보인다 | username = `robot$petmint+jenkins` |
| `harbor-robot-runshoes-jenkins` | `username`, `password` | Harbor robot `runshoes+jenkins`(push) | username = `robot$runshoes+jenkins` |
| `github-webhook-secret` | `secret` | 사람이 만든다. GitHub `petmint-rag-chatbot` · `runshoes` 웹훅에 같은 값 | ArgoCD `webhook.github.secret`과 다른 값 |
| `foreman-webhook-token` | `token` | foreman `.env.bridge`의 `FOREMAN_WEBHOOK_TOKEN` | 그 값과 같다. ArgoCD `argocd-notifications-secret`과도 같다 |
| `ronanlab-infra-deploy-key` | `ssh-privatekey` | `scripts/make-deploy-keys.sh`가 만든다(쓰기 키) | |

저장소 밖(사람이 대시보드에서): Harbor robot 두 개, GitHub 웹훅 두 개(`https://jenkins.ronanlab.dev/github-webhook/`), GitHub `ronanlab-infra` 쓰기 Deploy key, Cloudflare Access Bypass 앱(`/github-webhook`).

```bash
# m-k8s. 비밀값은 read -rs 로 셸 변수에 받고 표준 입력으로 넘긴다(명령 인자 · 화면에 남기지 않는다)
kubectl create namespace jenkins

read -rs P && printf %s "$P" | kubectl -n jenkins create secret generic jenkins-admin \
  --from-literal=jenkins-admin-user=admin --from-file=jenkins-admin-password=/dev/stdin; unset P
read -rs P && printf %s "$P" | kubectl -n jenkins create secret generic harbor-robot-jenkins \
  --from-literal=username='robot$petmint+jenkins' --from-file=password=/dev/stdin; unset P
read -rs P && printf %s "$P" | kubectl -n jenkins create secret generic harbor-robot-runshoes-jenkins \
  --from-literal=username='robot$runshoes+jenkins' --from-file=password=/dev/stdin; unset P
S=$(head -c 48 /dev/urandom | base64 | tr -dc A-Za-z0-9 | head -c 32)
printf %s "$S" | kubectl -n jenkins create secret generic github-webhook-secret --from-file=secret=/dev/stdin
#   GitHub petmint-rag-chatbot · runshoes → Settings → Webhooks: https://jenkins.ronanlab.dev/github-webhook/, Secret = $S, push. 끝나면 unset S
```

```bash
# 호스트: FOREMAN 토큰(ArgoCD 알림과 같은 값)
sed -n 's/^FOREMAN_WEBHOOK_TOKEN=//p' ~/AI_programming/foreman/.env.bridge | tr -d '\n' \
  | (cd ~/k8s-cluster && vagrant ssh m-k8s -c 'kubectl -n jenkins create secret generic foreman-webhook-token --from-file=token=/dev/stdin')
# 호스트: 저장소 deploy key 둘(ArgoCD 읽기 · Jenkins 쓰기). 공개 키를 GitHub ronanlab-infra → Deploy keys 에(쓰기 키만 Allow write access)
#   ssh -i <m-k8s 키> vagrant@192.168.122.10 'bash -s' < scripts/make-deploy-keys.sh
```

```bash
# m-k8s ~/platform-apply: 인증서 → helm(차트 · 버전은 2026-11-12 배포된 것과 같다)
kubectl apply -f platform/cert-manager/jenkins-certificate.yaml
helm repo add jenkins https://charts.jenkins.io && helm repo update
helm install jenkins jenkins/jenkins --version 5.9.68 -n jenkins -f platform/jenkins/values.yaml
```

- 저장소 values로 렌더한 매니페스트는 2026-11-12 배포된 것과 같다(Secret · checksum · test 빼고). 배포된 사용자 values도 저장소 파일과 같다
- jenkins 네임스페이스에는 helm `--create-namespace`가 붙이는 `name` 레이블이 없어 `kubectl create namespace`로 만든 것으로 본다
- `jenkins-admin`의 사용자 이름은 `admin`이다(2026-11-12 Secret 키 `jenkins-admin-user`가 admin과 같은지만 확인). Harbor robot의 권한은 push · pull, 만료는 두지 않았다(2절 「로봇 계정」)

## 2. 왜 이렇게 했나

### Jenkins를 직접 세우는 이유

CI 도구는 GitHub Actions가 더 쉽다. 저장소에 YAML 하나 넣으면 끝이고 서버를 관리할 필요도 없다. 그럼에도 Jenkins를 고른 이유는 두 가지다.

채용 공고를 모아보니 DevOps · 플랫폼 엔지니어 공고에서 Jenkins가 여전히 많이 언급된다. GitHub Actions와 나란히 적힌 경우가 흔하고, 사내 인프라를 쓰는 조직일수록 Jenkins를 쓴다. 그리고 Actions는 GitHub가 러너를 대신 돌려주므로 **빌드가 어디서 어떻게 실행되는지를 다룰 일이 없다.** 지금 하려는 것은 그 반대다. 빌드 파드를 직접 띄우고 권한을 주고 레지스트리에 밀어 넣는 과정 전체를 손으로 다루는 것이다.

### 특권 없이 빌드한다 (Kaniko로 계획, BuildKit rootless로 실행)

컨테이너 안에서 컨테이너 이미지를 빌드하는 것은 생각보다 까다롭다. `docker build`는 도커 데몬이 필요하고, 데몬은 리눅스 커널 기능(네임스페이스 · cgroup)을 직접 다뤄야 해서 특권이 필요하다.

| 방식 | 필요 조건 | 문제 |
| --- | --- | --- |
| DinD (Docker-in-Docker) | `privileged: true` | 그 파드가 뚫리면 노드 전체가 뚫린다 |
| 노드 소켓 마운트 | `/var/run/docker.sock` 공유 | 파드가 노드의 모든 컨테이너를 조작할 수 있다 |
| Kaniko (처음 계획) | 없음 | 설정이 다소 번거롭다 |
| BuildKit rootless (채택) | `privileged` 없음. seccomp · AppArmor 프로필만 Unconfined | rootlesskit이 사용자 네임스페이스를 만든다 |

Kaniko는 데몬 없이 사용자 공간에서 Dockerfile을 해석하고 레이어를 직접 조립한다. 특권이 필요 없다는 것이 핵심이고, 빌드 파드가 침해당해도 그 파드 안에 갇힌다.

**실제 파이프라인(2026-10-15)은 BuildKit rootless로 짰다.** 목표는 같다. `privileged` 없이, rootlesskit이 만든 사용자 네임스페이스 안에서 빌드한다. 대가로 seccomp · AppArmor 프로필만 푼다. 빌드 Pod 모양은 앱 저장소 Jenkinsfile이 정한다.

```yaml
containers:
  - name: buildkit
    image: moby/buildkit:v0.33.1-rootless
    command: ["cat"]          # 단계가 exec 로 들어올 때까지 살아 있게
    tty: true
    env:
      - name: BUILDKITD_FLAGS
        value: --oci-worker-no-process-sandbox
    securityContext:
      runAsUser: 1000
      runAsGroup: 1000
      seccompProfile: { type: Unconfined }
      appArmorProfile: { type: Unconfined }
```

`buildctl-daemonless.sh`는 부를 때마다 데몬을 새로 띄운다. 그래서 runshoes처럼 이미지가 둘(앱 · 챗봇)이어도 한 컨테이너에서 차례로 빌드한다.

**노드에 docker를 설치하지 않은 것도 같은 맥락이다.** k8s 노드는 containerd를 쓰며 docker를 함께 설치하면 충돌 소지가 있다. BuildKit rootless도 빌드 Pod 안에서 돌고 docker를 요구하지 않으므로 노드 구성을 건드릴 이유가 없다.

### 로봇 계정

Jenkins가 Harbor에 이미지를 올리려면 자격증명이 필요하다. admin 계정을 쓰면 파이프라인이 Harbor의 모든 것을 할 수 있게 된다. 프로젝트 삭제, 사용자 관리까지.

Harbor의 **로봇 계정**은 프로젝트 단위로 발급되고 권한을 개별 선택할 수 있다.

```txt
petmint 프로젝트 → Robot Accounts → New Robot Account
  권한: Repository push, pull (두 개만)
```

artifact 삭제, helm-chart, scan, tag 등은 모두 해제했다. Jenkins가 하는 일은 이미지를 올리는 것뿐이므로 딱 그만큼만 준다. runshoes 프로젝트에도 같은 모양으로 `robot$runshoes+jenkins`를 만들었다(`apps/runshoes/README.md` 「처음 만드는 순서」).

만료는 설정하지 않았다. 실무라면 기한을 두고 주기적으로 교체하는 것이 맞지만, 만료되면 어느 날 갑자기 파이프라인이 인증 실패로 멈추고 원인을 찾는 데 시간을 쓰게 된다. **"기한을 두지 않았다"가 아니라 "기한 관리 체계가 없어서 두지 않았다"**로 기록해둔다.

> 로봇 계정의 시크릿은 생성 직후 **한 번만** 표시된다. ArgoCD · Jenkins의 초기 비밀번호가 Secret에 남아 있어 언제든 다시 읽을 수 있는 것과 다르다.

### 플러그인 버전은 "작동을 확인한 것"을 적는다

|  | 버전 고정 | 결과 |
| --- | --- | --- |
| ArgoCD, kubeadm, Harbor 차트 | 단일 아티팩트 | 성공 |
| Jenkins 플러그인 | 서로 의존하는 집합 | 실패 → 설치 후 역기록 |

> **재현성의 원칙은 같지만 방법이 다르다.** 단일 아티팩트는 원하는 버전을 고르면 되지만, 의존성 그래프를 가진 집합은 해결기에게 맡긴 뒤 결과를 고정하는 순서가 맞다. "버전을 적어뒀다"가 아니라 **"작동을 확인한 버전을 적어뒀다"**가 되어야 한다.

자세한 경위는 3절 10-10단계 트러블슈팅.

### 인프라 저장소를 클러스터 단위로 묶은 이유

values 파일이 m-k8s 홈 디렉토리에만 있어 VM이 사라지면 함께 없어진다. GitHub private 저장소 `ronanlab-infra`를 만들어 버전 관리를 시작했다(3절 「인프라 저장소 ronanlab-infra」).

**프로젝트별이 아니라 클러스터 단위로 묶은 이유**: Harbor · Jenkins · ArgoCD · 터널은 펫민트의 것이 아니라 클러스터의 것이다. runshoes를 이주해와도 같은 Jenkins로 빌드하고 같은 Harbor에 올린다. 결정적인 것은 터널 ConfigMap이다. 공개 호스트 전부(그때 다섯: petmint, argocd, harbor, jenkins, runshoes. runshoes는 2026-10-18 추가. 2026-11-12 지금은 grafana · prometheus까지 일곱)가 한 파일(`apps/cloudflared/configmap.yaml`)에 들어 있어 프로젝트별로 쪼갤 수 없다. 어느 프로젝트 저장소에 넣어도 어색하다면 클러스터 저장소가 맞다는 뜻이다.

앱 매니페스트는 `apps/<앱>/` 아래에 두고, ArgoCD는 이 저장소 하나만 등록해 폴더별 Application으로 분리한다([07_project_deploy.md](07_project_deploy.md)).

**앱 저장소와 매니페스트 저장소를 나눈 이유**: 한 저장소에 두면 Jenkins가 태그를 갱신하며 push한 것이 다시 webhook을 트리거해 빌드가 무한히 돈다(3절 「이후: 파이프라인」 표의 마지막 줄).

## 3. 진행 기록

### 10-9단계: 차트 저장소와 버전 (2026-10-14)

```bash
helm repo add jenkins https://charts.jenkins.io
helm repo update
helm search repo jenkins/jenkins --versions | head -5
```

```txt
NAME             CHART VERSION   APP VERSION
jenkins/jenkins  5.9.68          2.580.1
jenkins/jenkins  5.9.67          2.580.1
jenkins/jenkins  5.9.65          2.568.3
```

차트 5.9.68 / Jenkins 2.580.1로 고정. 2026-11-12까지 9번 upgrade했지만 차트 버전은 그대로다.

> **Helm 저장소는 머신마다 따로 관리된다.** 처음에 호스트에서 `helm repo add`를 하고 m-k8s에서 `helm install`을 시도해 `repo jenkins not found`가 났다. 저장소 목록은 각 머신의 `~/.config/helm/`에 저장되며 공유되지 않는다.

이 프로젝트는 명령을 실행하는 위치가 두 곳으로 나뉜다.

| 머신 | 있는 도구 |
| --- | --- |
| 호스트 (kopo17) | `cloudflared`, `docker`, `vagrant` |
| m-k8s | `kubectl`, `helm` |

### 10-10단계: values.yaml

그때(2026-10-14)의 values다. 지금 values는 1절(플러그인 73개 · JCasC · nodeSelector · TLS · admin Secret이 더해졌다).

```yaml
controller:
  jenkinsUrlProtocol: https
  jenkinsUrl: https://jenkins.ronanlab.dev

  ingress:
    enabled: true
    ingressClassName: nginx
    hostName: jenkins.ronanlab.dev
    annotations:
      nginx.ingress.kubernetes.io/ssl-redirect: "false"

  serviceType: ClusterIP

  installPlugins:
    - kubernetes:4560.vc25b_83890c34
    - workflow-aggregator:608.v67378e9d3db_1
    - git:5.11.0
    - configuration-as-code:2136.veb_3a_554550b_f

  resources:
    requests:
      cpu: 500m
      memory: 1Gi
    limits:
      memory: 2Gi

persistence:
  enabled: true
  storageClass: local-path
  size: 8Gi

agent:
  enabled: true

rbac:
  create: true

serviceAccount:
  create: true
  name: jenkins
```

| 값 | 기본값대로 두면 | 이유 |
| --- | --- | --- |
| `jenkinsUrl` | 내부 Service 주소가 박힌다 | Jenkins가 만드는 링크와 webhook 주소의 기준. Harbor의 `externalURL`과 같은 역할 |
| `serviceType: ClusterIP` | LoadBalancer로 생성돼 **Pending에서 멈춤** | Harbor와 같은 함정. 이 환경엔 클라우드 로드밸런서가 없다 |
| `agent.enabled: true` | (없음) | 빌드마다 파드를 띄웠다 지우는 구조. 빌드 Pod 모양은 Jenkinsfile의 `agent { kubernetes { yaml … } }`가 정한다(BuildKit 컨테이너) |
| `rbac.create` + ServiceAccount | (없음) | Jenkins가 파드를 생성할 권한. jenkins 네임스페이스 안으로 제한된다 |
| `persistence.storageClass` | (없음) | 잡 설정과 빌드 이력이 쌓인다. 상태를 갖는 앱이므로 노드에 묶이는 것이 맞다 |

#### 트러블슈팅: 버전을 고정했더니 설치가 깨졌다

**증상**

```txt
jenkins-0   0/2   Init:Error   1 (8s ago)   44s
```

init 컨테이너가 반복 실패했다. `describe`의 Events에는 `BackOff restarting failed container`만 있고 원인이 없다. 이미지 pull은 성공했으므로 네트워크 문제도 아니다.

**로그를 보려는데 컨테이너가 이미 정리돼 접근할 수 없었다.**

```bash
kubectl -n jenkins logs jenkins-0 -c init --previous
# unable to retrieve container logs for containerd://a0e5172...
```

BackOff 주기에 맞춰 `-f`로 붙어 다음 시도의 출력을 잡았다.

```bash
kubectl -n jenkins logs -f jenkins-0 -c init
```

```txt
Multiple plugin prerequisites not met:
Plugin kubernetes:4400.v2c2b_6e1e3bcd has unresolvable dependencies
Plugin workflow-aggregator:608.v67378e9d3db_1 (via ...->credentials:1514)
  depends on configuration-as-code:2117.vc05a_0b_e6b_f4e,
  but there is an older version defined on the top level
  - configuration-as-code:1944.vb_79a_9be2a_a_1
Plugin git:5.7.0 (via credentials:1514) depends on configuration-as-code:2117...
```

**원인**

`installPlugins`에 적은 버전들이 서로 호환되지 않았다. 특히 `configuration-as-code`를 1944로 고정했는데, 다른 플러그인들이 2117 이상을 요구하면서 의존성 해결 자체가 막혔다.

ArgoCD · kubeadm · Harbor 차트에서 버전 고정이 잘 통했기에 플러그인에도 같은 원칙을 적용했지만, **이 경우엔 고정이 오히려 설치를 막았다.** 플러그인은 서로 의존하므로 하나만 어긋나도 전체가 풀리지 않는다. 버전을 고정하려면 호환되는 조합 전체를 알아야 하는데, 그 조합은 설치해보기 전에는 알 수 없다.

**해결**

버전을 떼고 이름만 남겨 설치한다.

```yaml
  installPlugins:
    - kubernetes
    - workflow-aggregator
    - git
    - configuration-as-code
```

설치가 통과한 뒤, Manage Jenkins → Plugins → Installed에서 **실제로 설치된 버전**을 확인해 values에 역으로 기록했다(위 values). 이 조합은 추측이 아니라 작동이 확인된 값이다.

### 10-11단계: 외부 노출

터널 ConfigMap에 `jenkins.ronanlab.dev` 추가. Harbor와 동일한 절차다.

```bash
cloudflared tunnel --config /dev/null route dns \
  02ad6a13-ce45-4262-a32a-40241bf034dc jenkins.ronanlab.dev
```

```txt
ERR Configuration file /dev/null was empty
INF Added CNAME jenkins.ronanlab.dev which will route to this tunnel
    tunnelID=02ad6a13-ce45-4262-a32a-40241bf034dc
```

`ERR`로 찍히지만 **의도한 결과다.** 빈 파일을 읽혀 기본 config의 `tunnel: ollama-tunnel`을 무시하게 만든 것이고, 바로 다음 줄에서 올바른 터널 ID가 확인된다.

### 10-12단계: 검증

```bash
curl -I https://jenkins.ronanlab.dev
```

```txt
HTTP/2 403
x-jenkins: 2.580.1
x-you-are-authenticated-as: anonymous
x-required-permission: hudson.model.Hudson.Read
```

**403이 성공 신호다.** 9단계에서 404를 "요청이 끝까지 도달했다는 증거"로 읽은 것과 같은 상황인데([03_cloudflare_tunnel.md](03_cloudflare_tunnel.md)), 여기서는 더 명확하다.

- `x-jenkins: 2.580.1`: Jenkins 본인이 응답했다. Cloudflare나 nginx가 가로막은 것이 아니다
- `x-you-are-authenticated-as: anonymous`: curl이 로그인하지 않았을 뿐
- `x-required-permission`: 읽기 권한이 필요한데 없어서 거절

그때의 길(터널 이름은 2026-10-18 `petmint-tunnel`에서 `ronanlab-tunnel`로 바뀌었고 Pod는 `cloudflared` 네임스페이스로 옮겼다, `apps/cloudflared/README.md`):

```txt
jenkins.ronanlab.dev
  → Cloudflare 엣지 (NRT, 도쿄)
  → petmint-tunnel (클러스터 내 Pod 2개)
  → nginx-ingress (Host 헤더로 분기)
  → jenkins-0
```

브라우저 접속과 `admin` 로그인 확인. 그때 초기 비밀번호는 차트가 만든 Secret `jenkins`에 있었다.

```bash
kubectl -n jenkins get secret jenkins \
  -o jsonpath="{.data.jenkins-admin-password}" | base64 -d; echo
```

ArgoCD의 `argocd-initial-admin-secret`과 같은 구조이며, `base64 -d`가 필요한 이유도 같다. 2026-11-12 지금은 차트가 이 Secret을 만들지 않는다. admin 비밀번호는 사람이 넣은 Secret `jenkins-admin`에 있다(1절, `controller.admin.existingSecret`).

> **9단계 설계가 세 번째로 검증됐다.** ArgoCD · Harbor · Jenkins 모두 터널에 hostname 한 줄 추가가 전부였고, Harbor와 Jenkins는 Ingress조차 차트가 만들어줬다.

### 인프라 저장소 ronanlab-infra

처음 구조:

```txt
ronanlab-infra/
  platform/
    harbor/values.yaml
    jenkins/values.yaml
  .gitignore
```

2026-11-12 지금 구조(worktree에서 `ls`로 확인, docs는 노션에서 옮기는 중인 파일 포함):

```txt
ronanlab-infra/
  CLAUDE.md                 저장소에서 도는 세션 규칙
  README.md
  bootstrap/root-app.yaml   루트 Application(App of Apps). 이것만 사람이 kubectl apply
  apps/                     ArgoCD가 배포하는 것(Application 5개 + 루트)
    cloudflared/            클러스터 공용 터널(수동 Sync)
    harbor-backup/          Harbor DB 백업 CronJob
    monitoring/             Prometheus · Grafana · Loki · Alloy · node-exporter · kube-state-metrics · json-exporter(w4)
    petmint/                펫퍼민트 앱 + MySQL(Primary · Replica) + 백업 CronJob
    runshoes/               런슈즈 앱 + MySQL(Primary · Replica) + 리뷰 요약 CronJob + runbooks/
  platform/                 ArgoCD 밖, 사람이 Helm · kubectl로 넣은 기반
    argocd/  cert-manager/  coredns/  harbor/  ingress-nginx/  jenkins/  metallb/
  cluster/                  Vagrantfile · setup-node.sh(호스트 ~/k8s-cluster 의 사본) · label-nodes.sh(노드 역할 라벨, 저장소에만 있다)
  scripts/                  make-deploy-keys.sh · host-nfs-harbor-backup-setup.sh · host-gpu-exporter.sh · mysql-replica-seed.sh · mysql-replica-check.sh
  docs/                     인프라 문서
    README.md  TODO.md
    00_server.md  kubernetes_install.md  01_cluster.md ~ 09_monitoring.md
    history/                지난 구성(vcluster 시절 터널)
    runbooks/mysql-replica.md
  .gitignore
```

**커밋 전 `harborAdminPassword` 줄을 제거했다.** 재설치 시에는 명령줄로 넘긴다.

```bash
helm install harbor harbor/harbor \
  --namespace harbor --version 1.19.2 \
  -f platform/harbor/values.yaml \
  --set harborAdminPassword='...'
```

`.gitignore`는 9단계의 "자격증명 파일은 `.gitignore`로 관리한다"를 실행한 것이다(2026-11-12 내용 그대로).

```txt
*credentials*.json
*secret*.yaml
secrets/
*.key
*.pem
```

cloudflared credentials.json, Harbor 로봇 계정, 이후 Jenkins 토큰까지 이 패턴에 걸린다.

### 이후: 파이프라인 (2026-10-15)

이 단계에서는 컨트롤러까지만 세웠다. 빌드할 Dockerfile이 아직 없었기 때문이다. 파이프라인은 2026-10-15 펫퍼민트 Dockerfile과 함께 구성했고, 런슈즈는 2026-10-18 이주하며 같은 모양으로 붙였다. 당시 계획과 실제(배포 흐름 전체는 [07_project_deploy.md](07_project_deploy.md)):

| 항목 | 내용 |
| --- | --- |
| 빌드 파드 템플릿 | 계획: Jenkins 에이전트를 Kaniko 이미지로 → 실제: Jenkinsfile의 Pod 템플릿에 BuildKit rootless 컨테이너(2절) |
| Harbor 자격증명 | 계획: `kubernetes.io/dockerconfigjson` Secret으로 주입 → 실제: 로봇 값을 담은 Secret을 JCasC가 Jenkins 자격 증명(usernamePassword)으로 만들고, Jenkinsfile이 `withCredentials`로 쓴다. 노드가 pull할 때 쓰는 로봇은 따로 뒀다(push 권한을 노드에 주지 않게) |
| Jenkinsfile | 앱 저장소에 둔다(그대로). Job · 자격 증명 · 트리거는 `platform/jenkins/values.yaml`의 JCasC + job-dsl이 만든다. UI에서 만든 것은 Pod를 다시 만들면 사라진다 |
| GitHub webhook | `jenkins.ronanlab.dev/github-webhook/`, 2026-11-03부터. 그 전에는 Access에 막혀 SCM 폴링 2분이었다. Access는 이 경로만 비켜 두고 서명(HMAC SHA-256)이 지킨다. 안전망 폴링 15분 |
| 이미지 태그 갱신 | `ronanlab-infra`의 매니페스트를 고쳐 push → ArgoCD가 감지(그대로). `newTag` 한 줄을 `sed`로 바꾸고 `grep`으로 다시 센 뒤 push. ronanlab-infra는 `sh 'git clone'`으로 받는다([07_project_deploy.md](07_project_deploy.md) 「트러블슈팅: 태그 push가 빌드를 다시 부른다」) |

#### 트러블슈팅: runshoes Job이 목록에 안 보인다 (2026-10-18)

**증상**: runshoes Job을 처음 더한 `helm upgrade` 뒤, `jobs/runshoes-app/config.xml`은 디스크에 있는데 API로는 404였다.

**원인**: 기동 중 JCasC가 Job을 만든 직후 Jenkins가 디스크의 Job 목록으로 덮었다.

**해결**: `POST /configuration-as-code/reload`(관리 → Configuration as Code → Reload) 한 번이면 나타난다(values.yaml 주석).

### 이후: 웹훅 · FOREMAN 알림 (2026-11-03)

- GitHub 웹훅: 두 앱 저장소에 사람이 GitHub에서 손으로 걸었다(플러그인이 훅을 관리하지 않는다, 토큰 없음). 공유 시크릿 `github-webhook-secret` 하나를 두 저장소가 같이 쓴다. ArgoCD 웹훅(ronanlab-infra)은 다른 값이다
- FOREMAN 빌드 알림: Jenkinsfile의 `foremanNotify`가 시작 · 끝을 알린다. 실패해도 빌드 결과에 영향이 없다. Jenkins API 토큰(관리자 권한) 대신 알림 전용 토큰을 쓴 까닭은 새도 가짜 빌드 이벤트를 넣는 정도라서다

### 이후: 플러그인 73개 전부 고정 (2026-11-03)

10-10단계 values의 네 줄만 고정해서는 부족했다. 차트 기본(`installLatestPlugins: true`)이 재시작할 때마다 **의존 플러그인**을 최신으로 올려, 빌드가 어느 날 깨져도 무엇이 바뀌었는지 알 수 없었다(2026-11-02 `helm upgrade` 때 의존 10개가 같이 올랐다).

| values | 값 | 뜻 |
| --- | --- | --- |
| `installPlugins` | 73개 전부 `이름:버전`. 직접 쓰는 6개 + 의존 67개 | 실행 중이던 목록 그대로(`/pluginManager/api/json`에서 뽑았다) |
| `installLatestPlugins` | false | 목록에 없는 의존이 생기면 최신이 아니라 요구 최소 버전 |
| `overwritePlugins` | true | 기동마다 플러그인 디렉터리를 목록으로 다시 채운다. 설치 = 목록 |

10-10단계의 "설치 후 역기록"을 의존성까지 넓힌 것이다. 플러그인을 올릴 때는 올릴 것과 그 의존을 목록에서 같이 고치고 `helm upgrade`한다. 목록 뽑는 법은 펫퍼민트 저장소 `~/AI_programming/petmint-rag-chatbot/docs/02_pipeline/14_deployment.md` 「1-23. Jenkins 플러그인 버전 고정 (2026-11-03)」.

### 이후: 문서만 바뀐 빌드는 건너뛴다 (2026-11-09)

바뀐 파일(직전 성공 빌드의 커밋 → 이번 커밋)이 모두 `docs/` · `data/review/` · 루트 `*.md`(펫퍼민트 기준)이면 빌드는 SUCCESS로 끝내고 이미지 빌드 · 태그 커밋을 건너뛴다. 손으로 누른 빌드, 직전 성공 커밋이 없거나 못 찾을 때는 늘 빌드한다(`~/AI_programming/petmint-rag-chatbot/Jenkinsfile` 머리 주석). 자세한 것은 [07_project_deploy.md](07_project_deploy.md) 「트러블슈팅: 태그 push가 빌드를 다시 부른다」.

### 이후: w3에 고정 (2026-11-10)

`controller.nodeSelector: node.ronanlab.dev/role: infra`를 넣고 `helm upgrade`(revision 9). PVC(local-path)가 w3에 있어 원래도 w3에서만 떴다. 빌드 Pod(BuildKit)는 여기서 고정하지 않는다. 배치 · 재기동 기록은 [08_scale_out.md](08_scale_out.md).

## 4. 남은 한계

- **CSP(Content Security Policy)를 켜지 않았다.** Jenkins가 CSP 활성화를 권고하는 알림을 띄운다. CSP는 브라우저에 "어디서 온 스크립트만 실행하라"를 지시해 XSS의 영향을 줄이는 헤더로, Jenkins는 구 플러그인 호환성 때문에 기본적으로 꺼둔다.
  실제로는 `content-security-policy-report-only` 상태다. **규칙을 적용하지 않고 위반만 기록**하는 모드이며, 10-12단계 `curl` 응답 헤더에서도 확인된다.
  지금 켜지 않은 이유:
  - 일부 플러그인 UI가 깨질 수 있다(특히 HTML 리포트를 뿌리는 종류)
  - 파이프라인을 구성하며 플러그인이 더 추가될 예정이라, 그때 문제가 생기면 CSP 때문인지 구분이 어려워진다

  플러그인 구성이 확정된 뒤 enforce로 전환하고 깨지는 것이 있는지 확인한다. 모르고 두는 것과 알고 미루는 것은 다르다
- **로봇 계정에 만료가 없다.** 기한 관리 체계가 없어서 두지 않았다(2절 「로봇 계정」)
- **빌드 Pod 배치가 고정되지 않았다.** Jenkinsfile(앱 저장소)의 Pod 템플릿에 nodeSelector가 없다. 빌드(상한 3Gi)가 app 노드에 뜨면 앱과 메모리를 나눈다([08_scale_out.md](08_scale_out.md))
- **컨트롤러는 하나, w3에 묶였다.** w3를 정비하는 동안 빌드가 멈춘다(떠 있는 앱은 영향 없음)
- **BuildKit 캐시가 없다.** 캐시가 emptyDir라 빌드마다 처음부터 굽는다
- **컨트롤러 이미지 태그는 values에 적지 않았다.** 차트 5.9.68 기본(`2.580.1-jdk25`)을 쓴다. 차트를 올리면 이미지도 같이 바뀐다
- UI에서 Job · 자격 증명 · admin 비밀번호를 바꾸면 재시작 때 values(JCasC)로 되돌아간다. 바꿀 것은 values · Secret에서 바꾼다

## 5. 확인 방법

m-k8s에서(`cd ~/k8s-cluster && vagrant ssh m-k8s`):

```bash
helm list -n jenkins
# jenkins  jenkins  9  ...  deployed  jenkins-5.9.68  2.580.1

kubectl -n jenkins get pod jenkins-0 -o wide
# jenkins-0  2/2  Running  ...  w3-k8s

kubectl -n jenkins get pvc jenkins
# jenkins  Bound  ...  8Gi  RWO  local-path

kubectl -n jenkins get sts jenkins -o jsonpath='{.spec.template.spec.containers[*].image}{"\n"}'
# docker.io/jenkins/jenkins:2.580.1-jdk25 docker.io/kiwigrid/k8s-sidecar:2.11.2

kubectl -n jenkins get secret
# jenkins-admin · harbor-robot-jenkins · harbor-robot-runshoes-jenkins · ronanlab-infra-deploy-key · github-webhook-secret · foreman-webhook-token · jenkins-tls (이름만 본다)
```

values 쪽(저장소에서):

```bash
awk '/installPlugins:/{f=1;next} f&&/^  [a-z]/{f=0} f&&/^    - /{n++} END{print n}' platform/jenkins/values.yaml
# 73
```

바깥에서(호스트):

```bash
curl -sI https://jenkins.ronanlab.dev | head -1
# HTTP/2 302, location 이 https://<팀>.cloudflareaccess.com/... (2026-11-12 확인)
# Access 로그인으로 보내면 터널 · Access가 정상이다(운영자만). 10-12단계의 403은 Access를 걸기 전 기록이다
```

Jenkins UI(관리 → Plugins → Installed)에서 설치된 플러그인 수가 73인지, Job 목록에 `petmint-app` · `runshoes-app` 둘이 있는지 본다.

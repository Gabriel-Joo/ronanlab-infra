# 07. 프로젝트 배포

두 앱(펫퍼민트 · 런슈즈)을 클러스터에 올린 기록이다. 앱 저장소 push 한 번이 Jenkins 빌드 → Harbor push → ronanlab-infra 태그 커밋 → ArgoCD 자동 Sync → 롤링으로 이어지고, 클러스터에는 상태 없는 앱 Pod 2개(w1 · w2)와 MySQL Primary(w1) · Replica(w2)가 올라가 있다.

- 날짜: petmint 2026-10-16, runshoes 2026-10-18(학교 vcluster에서 이주), 2026-11-02 App of Apps, 2026-11-10 replicas 2 · 롤링 방식 · MySQL Replica, 2026-11-11 petmint 자동 Sync, 2026-11-12 코드와 맞춤
- 범위: 네임스페이스 · Secret → 매니페스트 · ArgoCD Application → Jenkins · Harbor · ArgoCD로 잇는 배포 흐름 → MySQL StatefulSet · PVC → Ingress · 터널 · 도메인 → 앱 로그인 · ConfigMap 플래그. Jenkins 자체는 [06_jenkins.md](06_jenkins.md), 노드 배치 · Replica · 정비 절차는 [08_scale_out.md](08_scale_out.md), 모니터링은 [09_monitoring.md](09_monitoring.md), 터널 설계는 [03_cloudflare_tunnel.md](03_cloudflare_tunnel.md)
- 코드: `apps/petmint/`, `apps/runshoes/`, `apps/cloudflared/`, `bootstrap/root-app.yaml`, 앱 저장소 `Jenkinsfile`(`~/AI_programming/petmint-rag-chatbot/Jenkinsfile`, `~/AI_programming/runshoes/Jenkinsfile`)
- 앱별 운영 문서: [apps/petmint/README.md](../apps/petmint/README.md), [apps/runshoes/README.md](../apps/runshoes/README.md). 처음 만드는 순서 · 되돌리기 절차는 그 README가 원본이다

## 1. 지금 구성

2026-11-12 09:18 KST 클러스터 조회와 저장소 파일에서 직접 본 값이다.

### 두 앱

| 항목 | petmint (펫보험 상담 RAG) | runshoes (러닝화 아카이브) |
| --- | --- | --- |
| 네임스페이스 | `petmint` | `runshoes` |
| 앱 | Deployment `petmint-app`: FastAPI + React 빌드물 한 컨테이너(:8000) | Deployment `runshoes`: Spring Boot(React 빌드물 포함, :3000) + 챗봇 사이드카(파이썬 WebSocket, :8766) |
| 이미지(태그는 2026-11-12 값) | `harbor.ronanlab.dev/petmint/petmint-app:574b3f50acf8` | `harbor.ronanlab.dev/runshoes/runshoes:4f57bc0e1537` · `runshoes-chatbot:4f57bc0e1537`(같은 태그) |
| Pod 배치 | 2개, w1 · w2(`nodeSelector node.ronanlab.dev/role: app` + required anti-affinity) | 2개, w1 · w2(같은 방식) |
| 롤링 | `maxSurge: 0`, `maxUnavailable: 1`(2026-11-10~) | `maxSurge: 0`, `maxUnavailable: 1`(2026-11-10~) |
| PDB | `petmint-app` minAvailable 1 | `runshoes` minAvailable 1 |
| MySQL | Primary StatefulSet `mysql`(mysql-0, w1) + Replica `mysql-replica`(mysql-replica-0, w2), `mysql:8.0.46`, local-path 10Gi씩. DB 둘(petmint, insurance\_core) | Primary `runshoes-mysql`(w1) + Replica `runshoes-mysql-replica`(w2), `mysql:8.0.46`, local-path 2Gi씩. DB `runshoes` |
| 그 밖의 볼륨 | 약관 · 시드: 호스트 NFS 읽기 전용 PV 3개(`petmint-chunks` · `petmint-graph` · `petmint-fixtures`), 백업: NFS 쓰기 PV `petmint-backup` 5Gi | 없음 |
| CronJob | `mysql-backup` `30 3 * * *` Asia/Seoul(mysqldump) | `runshoes-summary` `30 3 * * *` Asia/Seoul(리뷰 요약 배치, 앱과 같은 이미지) |
| 스키마 | 초기화 Job `petmint-init-db`(Sync hook, `db.migrate`) | 앱이 기동할 때 Flyway |
| GPU | 호스트 Ollama · Milvus · search-service를 `192.168.122.1`로 직접 부른다 | 호스트 Ollama를 같은 주소로 부른다(리뷰 요약 · 챗봇) |
| 공개 주소 | `petmint.ronanlab.dev`(Access 없음, 앱 로그인) | `runshoes.ronanlab.dev`(Access 없음, 공개 사이트) |
| ArgoCD Sync | **자동**(2026-11-11~, 그 전은 수동). prune · selfHeal 끔 | 자동(스키마를 바꾸는 배포 때만 끈다). prune · selfHeal 끔 |
| Secret(이름만) | `harbor-pull` · `insurance-seed-db` · `mysql-repl` · `mysql-root` · `petmint-db` | `harbor-pull` · `mysql-repl` · `runshoes-auth` · `runshoes-mysql` |

MySQL Replica는 Primary의 binlog를 받아 따라간다. 앱은 Replica를 보지 않고(Service `mysql` · `runshoes-mysql`은 Primary만 고른다) 자동 전환은 없다. 승격은 사람이 [runbooks/mysql-replica.md](runbooks/mysql-replica.md)대로 한다. 배치를 왜 이렇게 했는지는 [08_scale_out.md](08_scale_out.md).

### ArgoCD Application (6개)

| Application | 경로 | Sync | 비고 |
| --- | --- | --- | --- |
| `root` | `apps`(`*/app.yaml`만) | 자동 | App of Apps. 자식의 `spec.syncPolicy`는 덮지 않는다 |
| `petmint` | `apps/petmint` | 자동(2026-11-11~) | |
| `runshoes` | `apps/runshoes` | 자동 | |
| `monitoring` | `apps/monitoring` | 자동(2026-11-11~) | [09_monitoring.md](09_monitoring.md) |
| `harbor-backup` | `apps/harbor-backup` | 자동 | CronJob `harbor-db-backup` `45 3 * * *` |
| `cloudflared` | `apps/cloudflared` | **수동** | 터널이 깨지면 공개 주소 7개가 한꺼번에 안 보인다 |

모두 `targetRevision: main`, prune 끔, finalizer 없음, `CreateNamespace=false`. 자동 Sync를 켜고 끄는 실제 스위치는 클러스터의 `kubectl patch`이고 `app.yaml`은 기록이다(`bootstrap/root-app.yaml` 머리 주석).

### Ingress (7개) · 터널 호스트 (7개)

| 네임스페이스 | Ingress | 호스트 | TLS | Access |
| --- | --- | --- | --- | --- |
| argocd | argocd-server | argocd.ronanlab.dev | argocd-ingress-tls | 운영자만 |
| harbor | harbor-ingress | harbor.ronanlab.dev | harbor-tls | 운영자만 |
| jenkins | jenkins | jenkins.ronanlab.dev | jenkins-tls | 운영자만(`/github-webhook/`만 Bypass) |
| monitoring | grafana | grafana.ronanlab.dev | grafana-tls | 운영자만(+ Grafana 로그인) |
| monitoring | prometheus | prometheus.ronanlab.dev | prometheus-tls | 운영자만 |
| petmint | petmint-app | petmint.ronanlab.dev | 없음 | 없음 |
| runshoes | runshoes | runshoes.ronanlab.dev | 없음 | 없음 |

터널 `ronanlab-tunnel`(`02ad6a13-ce45-4262-a32a-40241bf034dc`)의 ConfigMap(`apps/cloudflared/configmap.yaml`)에 위 일곱 호스트가 있고 모두 `https://ingress-nginx-controller.ingress-nginx.svc.cluster.local:443`으로 간다. cloudflared Pod 2개(w1 · w2). Access 열은 2026-11-12 `curl -sI`로 본 응답(302 → `cloudflareaccess.com`이면 Access, 200이면 없음)이다.

## 2. 왜 이렇게 했나

### 두 프로젝트가 무엇을 올리나

GPU를 쓰는 것은 전부 호스트에 남고, 클러스터에는 **상태 없는 앱 + MySQL**만 올라간다. 05번에서 정리한 "상태를 가진 것은 노드에 묶이고, 상태 없는 앱은 어느 노드에서든 뜬다"([05_harbor.md](05_harbor.md))를 그대로 적용한 배치다.

| 항목 | petmint | runshoes |
| --- | --- | --- |
| 앱 저장소 | `petmint-rag-chatbot` | `runshoes` |
| 상태 | MySQL 하나에 DB 둘(petmint, insurance\_core) + 약관 파일(호스트 NFS) | MySQL 하나(runshoes) |
| 스키마 | 초기화 Job(`db.migrate`) | 앱이 기동할 때 Flyway |

### 네임스페이스와 Secret은 사람이 만든다

ArgoCD는 `CreateNamespace=true` 한 줄이면 네임스페이스까지 만들어 준다. 쓰지 않았다.

| 방식 | 문제 |
| --- | --- |
| ArgoCD가 네임스페이스를 소유 | Application 삭제 · prune 한 번에 네임스페이스가 지워지고, 그 안의 Secret(사람이 넣은 DB 비밀번호 · pull 자격증명)도 같이 사라진다 |
| 사람이 만든다 (채택) | 처음 한 번 손이 더 간다 |

Secret은 git에 두지 않는다. 각 앱 디렉터리의 `scripts/create-secrets.sh`가 무작위 값을 만들어 클러스터에 직접 넣는다. 06번의 `.gitignore` 원칙([06_jenkins.md](06_jenkins.md))을 매니페스트 단계에서도 지킨 것이다. 매니페스트에는 Secret **이름과 키**만 있다.

### 매니페스트는 ronanlab-infra 한 곳에

06번 끝에서 정한 대로 앱 저장소와 매니페스트 저장소를 나눴다. 앱 매니페스트는 `ronanlab-infra/apps/<앱>/`, 클러스터 공용(Harbor · Jenkins · MetalLB · cert-manager 등)은 `platform/`이다. 저장소 전체 구조는 [06_jenkins.md](06_jenkins.md) 「인프라 저장소 ronanlab-infra」.

```txt
ronanlab-infra/
  bootstrap/root-app.yaml     루트 Application. 이것만 사람이 kubectl apply (한 번)
  apps/
    petmint/                  app.yaml + 매니페스트
    runshoes/                 app.yaml + 매니페스트
    cloudflared/              클러스터 공용 터널
    harbor-backup/            Harbor DB 백업
    monitoring/               모니터링(09)
  platform/                   ArgoCD 밖(Helm · kubectl로 넣은 기반)
```

**App of Apps (2026-11-02)**: 처음에는 Application을 앱마다 `kubectl apply`로 넣었다. 지금은 루트 Application 하나가 `apps/*/app.yaml`을 읽어 Application을 만든다. 새 앱은 폴더를 넣고 push하면 3분 안에 Application이 생긴다.

### 이미지 태그를 다루는 방식

| 값 | 다르게 하면 | 이유 |
| --- | --- | --- |
| 태그 = 커밋 해시 12자리 | `latest`면 롤링 중 어느 Pod가 무엇을 도는지 알 수 없다 | 태그로 코드를 찾아갈 수 있다. 같은 커밋이면 같은 태그 |
| 태그를 kustomization 한 줄에 | Deployment · Job · CronJob에 흩어 쓰면 Jenkins가 여러 곳을 고쳐야 한다 | 초기화 Job · 요약 CronJob도 같은 이미지라, 한 줄이 셋을 함께 바꾼다 |
| Namespace를 kustomization에 넣지 않음 | ArgoCD가 소유하게 된다 | 위 「네임스페이스와 Secret은 사람이 만든다」 |

### 저장소 접근 키를 나눈다

저장소는 private이라 ArgoCD는 **읽기 전용 deploy key**(Secret `argocd/repo-ronanlab-infra`)로, Jenkins는 **쓰기 deploy key**(Secret `jenkins/ronanlab-infra-deploy-key`)로 따로 접근한다(`scripts/make-deploy-keys.sh`). 한쪽 키가 새도 다른 권한은 따라가지 않는다.

### Harbor에 닿는 길은 두 가지다

| 누가 | 어떻게 | 왜 |
| --- | --- | --- |
| Jenkins 빌드 Pod (push) | CoreDNS가 `harbor.ronanlab.dev`를 ingress-nginx 내부 Service로 돌린다(`platform/coredns/configmap.yaml`) | 공개 주소로 나가면 Cloudflare Access에 막힌다 |
| 노드의 kubelet · containerd (pull) | 노드 `/etc/hosts`의 `192.168.122.240 harbor.ronanlab.dev`(MetalLB VIP) | kubelet은 클러스터 DNS를 쓰지 않는다 |

VIP 경로의 TLS는 cert-manager가 Let's Encrypt(DNS-01)로 받은 정식 인증서다. 05번에서 TLS를 Cloudflare에만 맡기며 피했던 "노드 containerd에 CA 배포"를 하지 않고도 검증을 켠 채 당긴다.

### 앱 Pod 두 개를 서로 다른 노드에

세션 · 상태가 DB에 있어 Pod를 늘려도 된다. required anti-affinity로 둘을 같은 노드에 두지 않고, PDB로 drain 때 둘을 한꺼번에 내보내지 않는다. 노드 하나가 죽어도 다른 Pod가 받는다. 롤링을 `maxSurge 0 / maxUnavailable 1`로 바꾼 까닭은 3절 11-6단계.

## 3. 진행 기록

### 11-1단계: 네임스페이스와 Secret

m-k8s 안에서(처음 만드는 순서 전체는 [apps/petmint/README.md](../apps/petmint/README.md) 「처음 만드는 순서 (빈 클러스터에서)」, [apps/runshoes/README.md](../apps/runshoes/README.md) 「처음 만드는 순서」):

```bash
kubectl create namespace petmint
HARBOR_USER='robot$petmint+pull' HARBOR_PASSWORD=... apps/petmint/scripts/create-secrets.sh

kubectl create namespace runshoes
HARBOR_USER='robot$runshoes+pull' HARBOR_PASSWORD=... apps/runshoes/scripts/create-secrets.sh
```

```bash
kubectl -n petmint get secret; kubectl -n runshoes get secret
```

```txt
petmint    harbor-pull         kubernetes.io/dockerconfigjson
petmint    insurance-seed-db   Opaque
petmint    mysql-root          Opaque
petmint    petmint-db          Opaque
runshoes   harbor-pull         kubernetes.io/dockerconfigjson
runshoes   runshoes-auth       Opaque
runshoes   runshoes-mysql      Opaque
```

2026-11-10 Replica를 넣으며 두 네임스페이스에 복제 계정 Secret `mysql-repl`이 더해졌다([runbooks/mysql-replica.md](runbooks/mysql-replica.md) 「1. 처음 한 번」).

`harbor-pull`은 Harbor **pull 전용** 로봇 계정이다. 06번에서 Jenkins에 push · pull 로봇을 따로 준 것과 같은 원칙이다. 노드가 이미지를 받는 데는 pull만 있으면 된다. Harbor 프로젝트 `petmint` · `runshoes`는 private이라, 이 Secret이 없으면 Pod가 `pull access denied … no basic auth credentials`로 멈춘다.

> Secret이 namespaced라 runshoes의 DB 계정을 petmint 초기화 Job이 만들 수 없다. 처음에는 MySQL 하나에 두 앱을 넣을 계획이었으나(펫퍼민트 저장소 `~/AI_programming/petmint-rag-chatbot/docs/02_pipeline/12_data_storage.md` 「1-3. 인스턴스 구성」), runshoes는 자기 네임스페이스에 MySQL을 따로 두었다.

### 11-2단계: 매니페스트 (Kustomize)

2026-11-12 파일 목록:

```txt
apps/petmint/
  app.yaml               ArgoCD Application(루트가 읽는다)
  kustomization.yaml     리소스 목록 + 이미지 태그(images.newTag)
  mysql/                 StatefulSet + headless Service, replica.yaml(Replica, 2026-11-10)
  data/nfs.yaml          약관 · 시드: 호스트 NFS 읽기 전용 PV 3개
  jobs/init-db.yaml      초기화 Job(ArgoCD Sync hook)
  app/                   Deployment · PDB · Service · Ingress · ConfigMap
  backup/cronjob.yaml    MySQL 백업 CronJob(2026-11-10)
  scripts/               create-secrets.sh

apps/runshoes/
  app.yaml               ArgoCD Application
  kustomization.yaml     이미지 둘(같은 태그)
  mysql/                 StatefulSet + headless Service, replica.yaml(Replica, 2026-11-10)
  app/                   Deployment(앱 + 챗봇) · PDB · Service · Ingress · CronJob(리뷰 요약)
  runbooks/              스키마를 바꾸는 배포 절차와 실행 기록
  scripts/               create-secrets.sh · check-image-migrations.sh
```

이미지 태그는 Deployment에 쓰지 않고 `kustomization.yaml` 한 곳에만 둔다. 아래 태그는 예시다(2026-11-12 petmint 값은 `574b3f50acf8`).

```yaml
images:
  - name: harbor.ronanlab.dev/petmint/petmint-app
    newTag: "830f345139f8"   # Jenkins가 바꾼다(커밋 해시 12자리). latest 금지
```

왜 이렇게 했는지는 2절 「이미지 태그를 다루는 방식」.

### 11-3단계: Jenkins → Harbor → ArgoCD

지금(2026-11-12)의 흐름:

```txt
앱 저장소 push
  → GitHub 웹훅 → Jenkins (안전망: 폴링 15분)
  → BuildKit rootless로 이미지 빌드 → Harbor push (태그 = 커밋 해시)
  → ronanlab-infra의 newTag 한 줄을 고쳐 push
  → GitHub 웹훅 → ArgoCD (안전망: 조회 3분)
  → petmint · runshoes 모두 자동 Sync (petmint는 2026-11-10까지 OutOfSync 표시 → 사람이 Sync)
  → 롤링 업데이트(옛 Pod 하나를 내리고 새 Pod, 한 Pod씩)
```

06번에서는 Kaniko로 빌드할 계획이었다. 실제 파이프라인은 **BuildKit rootless**(`moby/buildkit:v0.33.1-rootless`, 두 Jenkinsfile 모두 2026-11-12 확인)로 짰다. 특권 컨테이너가 필요 없다는 목표는 같다. 특권 대신 seccomp · AppArmor만 Unconfined로 풀고, rootlesskit이 사용자 네임스페이스를 만든다. Jenkins Job · 자격증명 · 웹훅은 `platform/jenkins/values.yaml`의 JCasC가 만든다([06_jenkins.md](06_jenkins.md)).

태그 갱신 단계(Jenkinsfile):

```bash
sed -E -i 's/^(    newTag: )"[0-9a-f]{12}"/\1"'"$TAG"'"/' "$KUSTOMIZATION"
grep -q '^    newTag: "'"$TAG"'"' "$KUSTOMIZATION" || { echo "newTag 줄을 못 찾았다"; exit 1; }
git push -q origin HEAD:main
```

바꾼 뒤 `grep`으로 다시 세는 이유: `sed`는 아무것도 못 바꿔도 성공으로 끝난다. 줄 모양이 바뀌면 빌드는 성공인데 배포가 조용히 빠진다. runshoes는 줄이 둘이라 `grep -c`가 2인지 본다.

#### 트러블슈팅: 태그 push가 빌드를 다시 부른다

**증상**: 06번에서 저장소를 나눈 이유가 "한 저장소면 태그 push가 webhook을 다시 부른다"였다. 저장소를 나눠도 같은 일이 생길 수 있었다.

**원인**: Jenkins의 SCM 폴링은 **빌드 중 `git`/`checkout` 단계로 받은 저장소를 전부 감시한다.** ronanlab-infra를 `git` 단계로 받으면 그 저장소도 감시 대상이 되어, 태그 push → 폴링이 변경 감지 → 빌드 → 또 태그 push가 이어진다.

**해결**: ronanlab-infra는 `sh 'git clone'`으로 받는다. Jenkins가 모르는 clone이라 감시하지 않는다.

> 문서만 바꾼 push도 이미지를 새로 굽고 태그를 바꿔 Pod를 갈았다(2026-11-09까지). 지금은 바뀐 파일이 모두 `docs/` · `*.md` 등이면 빌드는 SUCCESS로 끝내고 이미지 · 태그 커밋을 건너뛴다. 트리거에서 경로를 빼지 않은 이유는 "push했는데 빌드가 없다"와 "빌드를 건너뛰었다"를 구분하기 위해서다.

Harbor에 닿는 두 길(push는 CoreDNS, pull은 노드 `/etc/hosts`)은 2절 「Harbor에 닿는 길은 두 가지다」.

### 11-4단계: ArgoCD Application

처음(2026-10-16)의 petmint Application이다. 자동 Sync가 없었다. 지금 `apps/petmint/app.yaml`에는 `automated: {prune: false, selfHeal: false}`가 있다(2026-11-11).

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: petmint
  namespace: argocd
spec:
  project: default
  source:
    repoURL: git@github.com:Gabriel-Joo/ronanlab-infra.git
    targetRevision: main
    path: apps/petmint
  destination:
    server: https://kubernetes.default.svc
    namespace: petmint
  syncPolicy:
    syncOptions:
      - CreateNamespace=false
```

| 설정 | petmint | runshoes | 이유 |
| --- | --- | --- | --- |
| 자동 Sync | 켬(2026-11-11~, 2026-10-16~11-10은 끔) | 켬 | petmint는 처음에 매니페스트가 의도대로 반영되는지 사람이 보고 눌렀다. 2026-11-11 사용자 지시로 runshoes와 같게 켰다 |
| prune | 끔 | 끔 | git에서 지운 리소스가 클러스터에서 바로 사라지지 않게 |
| selfHeal | 끔 | 끔 | 복구 중 손으로 바꾼 것(예: replicas 0)을 ArgoCD가 되돌리지 않게 |
| finalizer | 없음 | 없음 | Application을 지워도 앱 · MySQL · PV가 남는다 |

ArgoCD · Jenkins가 서로 다른 deploy key로 저장소에 닿는 까닭은 2절 「저장소 접근 키를 나눈다」.

**스키마를 바꾸는 배포**는 자동 Sync를 잠시 끈다. runshoes는 덤프 → 복원 확인 → Sync → 확인 → 다시 켜기를 런북(`apps/runshoes/runbooks/`)대로 한다. 자동 Sync가 켜져 있으면 Jenkins 태그 커밋이 덤프보다 먼저 배포될 수 있다. petmint도 자동이 된 뒤로는 초기화 Job(마이그레이션)이 Sync마다 돌아 앱 push만으로 운영 DB에 적용되므로, 되돌리기 어려운 스키마 변경 · DB 복구 때는 먼저 끈다(끄고 켜는 명령은 [apps/petmint/README.md](../apps/petmint/README.md) 「ArgoCD가 관리한다」).

### 11-5단계: MySQL StatefulSet과 PVC

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: mysql
spec:
  serviceName: mysql
  replicas: 1
  persistentVolumeClaimRetentionPolicy:
    whenDeleted: Retain
    whenScaled: Retain
  template:
    spec:
      terminationGracePeriodSeconds: 60
      containers:
        - name: mysql
          image: mysql:8.0.46
          args:
            - --innodb-buffer-pool-size=256M
            - --character-set-server=utf8mb4
          readinessProbe:
            exec:
              command: ["mysqladmin", "ping", "-h", "127.0.0.1", "--silent"]
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        storageClassName: local-path
        resources:
          requests:
            storage: 10Gi
```

| 값 | 기본값대로 두면 | 이유 |
| --- | --- | --- |
| `volumeClaimTemplates` | (Deployment + 공유 PVC) 여러 Pod가 한 디스크에 쓴다 | 수업 Day6의 원칙. 상태를 가진 것은 StatefulSet으로 전용 PVC를 받는다 |
| `persistentVolumeClaimRetentionPolicy: Retain` | (기본도 Retain) | 명시해 둔다. StatefulSet을 지워도 데이터는 남는다. 지우려면 PVC를 직접 지운다 |
| `terminationGracePeriodSeconds: 60` | 30초 뒤 SIGKILL | InnoDB가 정상 종료할 시간 |
| `mysqladmin ping` | (없음) | 인증 없이도 서버가 응답하면 0을 돌려준다. 비밀번호를 프로세스 인자에 남기지 않는다 |
| `innodb-buffer-pool-size=256M` | 128M | 워커 메모리 안에서 조금만 키운다 |
| 이미지 `mysql:8.0.46` | (없음) | 개발 호스트와 같은 버전. kustomization `images`에 넣지 않아 Jenkins `sed`가 바꾸지 않는다 |

```bash
kubectl -n petmint get pvc; kubectl -n runshoes get pvc
```

그때(2026-11-10 Replica 전)의 출력:

```txt
petmint    data-mysql-0            local-path   10Gi   ReadWriteOnce
petmint    petmint-backup                       5Gi    ReadWriteMany
petmint    petmint-chunks                       1Gi    ReadOnlyMany
petmint    petmint-fixtures                     1Gi    ReadOnlyMany
petmint    petmint-graph                        1Gi    ReadOnlyMany
runshoes   data-runshoes-mysql-0   local-path   2Gi    ReadWriteOnce
```

2026-11-12 지금은 Replica의 PVC `data-mysql-replica-0`(local-path 10Gi, w2) · `data-runshoes-mysql-replica-0`(local-path 2Gi, w2)이 더 있다. Primary PVC는 둘 다 w1에 있다.

MySQL만 `local-path`다. 약관(chunks · graph)과 시드 픽스처는 호스트 디렉터리를 **NFS 읽기 전용**으로 붙인 정적 PV라 `ReadOnlyMany`이고, 앱 Pod가 어느 노드에 떠도 붙는다. 읽기 전용은 세 겹이다(호스트 export `ro` · PV `readOnly` · Pod volumeMount `readOnly`). 05번에서 미뤘던 "Milvus 같은 데이터를 어디 둘까"는 Milvus를 호스트에 두는 것으로 정리됐고, 앱이 읽는 파일만 NFS로 넘겼다.

**스키마를 넣는 방식이 둘이다.**

|  | petmint | runshoes |
| --- | --- | --- |
| 누가 | 초기화 Job(앱과 같은 이미지) | 앱 자신(Flyway, 기동 때) |
| 순서 보장 | ArgoCD sync-wave: MySQL(0) → Job(1, Sync hook) → 앱(2) | initContainer `wait-mysql`가 3306이 열릴 때까지 기다린다 |
| 여러 번 돌려도 | 같다. bootstrap · migrate는 멱등, 시드는 `--if-empty` | 적용된 버전은 다시 돌지 않는다 |

#### 트러블슈팅: Job은 다시 apply할 수 없다

**증상**: 이미지 태그를 바꾸고 그대로 apply하면 `field is immutable`로 실패한다.

**원인**: Job의 Pod 템플릿은 바꿀 수 없다.

**해결**: Job을 ArgoCD **Sync hook**으로 만들고 `hook-delete-policy: BeforeHookCreation`을 붙였다. Sync할 때마다 끝난 Job을 지우고 새로 만든다. 새 이미지의 마이그레이션이 Sync마다 돈다.

```yaml
metadata:
  annotations:
    argocd.argoproj.io/hook: Sync
    argocd.argoproj.io/hook-delete-policy: BeforeHookCreation
    argocd.argoproj.io/sync-wave: "1"
```

#### 트러블슈팅: 재부팅 뒤 runshoes가 스스로 끝났다

**증상**: 2026-11-06 노드 재부팅 뒤 runshoes 앱이 두 번 재시작했다(`lastState: Error`).

**원인**: 앱이 MySQL보다 먼저 떠서 Flyway가 DB에 붙지 못하자 Spring이 스스로 종료했다. startupProbe는 liveness를 늦출 뿐 **앱이 스스로 끝나는 것은 막지 못한다.**

**해결**: 앱 앞에 initContainer를 두었다. Service를 거쳐 3306이 열릴 때까지(MySQL readinessProbe 통과) 2초마다 확인하고, 3분이 넘으면 실패해 kubelet이 백오프로 다시 돈다.

```yaml
initContainers:
  - name: wait-mysql
    image: docker.io/library/busybox:1.37.0
    command:
      - sh
      - -c
      - |
        i=0
        until nc -z -w 2 runshoes-mysql 3306; do
          i=$((i+1))
          if [ "$i" -ge 90 ]; then echo "runshoes-mysql:3306 3분 동안 안 열림"; exit 1; fi
          sleep 2
        done
```

### 11-6단계: 앱 Deployment

2026-11-12 값이다.

| 설정 | 값 | 이유 |
| --- | --- | --- |
| `replicas` | 2 (runshoes는 2026-11-10부터) | 세션 · 상태가 DB에 있어 Pod를 늘려도 된다 |
| `nodeSelector` | `node.ronanlab.dev/role: app`(w1 · w2, 2026-11-10~) | 앱은 app 노드에만. 노드 역할은 `cluster/label-nodes.sh`, 까닭은 [08_scale_out.md](08_scale_out.md) |
| `podAntiAffinity` | required, `kubernetes.io/hostname` | 둘을 같은 노드에 두지 않는다. 노드 하나가 죽어도 다른 Pod가 받는다 |
| PodDisruptionBudget | `minAvailable: 1` | drain 때 둘을 한꺼번에 내보내지 않는다 |
| `maxSurge: 0`, `maxUnavailable: 1` | (2026-11-10~, 그 전은 `maxSurge: 1`, `maxUnavailable: 0`) | app 노드가 둘뿐이라 새 Pod를 먼저 띄우면(2+1개) 세 번째 Pod가 갈 곳이 없다. 옛 Pod 하나를 먼저 내리고 그 자리에 새 Pod를 띄운다. 롤링 동안 잠깐 Pod가 하나다(서비스는 이어진다) |
| readinessProbe | runshoes는 `/actuator/health/readiness`(DB 포함) | DB에 못 붙는 Pod에는 요청을 보내지 않는다 |
| preStop `sleep 5` | (없음) | Ingress가 엔드포인트를 뺄 시간을 준 뒤 SIGTERM |

> required anti-affinity라 롤링 중 2+1개가 뜨려면 스케줄 가능한 노드가 3대 있어야 한다. 워커가 3대일 때(2026-11-10 전, `maxSurge 1`)는 한 대가 빠진 동안 롤링하면 새 Pod가 Pending에 멈췄다(옛 Pod 둘이 계속 받는다). 2026-11-10 워커를 4대로 늘리면서 앱을 app 노드(w1 · w2) 둘에만 두도록 고정했고, 그래서 롤링을 `maxSurge 0 / maxUnavailable 1`로 바꿨다. **지금은 app 노드 하나가 빠지면 두 번째 Pod가 그 노드가 돌아올 때까지 Pending이고, 그동안 롤링은 멈춘다(남은 하나가 받는다).** ([08_scale_out.md](08_scale_out.md))

롤링 중 확인(petmint, 2026-10-16, 그때 롤링은 `maxSurge 1 / maxUnavailable 0`): 부하(HTTP 3종 동시 · WebSocket 5초마다) 속에서 롤링 두 번, HTTP 6,675건 · 5,012건 실패 0. WebSocket은 옛 Pod가 내려갈 때 1012(service restart)로 한 번 끊기고 프런트가 다시 붙는다. 2026-11-10 지금 방식으로 바꾼 뒤의 롤링 기록(실패 0)은 [08_scale_out.md](08_scale_out.md).

### 11-7단계: Ingress, 터널, 도메인

03번 설계([03_cloudflare_tunnel.md](03_cloudflare_tunnel.md)) 그대로, 앱마다 **Ingress 리소스 하나**를 더하고 터널 ConfigMap에 hostname 한 줄을 더했다.

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: runshoes
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "false"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "3600"
spec:
  ingressClassName: nginx
  rules:
    - host: runshoes.ronanlab.dev
      http:
        paths:
          - path: /ws/chat
            pathType: Prefix
            backend:
              service:
                name: runshoes
                port:
                  name: chatbot
          - path: /
            pathType: Prefix
            backend:
              service:
                name: runshoes
                port:
                  name: http
```

| 값 | 기본값대로 두면 | 이유 |
| --- | --- | --- |
| `ssl-redirect: "false"` | 리다이렉트 루프 가능성 | 터널이 이미 HTTPS로 받아 들어온다. 05번 Harbor와 같다 |
| `proxy-read/send-timeout: "3600"` | **60초 쉬면 WebSocket이 끊긴다** | 상담 · 챗봇 연결이 길게 이어진다. 그 사이는 앱의 ping(uvicorn 20초)이 살린다 |
| `/ws/chat` → `chatbot` 포트 | (없음) | 같은 Pod의 사이드카로. 프런트가 `wss://<같은 호스트>/ws/chat`로 붙어 경로를 바꾸지 않는다(rewrite 없음) |
| petmint `proxy-buffering: "off"` | 스트리밍 응답이 모였다가 한꺼번에 나간다 | 답변이 토큰 단위로 보이게 |

```bash
kubectl get ingress -A
```

그때(2026-11-10)의 출력:

```txt
argocd     argocd-server    argocd.ronanlab.dev     argocd-ingress-tls
harbor     harbor-ingress   harbor.ronanlab.dev     harbor-tls
jenkins    jenkins          jenkins.ronanlab.dev    jenkins-tls
petmint    petmint-app      petmint.ronanlab.dev    <none>
runshoes   runshoes         runshoes.ronanlab.dev   <none>
```

2026-11-11 모니터링 바깥 주소를 열며 `monitoring` 네임스페이스에 `grafana`(grafana-tls) · `prometheus`(prometheus-tls)가 더해져 지금은 7개다(1절 표).

앱 둘은 Ingress에 TLS가 없다. 바깥 TLS는 Cloudflare 엣지에서 끝난다. ArgoCD · Harbor · Jenkins(그리고 지금은 Grafana · Prometheus)만 인증서가 있는 이유는 클러스터 안(MetalLB VIP)에서도 그 이름으로 부르기 때문이다(2절 「Harbor에 닿는 길은 두 가지다」).

**터널은 클러스터 공용이 됐다.** 03번에서는 petmint 네임스페이스에 터널 Pod를 띄웠다. 2026-10-18 런슈즈를 다섯 번째 호스트로 더하면서 무중단으로 `cloudflared` 네임스페이스로 옮겼고(커넥터 2 → 4로 늘려 확인한 뒤 옛것을 지움, 1초마다 1,360회 실패 0), 지금은 `apps/cloudflared`를 ArgoCD가 수동 Sync로 관리한다. 이 Application은 ArgoCD 자신에게 오는 길이라 자동 Sync를 켜지 않는다(2026-11-11 사용자 결정으로 다시 확인, `apps/cloudflared/app.yaml`). 2026-11-11 grafana · prometheus가 더해져 호스트는 일곱이다.

```txt
runshoes.ronanlab.dev
  → Cloudflare 엣지
  → ronanlab-tunnel (cloudflared 네임스페이스, Pod 2개)
  → nginx-ingress (Host 헤더로 분기, / 와 /ws/chat 은 경로로)
  → runshoes Pod 2개 (앱 :3000 · 챗봇 :8766)
```

Access 정책은 Cloudflare 대시보드에서 호스트마다 건다. ArgoCD · Harbor · Jenkins(지금은 Grafana · Prometheus도)는 운영자만, runshoes는 공개 사이트라 걸지 않는다. GitHub 웹훅(`/api/webhook`, `/github-webhook/`)은 그 경로만 Access를 비켜 두고 HMAC 서명이 지킨다.

### 11-8단계: 앱 로그인

두 앱 모두 클러스터가 아니라 **앱이** 로그인을 한다. 비밀값은 Secret, 켜고 끄는 값은 ConfigMap · env다.

| 항목 | petmint | runshoes |
| --- | --- | --- |
| 방식 | 사번 · 비밀번호, 서버 저장 세션 쿠키(HttpOnly · Secure · SameSite=Lax) | 이메일 가입 · 로그인, JWT access(15분, 메모리) + refresh(14일, HttpOnly 쿠키) |
| 켜는 곳 | ConfigMap `PETMINT_AUTH: "app"` (2026-10-28) | 늘 켜짐. 체험 계정 카드는 env `DEMO_LOGIN_ENABLED` |
| 비밀 | DB 계정 비밀번호(`petmint-db`) | Secret `runshoes-auth`: `JWT_SECRET` · `SEED_USER_PASSWORD` · `ADMIN_PASSWORD` |
| 계정 | 가상 직원 11명(초기화 Job이 원장에 시드), 첫 관리자는 사람이 Pod 안에서 만든다 | 시드 사용자 30명 + 읽기 전용 데모 관리자. 비밀번호 칸이 비면 기동할 때 Secret 값으로 채운다 |
| 되돌리기 | `PETMINT_AUTH` 줄을 지우고 Sync → `rollout restart` | (없음) |

```bash
kubectl -n petmint exec -it deploy/petmint-app -- python -m db.employees add E2001003 --role 관리자
```

비밀번호는 화면에 보이지 않게 두 번 묻는다. git에는 평문도 해시도 없다.

runshoes의 `runshoes-auth`는 `envFrom: secretRef`로 붙이고 **optional이 아니다.** Secret이 없으면 새 Pod가 `CreateContainerConfigError`로 멈춘다. 처음(`maxUnavailable: 0`)에는 옛 Pod 둘이 계속 돌았고, 지금(`maxUnavailable: 1`, 2026-11-10~)은 옛 Pod 하나를 먼저 내리므로 남은 옛 Pod 하나가 계속 받고 롤링이 멈춘다. 어느 쪽이든 로그인 기능이 비밀 없이 뜨는 일은 없다.

### 11-9단계: ConfigMap 플래그

petmint는 검색 · 답 동작을 **코드 기본값을 바꾸지 않고 ConfigMap에서만** 켠다. 되돌릴 때 ConfigMap만 고치면 된다(`apps/petmint/app/configmap.yaml`).

| ConfigMap 키 | 값 | 하는 일 |
| --- | --- | --- |
| `PETMINT_SEARCH_VARIANT` | `v3` | search-service가 Milvus `petmint_*_v3` 컬렉션으로 찾는다 |
| `PETMINT_CHUNKS_DIR` · `PETMINT_GRAPH_DIR` | `…/chunks/v3` · `…/graph/v3` | NFS 공유 안의 v3 폴더 |
| `PETMINT_SEARCH_EXPAND` | `"1"` | 질의 확장(고객 말 → 약관 말) |
| `PETMINT_SEARCH_POOL` | `"50"` | 1차 후보 깊이 20 → 50 |
| `PETMINT_COVERAGE_CODE` 등 코드 답 플래그 | `"1"` | 나이 · 면책 단서 · 병명 보장 같은 질문은 모델 대신 코드가 약관 기준으로 답한다 |
| `PETMINT_TITLE_LLM` | `"1"` | 상담 제목을 호스트 Ollama로 짓는다 |
| `PETMINT_MODEL_RAG` | 어댑터 이름 | 호스트에 `ollama create`로 먼저 올려 둔 모델 |

플래그마다 측정 근거를 ConfigMap 주석에 남겼다(펫퍼민트 저장소 `~/AI_programming/petmint-rag-chatbot/data/review/*_measure.md`).

> **ConfigMap만 바꿔서는 떠 있는 Pod에 반영되지 않는다.** `envFrom`은 컨테이너가 시작할 때 한 번 읽는다. Sync(지금은 자동) 뒤 `kubectl -n petmint rollout restart deploy/petmint-app`(한 Pod씩 바뀐다). 이미지 태그가 같이 바뀌는 Sync면 롤링이 어차피 돌아 따로 하지 않는다.

**반영 순서: 앱 먼저, infra 나중.** 플래그를 먼저 올리면 옛 이미지가 v3 청크 파일을 읽으면서 검색은 옛 컬렉션으로 해 둘이 어긋난다. 앱 push → Jenkins 태그 커밋 → 그 커밋을 받은 뒤 ConfigMap 변경 push → Sync 순서로 한다. petmint가 자동 Sync가 된 뒤로는 push가 곧 반영이므로 이 순서가 더 중요하다.

### 최종 확인 (2026-11-10)

그때의 출력이다. 지금 값은 5절.

```bash
kubectl -n argocd get applications
```

```txt
NAME            SYNC STATUS   HEALTH STATUS
cloudflared     Synced        Healthy
harbor-backup   Synced        Healthy
petmint         Synced        Healthy
root            Synced        Healthy
runshoes        Synced        Healthy
```

```bash
kubectl -n petmint get deploy,sts,cronjob; kubectl -n runshoes get deploy,sts,cronjob
```

```txt
NAME                          READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/petmint-app   2/2     2            2           25d

NAME                     READY   AGE
statefulset.apps/mysql   1/1     25d

NAME                         SCHEDULE     TIMEZONE     SUSPEND   ACTIVE   LAST SCHEDULE   AGE
cronjob.batch/mysql-backup   30 3 * * *   Asia/Seoul   False     0        <none>          129m
NAME                       READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/runshoes   2/2     2            2           23d

NAME                              READY   AGE
statefulset.apps/runshoes-mysql   1/1     20d

NAME                             SCHEDULE     TIMEZONE     SUSPEND   ACTIVE   LAST SCHEDULE   AGE
cronjob.batch/runshoes-summary   30 3 * * *   Asia/Seoul   False     0        <none>          6h11m
```

```txt
petmint.ronanlab.dev / runshoes.ronanlab.dev
  → Cloudflare 엣지
  → ronanlab-tunnel (cloudflared Pod 2개)
  → nginx-ingress
  → 앱 Pod 2개 (서로 다른 노드, w1 · w2)
  → MySQL Primary StatefulSet (local-path PVC, w1) · 호스트 Ollama/Milvus (192.168.122.1)
    (Replica는 w2에서 Primary를 따라간다. 앱은 Replica를 보지 않는다)
```

> **03번 설계가 다섯 번째로 검증됐다.** ArgoCD · Harbor · Jenkins에 이어 두 앱도 터널에는 hostname 한 줄, 클러스터에는 Ingress 하나가 전부였다. 배포는 앱 저장소 push 한 번으로 이어지고, 사람이 하는 일은 그때 petmint의 Sync 버튼과 스키마 변경 때의 런북뿐이었다. 2026-11-11 petmint도 자동 Sync가 되어 지금 사람이 하는 일은 스키마 변경 · DB 복구 때 자동 Sync를 끄고 런북대로 하는 것뿐이다.

"07. 프로젝트 배포" 문서 전체(11단계) 완료. 다음은 [08_scale_out.md](08_scale_out.md)(구조 확장 · 이관).

### 이후: 2026-11-10 이후 바뀐 것

| 날짜 | 바뀐 것 | 자리 |
| --- | --- | --- |
| 2026-11-10 | runshoes replicas 2 · PDB, 두 앱 app 노드(w1 · w2) 고정, 롤링 `maxSurge 0 / maxUnavailable 1` | `apps/*/app/deployment.yaml`, [08_scale_out.md](08_scale_out.md) |
| 2026-11-10 | MySQL Replica(`mysql-replica` · `runshoes-mysql-replica`, w2), Secret `mysql-repl` | `apps/*/mysql/replica.yaml`, [runbooks/mysql-replica.md](runbooks/mysql-replica.md) |
| 2026-11-10 | petmint MySQL 백업 CronJob `mysql-backup` | `apps/petmint/backup/cronjob.yaml`, 펫퍼민트 저장소 `docs/02_pipeline/12_data_storage.md` 「1-5. 백업과 복구 (2026-11-10)」 |
| 2026-11-10 | runshoes `ACTIVITY_CLEANUP_CRON "-"`(Pod 둘이 같은 행을 지우려는 잠금 경합을 피해 activity\_logs 정리를 껐다) | `apps/runshoes/app/deployment.yaml` |
| 2026-11-10 | Application `monitoring`(루트 exclude 줄을 지웠다, 처음 수동 Sync) | [09_monitoring.md](09_monitoring.md) |
| 2026-11-11 | Ingress grafana · prometheus, 터널 호스트 7개 | `apps/monitoring/ingress.yaml`, `apps/cloudflared/configmap.yaml` |
| 2026-11-11 | petmint · monitoring 자동 Sync(cloudflared만 수동) | `apps/petmint/app.yaml`, `apps/monitoring/app.yaml`, `apps/cloudflared/app.yaml` |

## 4. 남은 한계

- **MySQL 자동 전환이 없다.** Primary(w1)가 죽으면 앱 쓰기가 멈추고, 승격은 사람이 [runbooks/mysql-replica.md](runbooks/mysql-replica.md) 「3. 승격」대로 한다. Primary PVC는 local-path라 w1 디스크에 묶여 있다
- **runshoes MySQL은 정기 백업 CronJob이 없다.** CronJob은 petmint `mysql-backup`뿐이다. runshoes는 스키마를 바꾸기 전에 덤프를 뜬다([apps/runshoes/README.md](../apps/runshoes/README.md) 「데이터」 절, `apps/runshoes/runbooks/auth-v3.md`). Replica는 백업이 아니다(지운 것도 따라간다)
- **app 노드 하나가 빠지면** 두 번째 앱 Pod는 Pending이고 롤링이 멈춘다. 그동안 Pod 하나가 받는다
- **롤링 동안 잠깐 Pod가 하나다**(`maxUnavailable: 1`). 그 사이 남은 Pod가 죽으면 끊긴다
- **petmint 자동 Sync는 마이그레이션까지 자동이다.** 초기화 Job이 Sync마다 돌아, 앱 커밋에 든 마이그레이션이 push만으로 운영 DB에 들어간다. 되돌리기 어려운 변경은 자동 Sync를 끄고 한다. DB 마이그레이션은 이미지 revert로 되돌아가지 않는다
- **ConfigMap 변경은 `rollout restart`가 따로 필요하다**(이미지가 같이 바뀌지 않으면)
- **runshoes activity\_logs가 지워지지 않고 쌓인다.** 정리 스케줄을 꺼 두었다. ShedLock(앱 저장소 일)이 들어오면 env를 뺀다
- **prune이 꺼져 있다.** git에서 지운 리소스는 클러스터에 남아 손으로 지운다
- 공개 터널 하나(cloudflared Pod 2개)가 공개 주소 7개를 모두 받는다. 터널이 깨지면 ArgoCD UI · Grafana도 바깥에서 안 보인다(`apps/cloudflared/README.md`)

## 5. 확인 방법

m-k8s에서(`cd ~/k8s-cluster && vagrant ssh m-k8s`). 기대 결과는 2026-11-12 09:18 KST 조회값이다.

```bash
kubectl -n argocd get app -o custom-columns=N:.metadata.name,AUTO:.spec.syncPolicy.automated,SYNC:.status.sync.status,HEALTH:.status.health.status
# cloudflared     <none>  Synced  Healthy   (수동)
# harbor-backup   map[]   Synced  Healthy
# monitoring      map[]   Synced  Healthy
# petmint         map[]   Synced  Healthy
# root            map[]   Synced  Healthy
# runshoes        map[]   Synced  Healthy
# (map[] = automated 켜짐, prune · selfHeal false)

kubectl -n petmint get pod -o wide; kubectl -n runshoes get pod -o wide
# petmint-app-*  w1-k8s · w2-k8s / mysql-0 w1-k8s / mysql-replica-0 w2-k8s
# runshoes-*     w1-k8s · w2-k8s / runshoes-mysql-0 w1-k8s / runshoes-mysql-replica-0 w2-k8s

kubectl -n petmint get deploy petmint-app -o jsonpath='{.spec.strategy.rollingUpdate}{"\n"}'
kubectl -n runshoes get deploy runshoes -o jsonpath='{.spec.strategy.rollingUpdate}{"\n"}'
# {"maxSurge":0,"maxUnavailable":1}

kubectl -n petmint get sts; kubectl -n runshoes get sts
# mysql 1/1 · mysql-replica 1/1 / runshoes-mysql 1/1 · runshoes-mysql-replica 1/1

kubectl get cronjob -A
# harbor    harbor-db-backup   45 3 * * *   Asia/Seoul
# petmint   mysql-backup       30 3 * * *   Asia/Seoul
# runshoes  runshoes-summary   30 3 * * *   Asia/Seoul

kubectl get pdb -A
# petmint  petmint-app  1 / runshoes  runshoes  1 (ALLOWED DISRUPTIONS 1)

kubectl get ingress -A
# 7개: argocd-server · harbor-ingress · jenkins · grafana · prometheus · petmint-app · runshoes

kubectl -n cloudflared get cm -o yaml | grep -c 'hostname:'
# 7

kubectl -n petmint get pvc; kubectl -n runshoes get pvc
# data-mysql-0 · data-mysql-replica-0 (10Gi) · petmint-backup · petmint-chunks · petmint-fixtures · petmint-graph
# data-runshoes-mysql-0 · data-runshoes-mysql-replica-0 (2Gi)
```

이미지 태그가 저장소와 같은지(저장소의 `newTag`와 Deployment 이미지):

```bash
grep newTag apps/petmint/kustomization.yaml apps/runshoes/kustomization.yaml   # 저장소에서
kubectl -n petmint get deploy petmint-app -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
kubectl -n runshoes get deploy runshoes -o jsonpath='{.spec.template.spec.containers[*].image}{"\n"}'
```

바깥에서(호스트):

```bash
curl -sI https://petmint.ronanlab.dev | head -1    # HTTP/2 200
curl -sI https://runshoes.ronanlab.dev | head -1   # HTTP/2 200
```

Replica가 따라오는지는 `scripts/mysql-replica-check.sh`와 [runbooks/mysql-replica.md](runbooks/mysql-replica.md).

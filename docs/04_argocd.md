# 04. ArgoCD

ArgoCD v2.13.2를 `install.yaml`로 깔고 Ingress와 기존 Cloudflare 터널로 `argocd.ronanlab.dev`에 내놓았다. 지금은 루트 Application 하나(App of Apps)가 `main`의 `apps/*/app.yaml`을 읽어 앱 Application 다섯을 만들고, 7개 Pod 모두 w3(infra)에서 돈다.

- 날짜: 2026-10-13 설치 · 외부 노출, 2026-11-02 App of Apps, 2026-11-03 웹훅 · 알림, 2026-11-10 w3 고정, 2026-11-12 코드와 맞춤
- 범위: ArgoCD 설치 · 외부 노출 · Application 구성 · 웹훅 · 알림. 터널 자체는 [03_cloudflare_tunnel.md](03_cloudflare_tunnel.md), 인증서는 [02_metrics_storage_ingress.md](02_metrics_storage_ingress.md), 앱 배포는 [07_project_deploy.md](07_project_deploy.md), 노드 배치는 [08_scale_out.md](08_scale_out.md)
- 코드: `bootstrap/root-app.yaml`, `apps/*/app.yaml`, `platform/argocd/ingress.yaml`, `platform/argocd/pin-infra.sh`

## 1. 지금 구성

2026-11-12 클러스터 조회(`cluster_snapshot.txt` 09:18 KST, `kubectl get pod -o wide`)로 확인한 값이다.

| 항목 | 값 |
| --- | --- |
| 버전 | v2.13.2(`quay.io/argoproj/argocd:v2.13.2`), 설치는 `install.yaml`을 `kubectl apply`. 그 매니페스트는 이 저장소에 없다 |
| Pod | 7개(application-controller · applicationset-controller · dex-server · notifications-controller · redis · repo-server · server) 모두 w3-k8s |
| 배치 고정 | `platform/argocd/pin-infra.sh`가 Deployment 여섯 · StatefulSet 하나에 `nodeSelector: node.ronanlab.dev/role: infra`를 patch한다. `install.yaml`을 다시 apply하면 사라지므로 이 스크립트를 다시 돌린다. PVC 없음(redis는 emptyDir) |
| 초기 비밀번호 Secret | `argocd-initial-admin-secret` 없음(`NotFound`, 지웠다) |
| 외부 주소 | `https://argocd.ronanlab.dev`, Ingress `argocd/argocd-server`(`platform/argocd/ingress.yaml`, 사람이 apply), TLS Secret `argocd-ingress-tls`(cert-manager) |
| 터널 | `ronanlab-tunnel`(`02ad6a13-ce45-4262-a32a-40241bf034dc`, 2026-10-18 전 이름 `petmint-tunnel`), 설정은 `apps/cloudflared/configmap.yaml` |
| 저장소 | `git@github.com:Gabriel-Joo/ronanlab-infra.git`(private), 읽기 전용 deploy key(Secret `argocd/repo-ronanlab-infra`, `scripts/make-deploy-keys.sh`) |

### Application (6개)

| 이름 | 경로 | Sync | 상태 |
| --- | --- | --- | --- |
| root | `apps`(`*/app.yaml`만) | 자동 | Synced / Healthy |
| cloudflared | `apps/cloudflared` | **수동** | Synced / Healthy |
| harbor-backup | `apps/harbor-backup` | 자동 | Synced / Healthy |
| monitoring | `apps/monitoring` | 자동(2026-11-11~) | Synced / Healthy |
| petmint | `apps/petmint` | 자동(2026-11-11~, 그 전은 수동) | Synced / Healthy |
| runshoes | `apps/runshoes` | 자동 | Synced / Healthy |

- 모두 `targetRevision: main`. 자동인 것은 모두 prune · selfHeal 끔, finalizer 없음, `CreateNamespace=false`
- 루트는 사람이 한 번 넣는다(`kubectl apply -f bootstrap/root-app.yaml`). 새 앱은 `apps/<이름>/`에 `app.yaml`과 매니페스트를 넣고 push하면 3분 안에 Application이 생긴다
- **자동 Sync를 켜고 끄는 실제 스위치는 클러스터의 `kubectl patch`이고 `app.yaml`은 기록이다.** 루트가 자식의 `spec.syncPolicy`를 덮지 않는다(`ignoreDifferences` + `RespectIgnoreDifferences=true`, `bootstrap/root-app.yaml` 머리 주석). 그러지 않으면 Jenkins 태그 커밋 하나에 루트가 다시 Sync해서, 스키마 배포 중 잠시 꺼 둔 자동 Sync를 도로 켠다
- cloudflared만 수동인 까닭: 터널이 깨지면 공개 주소 7개가 한꺼번에 안 보이고 고칠 도구(ArgoCD UI) · 볼 도구(Grafana)도 같이 사라진다(`apps/cloudflared/app.yaml`, 2026-11-11 사용자 결정)
- 수동 Sync: `kubectl -n argocd patch app <앱> --type merge -p '{"operation":{"sync":{"revision":"<커밋>"}}}'`
- `platform/`(cert-manager · coredns · ingress-nginx · metallb · harbor · jenkins · argocd ingress)은 ArgoCD 밖이다

### 웹훅 · 알림

| 항목 | 값 |
| --- | --- |
| GitHub 웹훅 | `https://argocd.ronanlab.dev/api/webhook`. Cloudflare Access는 이 경로만 비켜 두고 서명(HMAC SHA-256)이 지킨다 |
| 알림 | `argocd-notifications-cm`: 서비스 `service.webhook.foreman`(`http://192.168.122.1:8001`, 토큰은 `argocd-notifications-secret`의 `$foreman-webhook-token`), 트리거 여섯 `foreman-out-of-sync` · `foreman-sync-running` · `foreman-sync-succeeded` · `foreman-sync-failed` · `foreman-health-degraded` · `foreman-deployed`, 구독 선택자 `app.kubernetes.io/instance=root`(루트가 만든 Application) |
| `argocd-cm` | `data` 비어 있음(2026-11-12 조회) |

### 처음 한 번 (다시 세울 때)

값은 여기 적지 않는다. `kubectl`은 m-k8s에서 치고, 저장소 파일은 호스트에 있으므로 `cd ~/k8s-cluster && vagrant ssh m-k8s -c '…' < 파일`처럼 표준 입력으로 넘긴다. 비밀값은 셸 변수 · 표준 입력으로만 다루고 명령 인자 · 화면에 내지 않는다.

**클러스터에만 있는 것(2026-11-12 조회, 이름만)**

| 무엇 | 자리 | 저장소 |
| --- | --- | --- |
| 알림 설정 | ConfigMap `argocd/argocd-notifications-cm` 키 9개(서비스 · 템플릿 · 트리거 6 · 구독) | `platform/argocd/notifications-cm.yaml`(2026-11-12 옮김, kubectl diff 0) |
| 알림 토큰 | Secret `argocd/argocd-notifications-secret` 키 `foreman-webhook-token`. 값은 foreman `.env.bridge`의 `FOREMAN_WEBHOOK_TOKEN`(Jenkins `jenkins/foreman-webhook-token`과 같은 값) | 없음(아래 명령) |
| GitHub 웹훅 시크릿 | Secret `argocd/argocd-secret` 키 `webhook.github.secret`. Jenkins의 `github-webhook-secret`과는 다른 값 | 없음(아래 명령) |
| admin 비밀번호 | Secret `argocd/argocd-secret` 키 `admin.password`(bcrypt). 2026-10-18 03:12 UTC에 사람이 ArgoCD 웹 화면에서 직접 바꿨다(`admin.passwordMtime`) | 없음(아래 2) |
| 저장소 읽기 키 | Secret `argocd/repo-ronanlab-infra` | `scripts/make-deploy-keys.sh` |
| 저장소 밖(사람이 대시보드에서) | GitHub `ronanlab-infra` 웹훅 · Deploy key, Cloudflare Access Bypass 앱(`/api/webhook`), DNS CNAME | 이 절의 순서 |

**순서**

```bash
# 1~5는 m-k8s 에서. 저장소 파일은 호스트에서 넘긴다:
#   매니페스트 vagrant ssh m-k8s -c 'kubectl apply -f -' < <파일>,  스크립트 vagrant ssh m-k8s -c 'bash -s' < <파일>
# 1. 설치(v2.13.2 고정). 매니페스트는 저장소에 없다
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/v2.13.2/manifests/install.yaml
bash platform/argocd/pin-infra.sh                      # w3(infra)에 고정. install.yaml 을 다시 apply 하면 다시 돌린다

# 2. admin 비밀번호(2026-10-18 에도 이렇게 웹 화면에서 바꿨다)
#    설치하면 처음 비밀번호가 Secret argocd/argocd-initial-admin-secret 키 password 에 생긴다(사용자 admin).
#    사람이 자기 터미널에서만 꺼내 로그인에 쓴다. 대화 · 기록 · 로그에 남기지 않는다:
#      kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d; echo
#    https://argocd.ronanlab.dev 에 admin 으로 로그인 → User Info → Update Password 에서 새 비밀번호로 바꾼다
#    (새 비밀번호는 argocd-secret 의 admin.password 에 bcrypt 로 들어간다). 바꾼 뒤 처음 비밀번호 Secret 을 지운다
kubectl -n argocd delete secret argocd-initial-admin-secret

# 3. 바깥 주소: 인증서(02의 cert-manager가 먼저) → Ingress
kubectl apply -f platform/cert-manager/argocd-certificate.yaml
kubectl apply -f platform/argocd/ingress.yaml

# 4. 저장소 읽기 deploy key → 출력된 공개 키를 GitHub ronanlab-infra → Settings → Deploy keys(쓰기 끔)
#    ssh -i <m-k8s 키> vagrant@192.168.122.10 'bash -s' < scripts/make-deploy-keys.sh

# 5. 루트 Application. 나머지 Application 은 루트가 apps/*/app.yaml 로 만든다
kubectl apply -f bootstrap/root-app.yaml
```

```bash
# 6. GitHub 웹훅 시크릿(호스트에서). 값은 셸 변수로만 만들고, GitHub 에는 사람이 붙여 넣는다
S=$(head -c 48 /dev/urandom | base64 | tr -dc A-Za-z0-9 | head -c 32)
printf '{"stringData":{"webhook.github.secret":"%s"}}' "$S" \
  | (cd ~/k8s-cluster && vagrant ssh m-k8s -c 'kubectl -n argocd patch secret argocd-secret --type merge --patch-file /dev/stdin')
(cd ~/k8s-cluster && vagrant ssh m-k8s -c 'kubectl -n argocd rollout restart deploy/argocd-server')   # 시크릿을 바꾸면 다시 띄워야 읽는다(3절 트러블슈팅)
#    GitHub ronanlab-infra → Settings → Webhooks: Payload URL https://argocd.ronanlab.dev/api/webhook,
#    Content type application/json(2026-11-12 사람이 GitHub 설정 화면에서 확인), Secret = $S, push 이벤트.
#    Cloudflare Access 에 /api/webhook 만 Bypass 하는 앱을 둔다. 끝나면 unset S

# 7. 알림(호스트에서). 토큰은 foreman 파일에서 셸 변수로 읽는다
T=$(sed -n 's/^FOREMAN_WEBHOOK_TOKEN=//p' ~/AI_programming/foreman/.env.bridge)
printf '{"stringData":{"foreman-webhook-token":"%s"}}' "$T" \
  | (cd ~/k8s-cluster && vagrant ssh m-k8s -c 'kubectl -n argocd patch secret argocd-notifications-secret --type merge --patch-file /dev/stdin'); unset T
(cd ~/k8s-cluster && vagrant ssh m-k8s -c 'kubectl apply -f -') < platform/argocd/notifications-cm.yaml
```

- `argocd-notifications-secret` · `argocd-secret`은 `install.yaml`이 빈 채로 만든다. 그래서 `create`가 아니라 `patch`다
- 1의 `install.yaml`에도 빈 `argocd-notifications-cm`이 있다. 다시 apply하면 알림 설정이 지워질 수 있다(확인하지 않음). 그 뒤에 7의 apply를 다시 한다
- 확인: `kubectl -n argocd get secret argocd-secret -o jsonpath='{.data}' | python3 -c 'import json,sys; print(sorted(json.load(sys.stdin)))'`에 `webhook.github.secret`, 같은 방식으로 `argocd-notifications-secret`에 `foreman-webhook-token`이 보이면 된다(값은 보지 않는다)

## 2. 왜 이렇게 했나

### GitOps가 뭘 바꾸나

지금까지 metrics-server, local-path-provisioner, nginx-ingress는 모두 `kubectl apply -f`로 **사람이 직접** 클러스터에 반영했다. 이 방식에는 세 가지 약점이 있다.

| 문제 | 설명 |
| --- | --- |
| 변경 이력이 없다 | 누가 언제 무엇을 바꿨는지 클러스터 어디에도 남지 않는다 |
| 되돌릴 방법이 없다 | 잘못 적용하면 기억에 의존해 수동으로 복구해야 한다 |
| 드리프트를 모른다 | 누군가 `kubectl edit`으로 몰래 바꿔도 알아챌 수 없다 |

**GitOps는 Git을 유일한 진실의 원천(single source of truth)으로 삼는다.**

```txt
지금      매니페스트 수정 → kubectl apply → 클러스터 반영
GitOps    매니페스트 수정 → Git push → ArgoCD가 감지 → 자동 반영
```

ArgoCD는 Git 저장소를 주기적으로 확인하면서, **클러스터의 실제 상태와 Git의 선언 상태가 다르면** 그 차이(diff)를 보여주고 동기화한다. 누가 손으로 바꿔놔도 Git과 다르면 드리프트로 표시되고, 자동 치유(self-heal)를 켜면 되돌린다.

IT시스템엔지니어링 기초 Day8에서 "ArgoCD 전에 `diff → apply → drift 치유`를 수동으로 연습해보는 것이 이해에 도움이 된다"고 정리했는데, 지금까지 9단계를 수동 `apply`로 진행한 것이 그 연습에 해당한다.

### Jenkins · Harbor와의 역할 분담

세 도구는 하나의 파이프라인을 이룬다.

```txt
GitHub 푸시 → Jenkins가 빌드 → Harbor에 이미지 저장
            → 매니페스트의 이미지 태그 갱신 → ArgoCD가 감지해 배포
```

| 도구 | 역할 | 영역 |
| --- | --- | --- |
| Jenkins | 코드가 바뀌면 빌드하고 이미지를 만든다 | CI |
| Harbor | 만든 이미지를 저장한다 | 레지스트리 |
| ArgoCD | 매니페스트대로 클러스터를 맞춘다 | CD |

**ArgoCD를 먼저 설치한 이유**: 셋 중 가장 가볍고(파드 7개), Jenkins · Harbor 없이도 단독으로 의미가 있다. GitHub에 매니페스트만 올려두면 그 자체로 GitOps가 성립한다. Harbor는 Trivy · Redis · PostgreSQL까지 딸려 와 파드가 10개를 넘고, 같은 서버에서 GPU 학습이 도는 동안에는 이미지 pull · 압축 해제가 몰리는 단계를 피하는 편이 안전하다고 판단했다.

### 버전을 고정한 이유

공식 문서는 `stable` 브랜치를 안내하지만, 그러면 설치 시점마다 버전이 달라져 재현이 안 된다. 4단계에서 kubeadm/kubelet/kubectl을 `v1.35`로 고정한 것과 같은 원칙이다.

### 각 컴포넌트의 역할

| 컴포넌트 | 하는 일 |
| --- | --- |
| application-controller | Git과 클러스터 상태를 비교하고 동기화한다. ArgoCD의 핵심 |
| repo-server | Git 저장소를 clone하고 매니페스트를 렌더링한다(Helm · Kustomize 포함) |
| server | API와 웹 UI를 제공한다 |
| dex-server | SSO(GitHub · Google 등) 인증을 처리한다. admin 로그인만 쓸 거면 없어도 된다 |
| redis | 렌더링 결과 등을 캐시한다 |
| applicationset-controller | 여러 Application을 템플릿으로 한 번에 관리한다 |
| notifications-controller | 동기화 결과를 Slack 등으로 알린다 |

### Ingress를 ArgoCD가 관리하지 않는 이유

이 Ingress는 ArgoCD가 아니라 사람이 넣는다(`kubectl apply -f platform/argocd/ingress.yaml`). ArgoCD가 자기에게 오는 길을 스스로 관리하지 않게 했다.

### `backend-protocol: "HTTPS"`가 필요한 이유

nginx-ingress는 기본적으로 백엔드에 HTTP로 요청한다. 그런데 `argocd-server`는 자체 인증서로 HTTPS를 받으므로(`server.insecure` 아님), 그대로 두면 502가 난다. ArgoCD 공식 문서에서도 안내하는 설정이다.

## 3. 진행 기록

ArgoCD 설치 → Ingress + Cloudflare Tunnel로 외부 노출 → GitOps 준비까지의 기록이다(2026-10-13). 그 뒤에 바뀐 것은 이 절 끝 「이후 진행」.

### 10-1단계: ArgoCD 설치

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/v2.13.2/manifests/install.yaml
```

#### 트러블슈팅: 설치 직후 에러가 뜬다

**증상**: 설치 직후 Pod 여럿이 `CreateContainerConfigError` · `CrashLoopBackOff`.

```txt
NAME                                                READY   STATUS                       RESTARTS
argocd-application-controller-0                     0/1     ContainerCreating            0
argocd-applicationset-controller-7bbdf77977-v7lmx   1/1     Running                      0
argocd-dex-server-87585c998-7cmdx                   0/1     PodInitializing              0
argocd-notifications-controller-7b9cb66776-ftqsn    1/1     Running                      0
argocd-redis-6d77db97b7-k49md                       0/1     Init:0/1                     0
argocd-repo-server-675f958d59-pcsb4                 0/1     CreateContainerConfigError   0
argocd-server-6769f6848f-9zrxd                      0/1     CreateContainerConfigError   0
```

**원인**: **대부분 서로를 기다리느라 생기는 일시적 상태**다. ArgoCD는 ConfigMap · Secret · Service가 모두 갖춰져야 각 컴포넌트가 뜨는데, `kubectl apply`가 리소스를 순차적으로 만드는 동안 먼저 생성된 파드가 아직 없는 설정을 참조하면서 실패한다.

**해결**: 기다린다. 1~2분 뒤:

```txt
NAME                                                READY   STATUS    RESTARTS
argocd-application-controller-0                     1/1     Running   0
argocd-applicationset-controller-7bbdf77977-v7lmx   1/1     Running   0
argocd-dex-server-87585c998-7cmdx                   1/1     Running   2 (67s ago)
argocd-notifications-controller-7b9cb66776-ftqsn    1/1     Running   0
argocd-redis-6d77db97b7-k49md                       1/1     Running   0
argocd-repo-server-675f958d59-pcsb4                 1/1     Running   0
argocd-server-6769f6848f-9zrxd                      1/1     Running   0
```

7개 전부 Running. `dex-server`의 RESTARTS 2는 기동 순서 때문이고 이후 안정됐다.

> 교훈: 설치 직후의 에러 상태를 보고 바로 고치려 들면 안 된다. 수업 Day4에서 배운 "`describe` Events 먼저" 전에, **먼저 1~2분 기다려보는 것**이 ArgoCD처럼 컴포넌트가 많은 스택에서는 더 유효하다.

### 10-2단계: 초기 비밀번호 확인

ArgoCD는 설치 시 `admin` 계정의 임시 비밀번호를 Secret으로 만든다.

```bash
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d; echo
```

`base64 -d`가 필요한 이유는 k8s Secret이 암호화가 아니라 **base64 인코딩**이기 때문이다(9단계에서도 같은 성질을 확인했다). 뒤의 `echo`는 줄바꿈을 붙여 프롬프트와 섞이지 않게 하려는 것이다.

> 공식 문서는 첫 로그인 후 비밀번호를 변경하고 이 Secret을 삭제할 것을 권한다. 지웠다. 2026-11-12 확인해도 `argocd-initial-admin-secret`은 없다(`NotFound`).

### 10-3단계: 외부 노출 (Ingress + 기존 터널 재사용)

9단계에서 "터널은 nginx-ingress만 바라보고, 새 앱은 Ingress 리소스만 추가한다"고 설계했다. ArgoCD가 **그 설계를 처음으로 검증하는 사례**가 됐다.

#### DNS 추가

```bash
cloudflared tunnel --config /dev/null route dns \
  02ad6a13-ce45-4262-a32a-40241bf034dc argocd.ronanlab.dev
```

- `--config /dev/null`을 붙인 이유는 9단계의 트러블슈팅과 같다. 기본 설정 파일(호스트 `~/.cloudflared/config.yml`)에 `tunnel: ollama-tunnel`이 적혀 있어, 생략하면 엉뚱한 터널로 CNAME이 연결된다(2026-11-12 호스트 조회에서도 그대로다)

#### 터널 설정에 호스트 추가

```bash
kubectl -n petmint create configmap cloudflared-config --from-literal=config.yaml='
tunnel: 02ad6a13-ce45-4262-a32a-40241bf034dc
credentials-file: /etc/cloudflared/creds/credentials.json
ingress:
  - hostname: petmint.ronanlab.dev
    service: https://ingress-nginx-controller.ingress-nginx.svc.cluster.local:443
    originRequest:
      noTLSVerify: true
  - hostname: argocd.ronanlab.dev
    service: https://ingress-nginx-controller.ingress-nginx.svc.cluster.local:443
    originRequest:
      noTLSVerify: true
  - service: http_status:404
' --dry-run=client -o yaml | kubectl apply -f -

kubectl -n petmint rollout restart deploy/cloudflared
```

- **`--dry-run=client -o yaml | kubectl apply -f -` 패턴**: `kubectl create configmap`은 이미 존재하면 거부한다. dry-run으로 YAML만 만든 뒤 `apply`에 넘기면 덮어쓸 수 있다. 선언형 방식을 유지하면서 기존 리소스를 갱신하는 관용적인 방법이다

**두 호스트가 같은 service를 가리킨다.** 라우팅은 nginx-ingress가 Host 헤더를 보고 처리하므로, 터널 입장에서는 둘 다 같은 목적지다.

> 지금은 이 ConfigMap을 손으로 만들지 않는다. 터널은 `cloudflared` 네임스페이스로 옮겼고(2026-10-18), `apps/cloudflared/configmap.yaml`을 고쳐 push → 수동 Sync → `kubectl -n cloudflared rollout restart deploy/cloudflared`([03_cloudflare_tunnel.md](03_cloudflare_tunnel.md), `apps/cloudflared/README.md`).

#### Ingress 리소스

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: argocd-server
  namespace: argocd
  annotations:
    nginx.ingress.kubernetes.io/backend-protocol: "HTTPS"
    nginx.ingress.kubernetes.io/ssl-redirect: "false"
spec:
  ingressClassName: nginx
  tls:
    - secretName: argocd-ingress-tls
      hosts:
        - argocd.ronanlab.dev
  rules:
    - host: argocd.ronanlab.dev
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: argocd-server
                port:
                  number: 443
```

위 YAML은 지금 파일(`platform/argocd/ingress.yaml`)이다. 전에는 m-k8s의 `~/argocd-ingress.yaml`로 apply했고, 이제 이 파일이 원본이다. 처음 넣은 것과 세 가지가 다르다.

| 처음 | 지금 | 이유 |
| --- | --- | --- |
| `ssl-passthrough: "true"` | 뺐다 | 컨트롤러가 `--enable-ssl-passthrough` 없이 떠서 원래도 동작하지 않았다. 켜지면 nginx가 TLS를 종단하지 않아 아래 인증서가 쓰이지 않는다 |
| TLS 없음(Cloudflare 엣지에서만) | `tls`: Secret `argocd-ingress-tls` | cert-manager가 Let's Encrypt(DNS-01)로 받는다(`platform/cert-manager/argocd-certificate.yaml`, [02_metrics_storage_ingress.md](02_metrics_storage_ingress.md)). 클러스터 안 · 사설망(MetalLB VIP)에서도 같은 이름으로 검증된 HTTPS로 부른다 |
| 없음 | `ssl-redirect: "false"` | Harbor · Jenkins와 맞춘다. 터널은 https로 붙고, 사설망 http(80) 경로도 그대로 둔다 |

#### 확인

```bash
curl -k -I https://argocd.ronanlab.dev
```

```txt
HTTP/2 200
date: Tue, 13 Oct 2026 10:19:48 GMT
content-type: text/html; charset=utf-8
content-security-policy: frame-ancestors 'self';
x-frame-options: sameorigin
server: cloudflare
cf-ray: a49d9ba8fc4018ce-NRT
```

`x-frame-options: sameorigin`과 `frame-ancestors 'self'`는 **ArgoCD가 직접 보낸 보안 헤더**다. Cloudflare가 아니라 백엔드까지 요청이 도달했다는 증거다.

```txt
argocd.ronanlab.dev
  → Cloudflare 엣지 (NRT, 도쿄)
  → petmint-tunnel (클러스터 내 Pod 2개)
  → nginx-ingress (Host 헤더로 분기)
  → argocd-server
```

(2026-10-13 당시 그림이다. 터널은 2026-10-18 `ronanlab-tunnel`로 이름을 바꿨고 지금 Pod 2개는 `cloudflared` 네임스페이스에 있다.)

브라우저 접속과 `admin` 로그인까지 확인했다.

> **9단계 설계가 의도대로 작동했다.** 터널 설정은 hostname 한 줄을 추가했을 뿐이고, 나머지는 Ingress 리소스 하나를 만든 것이 전부다. 앱이 늘어나도 터널은 건드리지 않는다는 전제가 실제로 성립했다.

**이 단계에서 Application을 만들지 않은 이유**: 당시에는 배포할 매니페스트가 없었다. petmint 앱 화면(펫퍼민트 문서 09번 UI)이 만들어진 뒤 그 매니페스트를 올리고 Application으로 연결했다([07_project_deploy.md](07_project_deploy.md)).

### 참고: VM 디스크는 넉넉하다 (2026-10-13)

Vagrantfile에 `machine_virtual_size = 20`(20GB)으로 적었지만, 실제 할당은 다르다.

```bash
for vm in m-k8s w1-k8s w2-k8s w3-k8s; do vagrant ssh $vm -c "df -h /"; done
```

```txt
/dev/mapper/ubuntu--vg-ubuntu--lv   62G  7.5G   52G  13% /
/dev/mapper/ubuntu--vg-ubuntu--lv   62G  7.3G   52G  13% /
/dev/mapper/ubuntu--vg-ubuntu--lv   62G  6.9G   52G  12% /
/dev/mapper/ubuntu--vg-ubuntu--lv   62G  7.1G   52G  12% /
```

3단계에서 `vagrant up` 시 나왔던 "Ignoring requested virtual disk size" 경고가 이것이었다. `generic/ubuntu2204` 박스의 기본 디스크(가상 128GiB, 그 안의 루트 LV 62GB)가 그대로 쓰였다([01_cluster.md](01_cluster.md)). 게다가 씬 프로비저닝이라 호스트 디스크는 실제 사용량만큼만 차지한다.

따라서 Harbor · Loki · Prometheus 단계에서 디스크가 부족할 우려는 없다고 봤다.

> 2026-11-12 다시 보면: w3는 Harbor를 모으면서(2026-11-10) 루트를 92G로 늘렸고 51G를 쓴다(59%). w4(2026-11-10 추가)는 62G 중 16G(27%).

### 이후 진행 (2026-11-10 기준, 2026-11-12 맞춤)

이 단계에서 "다음"으로 남겨 둔 것은 전부 했다.

| 항목 | 언제 | 내용 |
| --- | --- | --- |
| 매니페스트 저장소 | 2026-10-14 | `ronanlab-infra`(private, [06_jenkins.md](06_jenkins.md)). ArgoCD는 **읽기 전용 deploy key**로 읽는다 |
| Harbor · Jenkins | 2026-10-14 ~ 15 | [05_harbor.md](05_harbor.md) · [06_jenkins.md](06_jenkins.md) |
| Application | 2026-10-16 petmint, 10-18 runshoes | [07_project_deploy.md](07_project_deploy.md). 그때 petmint는 수동 Sync, runshoes는 자동 Sync. petmint는 2026-11-11부터 자동 |
| App of Apps | 2026-11-02 | 루트 Application(`bootstrap/root-app.yaml`) 하나만 사람이 넣고, 루트가 `apps/*/app.yaml`을 읽어 Application을 만든다 |
| GitHub 웹훅 | 2026-11-03 | `https://argocd.ronanlab.dev/api/webhook`. Access는 이 경로만 비켜 두고 서명(HMAC SHA-256)이 지킨다. push 뒤 6.2초에 새 커밋을 봤다(전에는 조회 3분) |
| 알림 | 2026-11-03 | notifications-controller → FOREMAN 웹훅. Sync 시작 · 성공 · 실패, OutOfSync, Degraded |
| harbor-backup · monitoring | 2026-11-10 | Harbor DB 백업 Application, 루트의 `exclude: 'monitoring/app.yaml'`을 빼서 모니터링을 넣었다 |
| ArgoCD → w3 | 2026-11-10 | `platform/argocd/pin-infra.sh`(커밋 `862182f`). 7개 모두 w3, 커밋 뒤 웹훅으로 12초 만에 새 커밋을 봤다([08_scale_out.md](08_scale_out.md)) |
| monitoring · petmint 자동 Sync | 2026-11-11 | 사용자 지시. cloudflared만 수동으로 남겼다 |

#### 트러블슈팅: 틀린 서명도 웹훅이 받았다

**증상**: 웹훅 시크릿을 넣은 뒤에도 틀린 서명이 200으로 처리됐다.

**원인**: **웹훅 시크릿은 argocd-server가 뜰 때 한 번 읽는다.** 키를 넣고 재시작하기 전이었다.

**해결**: `rollout restart deploy/argocd-server` 뒤에는 맞는 서명 10/10, 틀린 · 없는 서명 0/40 통과. 시크릿을 바꾸면 argocd-server를 다시 띄운다.

## 4. 남은 한계

- ArgoCD 자체는 `install.yaml`(v2.13.2)을 `kubectl apply`로 깔아 그 매니페스트가 저장소에 없다. 다시 apply하면 nodeSelector가 사라지므로 `platform/argocd/pin-infra.sh`를 다시 돌려야 한다
- 알림 설정(`argocd-notifications-cm`)과 웹훅 시크릿은 클러스터에만 있고 저장소에 없다
- w3(infra) 한 노드에만 뜬다. w3가 내려가면 배포(ArgoCD) · 빌드 · 레지스트리가 함께 멈춘다(떠 있는 앱 Pod는 그대로, [08_scale_out.md](08_scale_out.md))
- prune을 끄고 있어 git에서 지운 리소스는 클러스터에 남는다. 손으로 지운다
- 웹훅 시크릿을 바꾸면 argocd-server를 다시 띄워야 반영된다

## 5. 확인 방법

호스트에서 `cd ~/k8s-cluster && vagrant ssh m-k8s -c '…'`로 친다.

```bash
# Application 6개, cloudflared 만 AUTO <none>, 모두 Synced / Healthy
kubectl -n argocd get applications.argoproj.io \
  -o custom-columns=NAME:.metadata.name,PATH:.spec.source.path,REV:.spec.source.targetRevision,AUTO:.spec.syncPolicy.automated,SYNC:.status.sync.status,HEALTH:.status.health.status

# 7개 Pod 모두 Running, NODE 가 w3-k8s
kubectl -n argocd get pod -o wide

# 이미지 v2.13.2
kubectl -n argocd get deploy argocd-server -o jsonpath='{.spec.template.spec.containers[0].image}'; echo

# NotFound 가 나와야 한다
kubectl -n argocd get secret argocd-initial-admin-secret

# Ingress 와 알림 키 이름
kubectl -n argocd get ingress argocd-server
kubectl -n argocd get cm argocd-notifications-cm -o go-template='{{range $k,$v := .data}}{{$k}}{{"\n"}}{{end}}'
```

```bash
# 사설망(MetalLB VIP)으로 검증된 HTTPS. HTTP/2 200 (2026-11-12 확인, -k 없이)
curl -sI --resolve argocd.ronanlab.dev:443:192.168.122.240 https://argocd.ronanlab.dev | head -1
```

호스트에서 공개 주소 `curl -sI https://argocd.ronanlab.dev`는 Cloudflare Access가 앞에 있어 `HTTP/2 302`(로그인으로 보냄)가 나온다(2026-11-12 확인).

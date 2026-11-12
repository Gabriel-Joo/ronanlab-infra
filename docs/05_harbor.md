# 05. Harbor

Harbor(차트 1.19.2, 앱 2.15.2)를 Helm으로 클러스터 안에 세우고 Ingress와 기존 터널로 `harbor.ronanlab.dev`에 내놓았다. 지금은 컴포넌트와 데이터(PVC 다섯) 모두 w3(infra)에 모여 있고, DB는 매일 호스트로 백업한다.

- 날짜: 2026-10-14 구축, 2026-10-15 cert-manager 인증서, 2026-11-10 DB 백업 · w3로 이사, 2026-11-12 코드와 맞춤
- 범위: Harbor 설치 · values · 외부 노출 · 스토리지 · 백업. Harbor 이사(노드 배치)는 [08_scale_out.md](08_scale_out.md), 인증서 · MetalLB는 [02_metrics_storage_ingress.md](02_metrics_storage_ingress.md), 터널은 [03_cloudflare_tunnel.md](03_cloudflare_tunnel.md), Jenkins는 [06_jenkins.md](06_jenkins.md)
- 코드: `platform/harbor/values.yaml`, `platform/harbor/pvc-w3.yaml`, `apps/harbor-backup/`

## 1. 지금 구성

2026-11-12 클러스터 조회(`cluster_snapshot.txt` 09:18 KST, `helm history`, `kubectl get pod -o wide`)로 확인한 값이다.

| 항목 | 값 |
| --- | --- |
| Helm 릴리스 | `harbor`(네임스페이스 `harbor`), 차트 `harbor-1.19.2`, 앱 2.15.2, revision 3(2026-11-10 11:48 UTC). revision 1 설치 2026-10-14, 2 2026-10-15 |
| values | `platform/harbor/values.yaml`(platform/은 ArgoCD 밖, 사람이 helm으로 넣는다) |
| 컴포넌트 | core · portal · jobservice · registry(2/2) · database-0 · redis-0 · trivy-0, 모두 w3-k8s(`nodeSelector: node.ronanlab.dev/role: infra`) |
| 이미지 | `goharbor/harbor-core` · `harbor-portal` · `harbor-jobservice` · `registry-photon` · `harbor-registryctl` · `harbor-db` · `valkey-photon` · `trivy-adapter-photon`, 모두 v2.15.2 |
| 외부 주소 | `https://harbor.ronanlab.dev`, Ingress `harbor/harbor-ingress`(차트가 만든다), TLS Secret `harbor-tls`(cert-manager, `platform/cert-manager/harbor-certificate.yaml`) |
| 노드가 당기는 길 | 노드 containerd가 사설 VIP `192.168.122.240`(ingress-nginx, MetalLB)로 https 검증해 당긴다. 노드 `/etc/hosts`가 `harbor.ronanlab.dev`를 그 VIP로 보낸다 |
| 터널 | `ronanlab-tunnel`(`02ad6a13-ce45-4262-a32a-40241bf034dc`, 2026-10-18 전 이름 `petmint-tunnel`), `apps/cloudflared/configmap.yaml` |
| 프로젝트 | `library` · `petmint` · `runshoes`(2026-11-10 DB 백업 검증 때 확인) |

### PVC (지금 쓰는 것)

`platform/harbor/pvc-w3.yaml`로 사람이 만들고 values의 `existingClaim`으로 붙인다. 모두 local-path, w3-k8s, PV reclaimPolicy Retain.

| PVC | 크기 | 쓰는 곳 |
| --- | --- | --- |
| `harbor-registry-w3` | 30Gi | registry(이미지 레이어) |
| `harbor-database-w3` | 5Gi | database(PostgreSQL) |
| `harbor-redis-w3` | 1Gi | redis |
| `harbor-jobservice-w3` | 1Gi | jobservice 작업 로그 |
| `harbor-trivy-w3` | 5Gi | trivy |

합계 42Gi. w3 루트는 92G 중 51G를 쓴다(59%, 2026-11-12 `df -h /`).

**옛 PVC 다섯은 아직 남아 있다**(원본 보존, 사람이 지운다, `docs/TODO.md` 첫 줄). 모두 Retain.

| 옛 PVC | 크기 | 노드 |
| --- | --- | --- |
| `data-harbor-redis-0` | 1Gi | w1 |
| `harbor-jobservice` | 1Gi | w1 |
| `data-harbor-trivy-0` | 5Gi | w2 |
| `harbor-registry` | 20Gi | w2 |
| `database-data-harbor-database-0` | 5Gi | w3 |

### 백업

Harbor DB(`registry` 데이터베이스)는 CronJob `harbor-db-backup`(`45 3 * * *`, `Asia/Seoul`)이 매일 `pg_dump -Fc`로 호스트 NFS(`~/backup/harbor`)에 뜬다. ArgoCD Application `harbor-backup`(자동 Sync)이 `apps/harbor-backup`을 본다. 절차 · 복구 · 검증 기록은 `apps/harbor-backup/README.md`.

### values.yaml (지금 파일)

```yaml
expose:
  type: ingress
  tls:
    enabled: true            # 처음엔 false, 2026-10-15부터 cert-manager 인증서
    certSource: secret
    secret:
      secretName: harbor-tls
  ingress:
    hosts:
      core: harbor.ronanlab.dev
    className: nginx
    annotations:
      nginx.ingress.kubernetes.io/proxy-body-size: "0"
      nginx.ingress.kubernetes.io/ssl-redirect: "false"

externalURL: https://harbor.ronanlab.dev

# certSource: secret 이면 이 차트(1.19.2)는 core 의 ca-download 볼륨 secretName 을 비워 둔다. 같은 Secret 을 준다
caSecretName: harbor-tls

# 2026-11-10 데이터를 w3 한 곳으로. existingClaim 을 쓰면 차트가 PVC 를 만들지 않는다
persistence:
  enabled: true
  persistentVolumeClaim:
    registry:
      existingClaim: harbor-registry-w3
      storageClass: local-path
      size: 20Gi
    jobservice:
      jobLog:
        existingClaim: harbor-jobservice-w3
        storageClass: local-path
        size: 1Gi
    database:
      existingClaim: harbor-database-w3
      storageClass: local-path
      size: 5Gi
    redis:
      existingClaim: harbor-redis-w3
      storageClass: local-path
      size: 1Gi
    trivy:
      existingClaim: harbor-trivy-w3
      storageClass: local-path
      size: 5Gi

trivy:
  enabled: true
  nodeSelector: { node.ronanlab.dev/role: infra }

# 모든 구성 요소를 w3(infra)에 (cluster/label-nodes.sh)
portal:
  nodeSelector: { node.ronanlab.dev/role: infra }
core:
  nodeSelector: { node.ronanlab.dev/role: infra }
jobservice:
  nodeSelector: { node.ronanlab.dev/role: infra }
registry:
  nodeSelector: { node.ronanlab.dev/role: infra }
database:
  internal:
    nodeSelector: { node.ronanlab.dev/role: infra }
redis:
  internal:
    nodeSelector: { node.ronanlab.dev/role: infra }
```

(위는 저장소 파일의 값이고 주석은 줄였다. `size`는 `existingClaim`이 있으면 쓰이지 않는다. 실제 registry PVC는 30Gi.)

비밀 값: 저장소 파일에는 `harborAdminPassword`가 없다. 배포된 릴리스 값(`helm get values harbor`)에는 키 `harborAdminPassword`가 있다(값은 보지 않았다).

## 2. 왜 이렇게 했나

### 왜 레지스트리를 직접 세우나

빌드한 이미지는 어딘가에 올려둬야 클러스터가 받아갈 수 있다. Docker Hub를 쓰면 되지 않나 싶지만 두 가지가 걸린다. 공개 저장소라 사내 코드가 담긴 이미지를 올릴 수 없고, 무료 계정은 pull 횟수 제한이 있어 파드가 자주 재시작되는 환경에서 막힐 수 있다.

학교 Harbor(`std-harbor.kopoctc.kr`)를 재사용하려 했으나 서버 PC에서 DNS부터 풀리지 않아 내부망 전용으로 확인됐다(이 프로젝트 최상위 문서에 기록). 그래서 클러스터 안에 직접 세운다.

Harbor를 고른 이유는 **단순 저장소 이상이기 때문**이다. 프로젝트 단위 권한 분리, 로봇 계정, Trivy 취약점 스캔이 기본으로 들어있다. 뒤에서 Jenkins가 이미지를 밀어 넣을 때 admin 비밀번호를 파이프라인에 박지 않고 로봇 계정을 발급할 수 있는 것도 이 때문이다.

### Helm을 쓰는 이유

지금까지 metrics-server, local-path, nginx-ingress, ArgoCD는 모두 `kubectl apply -f`로 설치했다. Harbor는 Helm으로 간다.

Harbor는 컴포넌트가 7개(core, portal, registry, database, redis, jobservice, trivy)이고 그중 5개가 PVC를 쓴다. 매니페스트를 직접 쓰면 Deployment · Service · PVC · ConfigMap · Secret이 수십 개가 되고, 그 안에 호스트명과 비밀번호가 흩어져 들어간다. Helm은 그 값들을 `values.yaml` 한 곳으로 모아준다.

수업 Day8에서 "Helm 차트는 `values`로 환경별 값을 분리한다"고 정리한 것이 정확히 이 상황이다.

**차트 버전과 앱 버전은 다르다.** 차트 1.19.2가 Harbor 2.15.2를 설치한다. 차트는 "설치 방법"의 버전이고 앱은 "소프트웨어 자체"의 버전이라, 매니페스트만 고쳐도 차트 버전은 올라간다. 차트 1.19.2로 고정한다. ArgoCD를 `v2.13.2`로, kubeadm을 `v1.35`로 못박은 것과 같은 원칙이다.

**Helm은 kubectl과 마찬가지로 클러스터 밖에서 API 서버에 말을 거는 클라이언트**다. 노드마다 깔 필요가 없고, kubeconfig가 있는 곳에만 있으면 된다.

### TLS를 Harbor가 하지 않는다

Harbor 차트는 기본적으로 자체 인증서를 만들어 HTTPS를 직접 처리한다. 그런데 그러면 **self-signed 인증서를 노드 4대의 containerd에 전부 배포**해야 한다. 안 그러면 이미지 pull 시 인증서 검증에 실패한다.

대신 암호화를 Cloudflare에 맡겼다(처음 결정).

```txt
[외부] --HTTPS(Cloudflare 인증서)--> 엣지
       --터널(암호화된 아웃바운드)--> cloudflared Pod
       --평문 HTTP--> nginx-ingress --> Harbor
```

클러스터 내부 구간은 사설망이므로 평문으로 둔다. 9단계에서 터널 `service`를 `https://`로 쓰고 `noTLSVerify: true`를 붙인 것과 같은 판단이다. 검증할 가치가 없는 구간의 TLS는 끄는 편이 단순하다.

| 방식 | 인증서 관리 | 비고 |
| --- | --- | --- |
| Harbor가 TLS 처리 | 노드 4대에 CA 배포 필요 | 노드 추가 시마다 반복 |
| Cloudflare가 TLS 종료 (처음 채택) | 없음 | 내부 구간은 사설망 |
| cert-manager 공인 인증서 (지금, 2026-10-15) | 자동 발급 · 갱신 | 공인 CA라 노드에 배포할 것이 없다 |

> **바뀐 것 (2026-10-15)**: 이 결정은 배포 단계에서 바뀌었다. 노드(kubelet · containerd)가 Harbor에서 이미지를 당길 때는 Cloudflare를 거치지 않는다. 공개 주소로 나가면 Access에 막힌다. 그런데 Harbor는 토큰 주소를 `externalURL`(https, 포트 없음)로 알려 주므로, 노드는 사설망에서도 443으로 가서 인증서를 검증한다. 그래서 self-signed CA를 노드에 뿌리는 대신 **공인 인증서**를 받았다. cert-manager + Let's Encrypt DNS-01 → Secret `harbor-tls`, ingress-nginx는 MetalLB VIP `192.168.122.240`에 443을 열고, 노드 `/etc/hosts`가 `harbor.ronanlab.dev`를 그 VIP로 보낸다. 위 표의 "노드 4대에 CA 배포" 문제를 다른 방법으로 푼 것이다([02_metrics_storage_ingress.md](02_metrics_storage_ingress.md)).

### values 하나하나

| 값 | 기본값대로 두면 | 이유 |
| --- | --- | --- |
| `expose.type: ingress` | Service가 LoadBalancer로 생성돼 **Pending에서 영원히 멈춤** | 8단계에서 baremetal 매니페스트를 쓴 것과 같은 이유. 이 환경에는 클라우드 로드밸런서가 없다(설치 당시. MetalLB는 2026-10-15에 들어왔다) |
| `tls.enabled`와 `certSource: secret` | Harbor가 self-signed 인증서를 생성 | 처음엔 `false`(TLS는 Cloudflare가 종료). 2026-10-15부터 cert-manager가 만든 Secret `harbor-tls`를 쓴다. 위 "바뀐 것" |
| `caSecretName: harbor-tls` | core의 ca-download 볼륨 secretName이 빈다 | `certSource: secret`이면 이 차트(1.19.2)가 그 볼륨을 비워 둔다. 같은 Secret을 준다 |
| `proxy-body-size: "0"` | **이미지 push가 413으로 실패** | nginx-ingress의 기본 업로드 상한이 1MB다. 이미지 레이어는 수백 MB가 넘는다. `0`은 무제한 |
| `ssl-redirect: "false"` | 리다이렉트 루프 가능성 | Cloudflare가 이미 HTTPS로 받았는데 nginx가 또 HTTPS로 보내려 한다 |
| `externalURL` | docker login은 되는데 push가 깨짐 | Harbor가 클라이언트에게 "이 주소로 레이어를 올려라"고 응답할 때 쓰는 값이다. 내부 주소면 클라이언트가 접근할 수 없다 |
| `storageClass: local-path` | (7단계에서 기본값 지정했으므로 생략 가능) | 명시해두면 기본 StorageClass가 바뀌어도 영향받지 않는다 |
| `existingClaim` (2026-11-10~) | 차트가 PVC를 만들고, 처음 뜬 노드에 묶인다 | w3에 미리 만든 PVC(`pvc-w3.yaml`)를 쓴다. 이때 차트는 PVC를 만들지 않는다 |
| `nodeSelector: role=infra` (2026-11-10~) | 아무 워커에나 뜬다 | 컴포넌트 모두를 w3에 모은다(`cluster/label-nodes.sh`가 붙인 라벨) |

**`trivy.enabled: true`로 둔 이유**: 파드와 디스크를 더 쓰지만, 레지스트리에 올라온 이미지의 취약점을 자동 스캔한다. CI가 만든 이미지를 그대로 믿지 않고 한 번 더 검사하는 단계를 파이프라인에 넣을 수 있다.

### local-path의 한계를 알고 쓴다

Harbor의 PVC 5개는 모두 `local-path`를 쓴다. 7단계에서 정리한 대로 **PVC는 그 파드가 처음 뜬 노드의 로컬 디스크에 묶인다.** 즉 registry는 앞으로 그 노드에서만 뜰 수 있고, 그 노드가 죽으면 이미지에 접근할 수 없다.

이것은 버그가 아니라 의도된 동작이다. 데이터가 w1에 있는데 파드만 w2로 옮겨가면 빈 상태로 뜨게 되고, 그건 복구가 아니라 유실이다. local-path는 "데이터가 있는 곳에만 떠라"를 강제하는 것이다.

제대로 풀려면 NFS · Ceph · Longhorn 같은 분산 스토리지로 데이터를 여러 노드에 복제해야 한다. 그럼에도 지금 도입하지 않은 이유는 두 가지다.

- **무게**: Longhorn은 사실상 클러스터를 하나 더 얹는 수준이다. VM 4대에 Harbor · Jenkins · Prometheus · Loki를 올릴 예정인데 스토리지 레이어까지 더하면 리소스와 복잡도를 감당하기 어렵다
- **실익 없음**: VM이 전부 같은 물리 서버 한 대 위에 있다. 노드 간 복제를 해도 그 서버가 꺼지면 함께 꺼진다. 들인 품에 비해 얻는 가용성이 없다

상태를 가진 앱(Harbor registry, Milvus, PostgreSQL)은 노드에 묶이고, 상태 없는 앱(RAG API, UI)은 PVC를 쓰지 않으므로 어느 노드에서든 뜬다. 이 구분을 [07_project_deploy.md](07_project_deploy.md) 배포 설계에 그대로 적용했다.

그래서 2026-11-10에는 흩어진 PVC를 한 노드(w3)로 모았다. 묶이는 것은 피할 수 없으니, 묶이는 자리를 하나로 정해 "w3가 내려가면 Harbor 전체가 멈춘다" 하나만 남겼다(아래 진행 기록 「PVC가 노드에 흩어져 있었다」).

## 3. 진행 기록

Harbor 자체 구축(Helm) → Ingress + 기존 터널로 외부 노출 → 이미지 push 검증까지의 기록이다(2026-10-14).

### 10-4단계: Helm 설치

호스트에는 Helm v3.22가 이미 있었으나(학교 vcluster 작업 때 설치한 것으로 추정), **호스트 Helm은 이 클러스터를 바라보지 않는다.** kubeconfig가 m-k8s 안에 있기 때문이다. m-k8s에 별도로 설치했다.

```bash
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
helm version
```

```txt
version.BuildInfo{Version:"v3.22.0", ...}
```

### 10-5단계: 차트 저장소 추가와 버전 확인

```bash
helm repo add harbor https://helm.goharbor.io
helm repo update
helm search repo harbor/harbor --versions | head -5
```

```txt
NAME            CHART VERSION   APP VERSION
harbor/harbor   1.19.2          2.15.2
harbor/harbor   1.19.1          2.15.1
harbor/harbor   1.19.0          2.15.0
```

차트 1.19.2로 고정했다(까닭은 2절).

### 10-6단계: values.yaml

처음(2026-10-14) values는 `tls.enabled: false`, `caSecretName` 없음, `persistence`는 차트가 PVC를 만드는 꼴(`storageClass: local-path`, registry 20Gi · jobservice 1Gi · database 5Gi · redis 1Gi · trivy 5Gi), nodeSelector 없음, `harborAdminPassword: "(별도 관리)"`였다. 지금 파일은 1절, 값마다의 까닭은 2절.

그때 PVC 5개 합계 32Gi. [04_argocd.md](04_argocd.md) 「참고: VM 디스크는 넉넉하다」 기록대로 각 VM의 실제 디스크는 62GB(52GB 여유)여서 충분하다고 봤다.

#### 설치

```bash
kubectl create namespace harbor

helm install harbor harbor/harbor \
  --namespace harbor \
  --version 1.19.2 \
  -f ~/harbor-values.yaml
```

```txt
NAME                                 READY   STATUS    RESTARTS      AGE
harbor-core-77ff6fcb48-m8zz4         1/1     Running   0             50s
harbor-database-0                    1/1     Running   0             50s
harbor-jobservice-5898f74df6-jkxkj   0/1     Running   2 (30s ago)   50s
harbor-portal-677b5d5455-z965s       1/1     Running   0             50s
harbor-redis-6d77db97b7-...          1/1     Running   0             50s
harbor-registry-7bc588b44-5wmc8      2/2     Running   0             50s
harbor-trivy-0                       1/1     Running   0             50s
```

(그때는 m-k8s의 `~/harbor-values.yaml`을 썼다. 지금 원본은 `platform/harbor/values.yaml`이다.)

#### 트러블슈팅: jobservice가 두 번 재시작한다

**증상**: `jobservice`의 **RESTARTS 2**.

**원인**: ArgoCD의 `dex-server`와 같은 현상이다. core가 준비되기 전에 접속하려다 두 번 죽고 세 번째에 성공했다.

**해결**: 기다린다. 54초 시점에 `1/1`로 안정됐다.

> [04_argocd.md](04_argocd.md)에서 "설치 직후의 에러를 보고 바로 고치려 들지 말고 1~2분 기다려라"고 적었는데, 두 번째로 같은 패턴을 확인했다. 컴포넌트가 많은 Helm 스택에서는 **기동 순서로 인한 재시작이 기본값**이라고 봐야 한다.

`harbor-database-0`, `harbor-redis-0`, `harbor-trivy-0`의 이름 끝 `-0`은 이들이 **StatefulSet**이라는 뜻이다. 수업 Day6에서 "Milvus는 StatefulSet으로"라고 정리한 것과 같은 이유다. 상태를 가진 컴포넌트는 `volumeClaimTemplates`로 각자 전용 PVC를 받아야 한다. Harbor 차트가 이미 그렇게 설계돼 있다.

### 10-7단계: 외부 노출

9단계 설계대로, **터널에 hostname 한 줄 추가**가 전부다.

```bash
cloudflared tunnel --config /dev/null route dns \
  02ad6a13-ce45-4262-a32a-40241bf034dc harbor.ronanlab.dev
```

- `--config /dev/null`은 9단계의 트러블슈팅 그대로다. 생략하면 기본 config의 `tunnel: ollama-tunnel`이 적용돼 엉뚱한 터널로 CNAME이 붙는다

> `cloudflared` CLI는 **호스트에만 있다.** 클러스터 안에 있는 것은 터널 Pod이지 CLI가 아니다. m-k8s에서 실행하면 `command not found`가 난다. 반대로 `kubectl`은 m-k8s에만 있다. 두 머신을 오가는 작업이라 어느 쪽에서 치는 명령인지 매번 확인해야 한다.

터널 ConfigMap에 harbor 호스트 추가:

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
  - hostname: harbor.ronanlab.dev
    service: https://ingress-nginx-controller.ingress-nginx.svc.cluster.local:443
    originRequest:
      noTLSVerify: true
  - service: http_status:404
' --dry-run=client -o yaml | kubectl apply -f -

kubectl -n petmint rollout restart deploy/cloudflared
```

> 지금은 이 ConfigMap을 손으로 만들지 않는다. 터널은 `cloudflared` 네임스페이스로 옮겼고(2026-10-18), `apps/cloudflared/configmap.yaml`을 고쳐 push → 수동 Sync → `kubectl -n cloudflared rollout restart deploy/cloudflared`([03_cloudflare_tunnel.md](03_cloudflare_tunnel.md), `apps/cloudflared/README.md`).

**Ingress 리소스는 따로 만들지 않았다.** ArgoCD 때는 직접 작성했지만, Harbor는 `expose.type: ingress`를 준 순간 차트가 만들어준다(`harbor-ingress`). Helm을 쓸 때의 차이다.

```bash
kubectl -n harbor get ingress
```

### 10-8단계: 검증

UI 접속과 레지스트리 동작은 **다른 문제다.** 포털은 평범한 웹 앱이지만 레지스트리는 Docker Registry HTTP API v2라는 별도 프로토콜을 쓰고, 업로드 상한과 `externalURL`이 걸리는 지점도 거기다. 그래서 둘을 따로 확인한다.

브라우저에서 `harbor.ronanlab.dev` 접속, `admin` 로그인 확인. 이어서 실제 push:

```bash
docker pull alpine
docker tag alpine harbor.ronanlab.dev/library/alpine:test
docker push harbor.ronanlab.dev/library/alpine:test
```

```txt
The push refers to repository [harbor.ronanlab.dev/library/alpine]
e2de96513ba9: Pushed
test: digest: sha256:d56c381f961d... size: 1022

i Info → Not all multiplatform-content is present and only the
         available single-platform image was pushed
```

**Info 메시지는 정상이다.** alpine은 amd64 · arm64 등을 묶은 멀티플랫폼 이미지인데, 호스트가 amd64라 해당 아키텍처만 올라갔다는 안내다.

> `docker` 명령은 **호스트에서** 실행했다. m-k8s에는 docker가 없고, 깔아서도 안 된다. k8s 노드는 containerd를 쓰며 docker를 함께 설치하면 충돌 소지가 있다. 실제 빌드에 쓴 BuildKit rootless([06_jenkins.md](06_jenkins.md))도 빌드 Pod 안에서 돌아 노드에 docker가 필요하지 않다.

경로의 `library`는 Harbor가 기본 생성하는 **public 프로젝트**다. 실제 배포용 이미지는 `petmint` 프로젝트를 private으로 따로 만들어 쓴다([07_project_deploy.md](07_project_deploy.md)).

검증용 이미지는 삭제했다.

```bash
docker rmi harbor.ronanlab.dev/library/alpine:test
```

```txt
harbor.ronanlab.dev
  → Cloudflare 엣지 (NRT, 도쿄)
  → petmint-tunnel (클러스터 내 Pod 2개)
  → nginx-ingress (Host 헤더로 분기)
  → harbor-portal / harbor-core / harbor-registry
```

(2026-10-14 당시 그림이다. 터널은 2026-10-18 `ronanlab-tunnel`로 이름을 바꿨고 지금 Pod 2개는 `cloudflared` 네임스페이스에 있다.)

> **9단계 설계가 두 번째로 검증됐다.** ArgoCD에 이어 Harbor도 터널 설정은 hostname 한 줄 추가가 전부였고, Ingress는 차트가 알아서 만들었다. "앱이 늘어나도 터널은 건드리지 않는다"는 전제가 두 번 연속 성립했다.

### 그때 세운 다음 계획: Jenkins

| 항목 | 내용 |
| --- | --- |
| 컨트롤러 | Helm + Ingress + 터널 hostname 추가 (Harbor와 동일 패턴) |
| 빌드 방식 | 계획은 Kaniko. 실제로는 BuildKit rootless([06_jenkins.md](06_jenkins.md)). 둘 다 특권 컨테이너 없이 이미지 빌드 |
| Harbor 자격증명 | 로봇 계정 발급 후 Secret 주입 (admin 비밀번호를 파이프라인에 넣지 않는다) |
| 권한 | Jenkins가 Kaniko 파드를 생성할 ServiceAccount + RBAC |
| 트리거 | GitHub webhook. 외부에서 들어오므로 터널 노출 필수 |

**Kaniko를 고른 이유(계획 당시)**: 컨테이너 안에서 이미지를 빌드하는 전통적 방법(DinD, Docker-in-Docker)은 `privileged: true`를 요구한다. 그 파드가 뚫리면 노드 전체가 뚫리는 구조다. Kaniko는 사용자 공간에서 레이어를 직접 조립해 데몬도 특권도 필요 없다. 설정이 조금 번거로운 대신, 왜 특권이 필요 없게 만들었는지를 설명할 수 있다. 실제 파이프라인은 같은 목표(특권 없음)를 BuildKit rootless로 이뤘다([06_jenkins.md](06_jenkins.md)).

### 2026-10-15: cert-manager 인증서로 TLS

helm revision 2. `tls.enabled: true`, `certSource: secret`, Secret `harbor-tls`, `caSecretName: harbor-tls`. 까닭은 2절 「TLS를 Harbor가 하지 않는다」의 "바뀐 것".

### 2026-11-10: PVC가 노드에 흩어져 있었다

위 「local-path의 한계」에서 예고한 "그 노드에 묶인다"가 실제로 어떻게 됐는지다. 각 PVC는 처음 뜬 노드에 생겼고, 그 노드들이 제각각이었다(이관 전 확인).

```bash
kubectl get pv -o custom-columns=PVC:.spec.claimRef.name,NODE:.spec.nodeAffinity.required.nodeSelectorTerms[0].matchExpressions[0].values[0] | grep harbor
```

```txt
data-harbor-redis-0               w1-k8s
harbor-jobservice                 w1-k8s
data-harbor-trivy-0               w2-k8s
harbor-registry                   w2-k8s
database-data-harbor-database-0   w3-k8s
```

| 내려가는 노드 | 멈추는 것 |
| --- | --- |
| w1 | Harbor 로그인 · push(redis · jobservice) |
| w2 | 이미지 pull · push(registry, 레이어 20Gi) |
| w3 | Harbor 전체(database) |

어느 워커를 내려도 Harbor 일부가 멈췄다. 2026-11-10 노드를 하나씩 증설할 때는 앱 Pod를 Harbor가 살아 있는 동안 먼저 다른 노드로 옮겨 이미지를 받게 한 뒤 노드를 내렸다.

### 2026-11-10: 백업 (Harbor DB)

Harbor의 프로젝트 · 로봇 계정 · 태그 · 정책은 전부 `harbor-database`(PostgreSQL)의 `registry` 데이터베이스에 있다. 이것을 하루 한 번 떠서 호스트에 둔다.

| 항목 | 값 |
| --- | --- |
| 방식 | CronJob `harbor-db-backup`, 매일 03:45 KST `pg_dump -Fc` |
| 클라이언트 | 서버와 같은 이미지 `goharbor/harbor-db:v2.15.2`(PostgreSQL 18.3). pg_dump가 서버보다 낮으면 실패한다 |
| 어디로 | 호스트 NFS 쓰기 export(`~/backup/harbor`) |
| 반쪽짜리 방지 | `.part`로 쓰고 `pg_restore -l` 목차에 테이블 데이터가 있어야 이름을 바꾼다 + sha256 |
| 보존 | 30일, 최신 7개는 날짜와 상관없이 남긴다 |
| 관리 | ArgoCD Application `harbor-backup`(`apps/harbor-backup`). Harbor 자체는 Helm 그대로고 백업만 git으로 |

**복구되는지까지 봤다.** 운영 DB를 덮지 않고, 같은 이미지로 따로 띄운 시험 Pod(emptyDir, Service 선택자와 다른 라벨)에 넣고 행 수를 맞췄다.

```txt
백업 harbor-registry-20261110-185750.dump 500480바이트, 테이블 데이터 49개
복구 0.46초, 49개 테이블 행 수 운영과 같음(총 16,260행)
artifact 246 · tag 246 · project 3 · repository 3 · robot 4 · harbor_user 2
schema_migrations 180/f, 프로젝트 library · petmint · runshoes: 운영과 같음
```

복구 절차는 `apps/harbor-backup/README.md` 「복구」.

### 2026-11-10: w3로 이사

helm revision 3(커밋 `2570d50`). `platform/harbor/pvc-w3.yaml`로 w3에 새 PVC 다섯을 만들고, values에 `existingClaim`과 `nodeSelector: role=infra`를 넣었다. registry는 16GB를 쓰고 있어 새 PVC를 30Gi로 잡았다. 이사 직전 DB 백업 → Harbor 정지 → 노드 간 tar(registry 3,408파일 16.9GB, 73초) → 파일 목록 md5 원본과 같음 → `helm upgrade`. Harbor가 멈춘 시간은 약 4분, DB 49개 테이블 행 수 이사 전과 같음. w3 루트를 62G → 92G로 늘렸다. 상세는 [08_scale_out.md](08_scale_out.md).

옛 PVC 다섯은 지우지 않고 남겼다(원본 보존). registry · jobservice의 옛 PVC는 차트가 `helm.sh/resource-policy: keep`을 달아 `helm upgrade`로도 지워지지 않고, database · redis · trivy의 옛 PVC는 StatefulSet `volumeClaimTemplates`가 만든 것이라 helm이 관리하지 않는다.

## 4. 남은 한계

- **w3 한 노드에 모았다.** w3가 내려가면 Harbor 전체가 멈춘다(떠 있는 앱 Pod는 이미지를 노드에 갖고 있어 그대로). ArgoCD · Jenkins도 w3라 배포 · 빌드가 함께 멈춘다([08_scale_out.md](08_scale_out.md))
- **옛 PVC 다섯이 남아 있다**(w1 · w2 · w3, 합계 32Gi, `harbor-registry` w2는 약 16GB). 새 쪽이 며칠 정상으로 돈 뒤 사람이 지운다(`docs/TODO.md`). 모두 Retain이라 PVC를 지워도 PV · 데이터는 남으니 PV도 따로 정리해야 한다
- **이미지 레이어(registry PVC)는 백업하지 않는다.** DB만 있으면 프로젝트 · 로봇 계정 · 정책은 돌아오지만 레이어가 없는 태그는 pull이 안 된다. 앱 이미지는 앱 저장소 커밋에서 Jenkins로 다시 빌드할 수 있다는 것을 전제로 한다
- 백업이 운영 디스크와 같은 물리 서버에 있다. 2절 "실익 없음"과 같은 이야기다(다른 디스크 · 바깥으로 한 벌 더는 `docs/TODO.md`)
- Harbor를 올리면 `apps/harbor-backup/cronjob.yaml`의 `goharbor/harbor-db` 태그도 같이 올려야 한다(pg_dump가 서버보다 낮으면 실패)
- 저장소의 `values.yaml`에는 `harborAdminPassword`가 없고, 배포된 릴리스 값에는 있다. 다음 `helm upgrade` 때 이 값을 어떻게 넣는지는 정해지지 않음
- local-path라 분산 스토리지가 없다(2절)

## 5. 확인 방법

호스트에서 `cd ~/k8s-cluster && vagrant ssh m-k8s -c '…'`로 친다.

```bash
# harbor-1.19.2 / 2.15.2, deployed
helm -n harbor list
helm -n harbor history harbor

# 컴포넌트 모두 Running, NODE 가 w3-k8s
kubectl -n harbor get pod -o wide

# 쓰는 PVC 다섯(harbor-*-w3)이 w3, Retain
kubectl get pv -o custom-columns=CLAIM:.spec.claimRef.name,RECLAIM:.spec.persistentVolumeReclaimPolicy,NODE:.spec.nodeAffinity.required.nodeSelectorTerms[0].matchExpressions[0].values[0] | grep harbor
kubectl -n harbor get pod -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.spec.volumes[*].persistentVolumeClaim.claimName}{"\n"}{end}'

# 사설망(VIP)으로 검증된 HTTPS. Pong 이 나와야 한다(2026-11-12 확인)
curl -s --resolve harbor.ronanlab.dev:443:192.168.122.240 https://harbor.ronanlab.dev/api/v2.0/ping; echo

# 백업 CronJob 45 3 * * * Asia/Seoul, 최근 Job Completed
kubectl -n harbor get cronjob harbor-db-backup
kubectl -n harbor get job
```

호스트에서 `ls -l ~/backup/harbor/`로 최신 `.dump`와 `.sha256`이 있는지 보고 `sha256sum -c`로 확인한다.

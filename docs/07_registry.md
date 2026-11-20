<!--
다루는 곳: platform/harbor/, apps/harbor-backup/, scripts/host-nfs-harbor-backup-setup.sh
읽은 커밋: 736d833
-->
# 이미지 저장소

Harbor를 Helm으로 클러스터 안에 세웠다. ArgoCD 밖이고, DB 백업 CronJob만 ArgoCD가 넣는다. 이력은 옛 구축 기록에 있다. [docs:history/build_log/05_harbor.md] [code:bootstrap/root-app.yaml:13]

## 지금 구성

- Helm 릴리스 `harbor`, 네임스페이스 `harbor`, 차트 `harbor/harbor` 1.19.2(앱 2.15.2), 차트 저장소 `https://helm.goharbor.io` [code:platform/versions.yaml:44-48] [docs:history/cluster_state_20261116.md:67]
- 바깥 주소 `https://harbor.ronanlab.dev`(`externalURL`). Ingress는 차트가 만들고 className `nginx` [code:platform/harbor/values.yaml:10-18]
- TLS Secret `harbor-tls`는 cert-manager Certificate(`platform/cert-manager/harbor-certificate.yaml`, ClusterIssuer `letsencrypt-prod`)가 만든다 [code:platform/cert-manager/harbor-certificate.yaml:1-13]
- 노드 containerd는 `/etc/hosts`의 `192.168.122.240 harbor.ronanlab.dev`(ingress-nginx의 MetalLB VIP)로 가서 https를 검증해 당긴다. 공개 DNS로 가면 Cloudflare Access에 막힌다 [code:cluster/Vagrantfile:32-36] [code:platform/harbor/values.yaml:4]
- 공개 경로는 터널 `apps/cloudflared/configmap.yaml`의 `harbor.ronanlab.dev` 항목, Access 「운영도구」 앱 뒤에 있다 [code:apps/cloudflared/configmap.yaml:22-25] [code:apps/cloudflared/configmap.yaml:35]
- 구성 요소 portal, core, jobservice, registry, database, redis, trivy 모두 `node.ronanlab.dev/role: infra`(w3) [code:platform/harbor/values.yaml:54-72] [code:cluster/label-nodes.sh:13]
- 프로젝트 `library`, `petmint`, `runshoes` [repo:apps/harbor-backup/README.md:55]

### PVC (지금 쓰는 것)

모두 local-path, w3, `platform/harbor/pvc-w3.yaml`로 사람이 만들고 values의 `existingClaim`으로 붙인다. PV reclaimPolicy는 다섯 모두 Retain으로 바꿔 두었다 [code:platform/harbor/pvc-w3.yaml:4-7]

| PVC | 크기 | 쓰는 곳 |
| --- | --- | --- |
| `harbor-registry-w3` | 30Gi | registry(이미지 레이어). `helm.sh/resource-policy: keep` [code:platform/harbor/pvc-w3.yaml:10-18] |
| `harbor-database-w3` | 5Gi | database(PostgreSQL) [code:platform/harbor/pvc-w3.yaml:33-38] |
| `harbor-trivy-w3` | 5Gi | trivy [code:platform/harbor/pvc-w3.yaml:53-58] |
| `harbor-redis-w3` | 1Gi | redis [code:platform/harbor/pvc-w3.yaml:43-48] |
| `harbor-jobservice-w3` | 1Gi | jobservice 작업 로그 [code:platform/harbor/pvc-w3.yaml:23-28] |

옛 PVC 다섯이 남아 있다(원본 보존, 사람이 지운다) [docs:TODO.md:7]

- `harbor-registry`(w2), `harbor-jobservice`(w1): 차트가 `helm.sh/resource-policy: keep`을 달아 helm이 지우지 않는다 [code:platform/harbor/pvc-w3.yaml:2]
- `database-data-harbor-database-0`(w3), `data-harbor-redis-0`(w1), `data-harbor-trivy-0`(w2): StatefulSet volumeClaimTemplates가 만든 것, helm이 관리하지 않는다 [code:platform/harbor/pvc-w3.yaml:3]

### DB 백업

- ArgoCD Application `harbor-backup`(자동 Sync, prune와 selfHeal 끔, finalizer 없음)이 `apps/harbor-backup`을 `harbor` 네임스페이스에 넣는다 [code:apps/harbor-backup/app.yaml:1-4] [code:apps/harbor-backup/app.yaml:15-22]
- CronJob `harbor-db-backup`: `45 3 * * *`, `Asia/Seoul`, `concurrencyPolicy: Forbid`, `activeDeadlineSeconds: 900` [code:apps/harbor-backup/cronjob.yaml:17-26]
- 대상은 `harbor-database`의 `registry` 데이터베이스. `pg_dump -Fc -Z 6 --no-owner` [code:apps/harbor-backup/cronjob.yaml:3] [code:apps/harbor-backup/cronjob.yaml:62]
- 이미지 `docker.io/goharbor/harbor-db:v2.15.2`(서버와 같은 이미지, PostgreSQL 18.3) [code:apps/harbor-backup/cronjob.yaml:7] [code:apps/harbor-backup/cronjob.yaml:39]
- 암호는 Secret `harbor-database` 키 `POSTGRES_PASSWORD`(차트가 만든다)를 `PGPASSWORD`로 [code:apps/harbor-backup/cronjob.yaml:45-47]
- `.part`로 쓰고 `pg_restore -l` 목차에 `TABLE DATA`가 있어야 이름을 바꾼다. 그 뒤 `.sha256`을 남긴다 [code:apps/harbor-backup/cronjob.yaml:62-67]
- 보존: 최신 7개(`KEEP_MIN`) 뒤의 것 중 30일(`RETAIN_DAYS`) 지난 것만 지운다 [code:apps/harbor-backup/cronjob.yaml:50-53] [code:apps/harbor-backup/cronjob.yaml:69-72]
- 쓰는 곳: PV/PVC `harbor-backup`(RWX, 5Gi 표시, Retain), NFS `192.168.122.1:/srv/nfs/backup/harbor`, `nfsvers=4.2` [code:apps/harbor-backup/cronjob.yaml:87-113]
- 호스트 쪽: `~/backup/harbor`를 `/srv/nfs/backup/harbor`에 bind mount하고 `192.168.122.0/24`에 rw, `all_squash`(호스트 사용자로 써짐), `fsid=105`로 export한다 [code:scripts/host-nfs-harbor-backup-setup.sh:8-18] [code:scripts/host-nfs-harbor-backup-setup.sh:31]

## 설정 자리

| 파일:줄 | 값 | 뜻 |
| --- | --- | --- |
| `platform/harbor/values.yaml:2` | `expose.type: ingress` | LoadBalancer Service를 만들지 않고 ingress-nginx 뒤에 둔다 |
| `platform/harbor/values.yaml:5-9` | `tls.enabled: true`, `certSource: secret`, `harbor-tls` | cert-manager가 만든 공인 인증서를 쓴다 |
| `platform/harbor/values.yaml:15` | `proxy-body-size: "0"` | 업로드 상한 없음. 기본 상한이면 이미지 push가 413으로 실패한다 [docs:history/build_log/05_harbor.md:217] |
| `platform/harbor/values.yaml:16` | `ssl-redirect: "false"` | 터널은 https로 붙고 사설망 http 경로도 둔다 [code:platform/argocd/ingress.yaml:7] |
| `platform/harbor/values.yaml:18` | `externalURL` | 토큰 주소. https라 노드도 인증서를 검증한다 [code:platform/harbor/values.yaml:4] |
| `platform/harbor/values.yaml:21` | `caSecretName: harbor-tls` | `certSource: secret`이면 차트 1.19.2가 core의 ca-download 볼륨 secretName을 비운다 [code:platform/harbor/values.yaml:20] |
| `platform/harbor/values.yaml:26-52` | `existingClaim` 다섯 | 차트가 PVC를 만들지 않는다. `size`는 existingClaim을 떼면 쓰인다 [code:platform/harbor/values.yaml:32-34] |
| `platform/harbor/values.yaml:54-72` | `nodeSelector` infra | 모든 구성 요소를 w3에 |
| `apps/harbor-backup/cronjob.yaml:39` | `goharbor/harbor-db:v2.15.2` | Harbor를 올리면 같이 올린다. pg_dump가 서버보다 낮으면 실패한다 |
| `apps/harbor-backup/cronjob.yaml:34-36` | `runAsUser: 999` | 이미지의 postgres 사용자. NFS all_squash라 호스트에서는 호스트 사용자 파일이 된다 |
| `scripts/host-nfs-harbor-backup-setup.sh:18` | `FSID=105` | 101~103은 약관(ro), 104는 petmint MySQL 백업 |

## 바꾸거나 다시 만들기

kubectl과 helm은 m-k8s에서 친다. 비밀번호는 셸 변수와 표준 입력으로만 넘긴다. [docs:history/build_log/05_harbor.md:143]

values를 바꿔 다시 넣기. `--reuse-values`는 쓰지 않는다(앞의 값을 덮는다). `harborAdminPassword`는 저장소에 없어 Secret에서 읽어 같은 값을 다시 넘긴다. 빠뜨리면 차트 기본값이 들어간다 [docs:history/build_log/05_harbor.md:154-162]

```bash
P=$(kubectl -n harbor get secret harbor-core -o jsonpath='{.data.HARBOR_ADMIN_PASSWORD}' | base64 -d)
printf %s "$P" | helm upgrade harbor harbor/harbor --version 1.19.2 -n harbor \
  -f platform/harbor/values.yaml --set-file harborAdminPassword=/dev/stdin; unset P
```

처음부터 다시 세우기 [docs:history/build_log/05_harbor.md:136-151]

```bash
helm repo add harbor https://helm.goharbor.io && helm repo update
kubectl create namespace harbor
kubectl apply -f platform/cert-manager/harbor-certificate.yaml   # TLS Secret harbor-tls
kubectl apply -f platform/harbor/pvc-w3.yaml                     # PVC 다섯. 첫 Pod 가 w3 에 뜨면 PV 가 w3 에 생긴다
P=$(head -c 48 /dev/urandom | base64 | tr -dc A-Za-z0-9 | head -c 24)
printf %s "$P" | helm install harbor harbor/harbor --version 1.19.2 -n harbor \
  -f platform/harbor/values.yaml --set-file harborAdminPassword=/dev/stdin; unset P
# PV 를 Retain 으로(local-path 기본은 Delete)
for c in harbor-registry-w3 harbor-database-w3 harbor-redis-w3 harbor-jobservice-w3 harbor-trivy-w3; do
  kubectl patch pv "$(kubectl -n harbor get pvc $c -o jsonpath='{.spec.volumeName}')" -p '{"spec":{"persistentVolumeReclaimPolicy":"Retain"}}'
done
```

- 비밀번호는 사람이 비밀번호 관리 자리에 따로 둔다. 프로젝트와 robot 계정은 DB 백업으로 돌아오고, 다시 만드는 법은 `apps/petmint/README.md`, `apps/runshoes/README.md` 「처음 한 번」이다 [docs:history/build_log/05_harbor.md:132]
- 백업용 호스트 준비는 sudo가 필요하다. 세션은 치지 않고 사람에게 `sudo scripts/host-nfs-harbor-backup-setup.sh` 한 줄로 알린다. 여러 번 돌려도 같고 nfs-server를 재시작하지 않는다 [code:scripts/host-nfs-harbor-backup-setup.sh:3-10]
- Harbor 판을 올리면 `platform/versions.yaml`과 `apps/harbor-backup/cronjob.yaml`의 이미지 태그를 같은 커밋에서 고친다 [code:platform/versions.yaml:6] [repo:apps/harbor-backup/README.md:17]

백업을 손으로 한 번 뜨기 [repo:apps/harbor-backup/README.md:21-24]

```bash
kubectl -n harbor create job --from=cronjob/harbor-db-backup harbor-db-backup-manual-$(date +%H%M)
```

DB 복구는 `apps/harbor-backup/README.md` 「복구」를 따른다. 운영 DB를 덮기 전에 시험 DB에 먼저 넣어 행 수를 본다. 옛 DB는 `registry_old`로 남기고 지우지 않는다 [repo:apps/harbor-backup/README.md:26-44]

## 확인

```bash
# harbor-1.19.2 / 2.15.2, deployed
helm -n harbor list

# 구성 요소 모두 Running, NODE 가 w3-k8s
kubectl -n harbor get pod -o wide

# 쓰는 PVC 다섯(harbor-*-w3)이 w3, Retain
kubectl get pv -o custom-columns=CLAIM:.spec.claimRef.name,RECLAIM:.spec.persistentVolumeReclaimPolicy,NODE:.spec.nodeAffinity.required.nodeSelectorTerms[0].matchExpressions[0].values[0] | grep harbor

# 사설망(VIP)으로 검증된 HTTPS. Pong
curl -s --resolve harbor.ronanlab.dev:443:192.168.122.240 https://harbor.ronanlab.dev/api/v2.0/ping; echo

# 백업 CronJob 과 최근 Job Completed
kubectl -n harbor get cronjob harbor-db-backup
kubectl -n harbor get job
```

호스트에서 `ls -l ~/backup/harbor/`로 최신 `.dump`와 `.sha256`을 보고, 그 폴더에서 `sha256sum -c harbor-registry-<날짜>.dump.sha256`이 OK여야 한다 [repo:apps/harbor-backup/README.md:32]

## 알려진 한계

- 모든 구성 요소와 데이터가 w3에 있다. w3가 내려가면 Harbor 전체가 멈춘다. 떠 있는 앱 파드는 이미지를 노드에 갖고 있어 그대로다 [code:cluster/label-nodes.sh:7]
- 이미지 레이어(`harbor-registry-w3`)는 백업하지 않는다. 레이어가 없는 태그는 pull이 안 되고, 앱 저장소 커밋에서 Jenkins로 다시 빌드하는 것을 전제로 한다 [repo:apps/harbor-backup/README.md:15-16]
- 백업이 운영과 같은 물리 서버에 있다 [docs:TODO.md:16]
- 옛 PVC 다섯이 남아 있다. 모두 Retain이라 PVC를 지워도 PV와 데이터가 남으니 PV도 따로 정리한다 [docs:TODO.md:7] [docs:history/build_log/05_harbor.md:481]
- `harborAdminPassword`는 릴리스 값에만 있다 [docs:history/build_log/05_harbor.md:485]
- `values.yaml`의 registry `size`(30Gi)는 배포된 릴리스 값(20Gi)과 다르다. existingClaim이라 렌더 결과는 같다 [docs:history/build_log/05_harbor.md:163] [code:platform/harbor/values.yaml:32-35]
- 네임스페이스 `harbor`는 차트가 만든다고 `app.yaml`에 적혀 있지만, 다시 세우는 순서에서는 Certificate와 PVC를 먼저 넣기 위해 사람이 먼저 만든다 [code:apps/harbor-backup/app.yaml:4] [docs:history/build_log/05_harbor.md:139]

# 08. 구조 확장·이관

가용성 작업 기록이다. 워커를 4대 · 8GB로 늘리고, 앱을 둘로 나누고, 노드마다 역할(app w1 · w2 / infra w3 / platform w4)을 고정해 "노드 하나가 죽으면 무엇이 멈추나"에 노드 이름으로 답할 수 있게 했다. Harbor · ArgoCD는 w3로 옮겼고, MySQL은 Replica(w2)와 수동 승격 런북을 두었다.

- 날짜: 2026-11-10 하루에 두 묶음(묶음 1 낮, 묶음 2 저녁), 2026-11-11 이후 바뀐 것은 3절 끝, 2026-11-12 코드 · 클러스터와 맞춤
- 범위: 노드 역할과 배치, 앱 분산(anti-affinity · PDB · 롤링), 데이터(Replica · 백업), 노드 정비 절차, Harbor · ArgoCD 이사. VM 만들기 · 메모리 바꾸기 절차는 [01_cluster.md](01_cluster.md), 모니터링 설치는 [09_monitoring.md](09_monitoring.md), MySQL 승격 절차는 [runbooks/mysql-replica.md](runbooks/mysql-replica.md)
- 코드: cluster/label-nodes.sh, platform/harbor/pvc-w3.yaml, platform/harbor/values.yaml, platform/argocd/pin-infra.sh, platform/jenkins/values.yaml, platform/ingress-nginx/overlay/, apps/petmint/, apps/runshoes/, apps/harbor-backup/, scripts/mysql-replica-seed.sh, scripts/mysql-replica-check.sh
- 이 파일은 옛 `docs/02_availability.md`이고, 노션 「08. 구조 확장·이관」의 원본이었다. 2026-11-12 노션에만 있던 사전 정리 · 설계 결정 · 12-1~12-8단계 · 트러블슈팅을 합쳤다

## 1. 지금 구성

### 1-1. 배치

사용자 2026-11-10 목표이고 묶음 2로 맞췄다. 2026-11-12 클러스터 조회와 같다.

```
m-k8s   컨트롤 플레인만(control-plane taint)                          4096
w1      app       MySQL Primary ×2 + petmint ×1 + runshoes ×1         8192
w2      app       MySQL Replica ×2 + petmint ×1 + runshoes ×1         8192
w3      infra     Harbor + Jenkins + ArgoCD                           8192
w4      platform  Prometheus · Grafana · Loki                         8192
```

노드 라벨 `node.ronanlab.dev/role`(`cluster/label-nodes.sh`, 노드를 다시 만들면 다시 돌린다). 매니페스트는 이 라벨을 nodeSelector로 본다.

| 죽는 노드 | 멈추는 것 | 도는 것 |
| --- | --- | --- |
| w1 | MySQL Primary 둘 → 사람이 Replica 승격([runbooks/mysql-replica.md](runbooks/mysql-replica.md)) | 앱은 w2의 Pod가 받는다(DB 쓰기는 승격 전까지 실패) |
| w2 | Replica(복제만 멈춤) | 앱은 w1의 Pod가 받는다 |
| w3 | 배포 · 빌드(Harbor · Jenkins · ArgoCD) | 서비스 전부. 떠 있는 Pod는 이미지가 노드에 있다 |
| w4 | 모니터링 · 로그 | 서비스 · 배포 전부 |

정해 두지 않은 것: ingress-nginx(2개, 분산 선호) · cloudflared(2개) · CoreDNS · cert-manager · MetalLB 컨트롤러 · local-path-provisioner는 아무 워커에나 뜬다(2026-11-12 조회: ingress-nginx w1 · w4, cloudflared w1 · w2).
Jenkins 빌드 Pod(BuildKit)는 앱 저장소 Jenkinsfile이 정해 아무 워커에나 뜬다(4절).

### 1-2. 노드에 묶인 것(local-path PVC)

묶음 2 뒤. 2026-11-12 `kubectl get pv`의 노드와 같다.

| 노드 | 묶인 것 |
| --- | --- |
| w1 | petmint `mysql-0` · `runshoes-mysql-0`(Primary) |
| w2 | `mysql-replica-0` · `runshoes-mysql-replica-0` |
| w3 | Harbor 다섯(`harbor-*-w3`, `platform/harbor/pvc-w3.yaml`) · `jenkins-0` |
| w4 | `prometheus-0` · `loki-0` |

**옛 Harbor PVC 다섯은 지우지 않고 남겨 두었다**(원본 보존, 사용자). 2026-11-12에도 다섯 모두 Bound로 남아 있다.

| 옛 PVC | 크기 | 노드 |
| --- | --- | --- |
| `harbor-registry` | 20Gi(쓴 것 약 16GB) | w2 |
| `data-harbor-trivy-0` | 5Gi | w2 |
| `data-harbor-redis-0` | 1Gi | w1 |
| `harbor-jobservice` | 1Gi | w1 |
| `database-data-harbor-database-0` | 5Gi | w3 |

Harbor PV는 옛것 · 새것 모두 reclaimPolicy Retain이다. 새 쪽이 며칠 정상으로 돈 뒤 사람이 지운다(TODO).

### 1-3. 앱 분산: anti-affinity · PDB · 롤링

| 앱 | replicas | 분산 | PDB | 롤링 |
| --- | --- | --- | --- | --- |
| petmint | 2 | app 노드(w1 · w2) + required anti-affinity | minAvailable 1 | maxSurge 0 · maxUnavailable 1 (자동 Sync, 2026-11-11~) |
| runshoes | 2 | 같음 | minAvailable 1 | 같음 (자동 Sync) |

- app 노드가 둘뿐이라 새 Pod를 먼저 띄우는 롤링(2+1)은 세 번째 Pod가 갈 곳이 없다. 그래서 **옛 Pod 하나를 먼저 내리고 새 Pod**를 띄운다. 롤링 동안 잠깐 Pod가 하나다(처리 용량 절반, 서비스는 이어진다. 2026-11-10 1초 탐침 실패 0)
- app 노드 하나가 죽으면 두 번째 Pod는 그 노드가 돌아올 때까지 Pending이고, 그동안 롤링은 멈춘다(남은 하나가 받는다)
- runshoes는 replicas 2와 함께 `ActivityCleanup`을 꺼 두었다(env `ACTIVITY_CLEANUP_CRON: "-"`, ShedLock 전까지)

### 1-4. 데이터: Replica · 백업

| 대상 | 무엇 | 어디로 |
| --- | --- | --- |
| petmint · runshoes MySQL | Replica(w2), binlog 파일 · 위치 복제, 자동 전환 없음. [runbooks/mysql-replica.md](runbooks/mysql-replica.md) | Replica 디스크(w2) |
| petmint MySQL | CronJob 03:30 KST mysqldump(`apps/petmint/backup/`) | 호스트 `~/backup/mysql/petmint`(NFS) |
| Harbor DB | CronJob 03:45 KST `pg_dump -Fc`(`apps/harbor-backup/`) | 호스트 `~/backup/harbor`(NFS) |
| runshoes MySQL | 정기 덤프 없음. 스키마 배포 전 수동 덤프(`apps/runshoes/runbooks/`). Replica가 생겼다 | 없음 |

Replica는 백업이 아니다. Primary에서 지운 것은 Replica에서도 지워진다. 덤프는 그대로 필요하다.

### 1-5. 노드 정비 절차 (한 노드씩)

```bash
free -g                                              # 호스트 여유
kubectl cordon <노드>
# 1. 그 노드의 단일 replica 무상태 Deployment 를 먼저 옮긴다(rollout restart: 새 Pod 가 Ready 된 뒤 옛 Pod 를 내린다)
#    배치를 고정한 것은 같은 역할의 다른 노드가 없으면 옮겨지지 않는다(infra · platform 은 노드가 하나). 그 노드 정비 동안 멈춘다
# 2. 앱 노드(w1 · w2)면 앱 Pod 를 먼저. 남은 app 노드에 하나가 이미 있어 새 Pod 는 Pending(남은 하나가 받는다)
kubectl drain <노드> --ignore-daemonsets --delete-emptydir-data --pod-selector='app.kubernetes.io/name in (petmint-app,runshoes)'
# 3. Jenkins 빌드 · 태그 커밋 롤아웃이 돌고 있으면 끝날 때까지 기다린다(w3 정비 때 특히)
# 4. 나머지 drain(PVC 에 묶인 Pod 는 돌아올 때까지 Pending) → halt → (메모리 변경, 01_cluster.md 「워커 메모리 늘리기」) → up
kubectl drain <노드> --ignore-daemonsets --delete-emptydir-data
cd ~/k8s-cluster && vagrant halt <노드> && vagrant up <노드>
# 5. NotReady 를 거쳐 다시 Ready 인 것을 보고 uncordon(꺼진 직후에는 Ready 가 아직 남아 있다)
kubectl wait --for=condition=Ready node/<노드> && kubectl uncordon <노드>
```

| 정비하는 노드 | 그동안 멈추는 것 |
| --- | --- |
| w1 | MySQL Primary 둘(쓰기 · runshoes Ready). 짧으면 기다리고, 길면 런북 3절로 승격 |
| w2 | Replica(돌아오면 따라잡는다), 앱 용량 절반 |
| w3 | Harbor · Jenkins · ArgoCD(배포 · 빌드) |
| w4 | 모니터링 · 로그(그동안의 지표 · 로그는 빈다) |

- 펫퍼민트 Sync는 정비 중에는 하지 않는다(사용자)
- drain은 끝난 Job의 Pod(Completed)도 지운다. 그 Pod 로그는 사라진다(Loki에는 남는다)

### 1-6. 모니터링 (w4)

설치 기록은 [09_monitoring.md](09_monitoring.md), 지금 구성은 `apps/monitoring/README.md`. Prometheus 15일 · Loki 7일(서버 로그만, 대화 기록 없음) · Grafana 대시보드 「petmint 운영」(`apps/monitoring/grafana/dashboards/petmint.json`).
앱에 `/metrics`가 없어 HTTP 지표는 ingress-nginx에서, 질문 · 답 지표는 petmint 턴 로그(Replica, 컬럼 단위 읽기 계정)에서 얻는다.

## 2. 왜 이렇게 했나

### 2-1. 사전 정리: 무엇이 문제였나

11단계까지 끝낸 클러스터는 "노드가 넷"이었지만, 노드 하나가 죽으면 무엇이 멈추는지 말할 수 없었다. local-path PVC는 처음 뜬 노드에 생기므로([02_metrics_storage_ingress.md](02_metrics_storage_ingress.md)의 local-path 단계) 상태를 가진 것들이 제각각 흩어져 있었다.

| 노드 | 묶여 있던 것 | 그 노드가 죽으면 |
| --- | --- | --- |
| w1 | MySQL 둘 · harbor-redis · jobservice | 두 앱의 DB, Harbor 로그인·push |
| w2 | harbor-registry(20Gi) · trivy | 이미지 pull·push |
| w3 | harbor-database · Jenkins | Harbor 전체, 빌드 |

어느 워커를 내려도 Harbor 일부가 멈췄다. 앱도 runshoes는 replicas 1이라 그 노드가 내려가면 끊겼다.

### 2-2. 설계 결정: 역할별 노드

목표는 "노드 하나가 죽어도 뭔가는 돈다"이고, **노드가 죽었을 때 무엇이 멈추는지를 노드 이름으로 말할 수 있게** 하는 것이다. 배치와 죽는 노드별 표는 1-1절.
노드에는 역할 라벨을 붙이고(`node.ronanlab.dev/role`), 매니페스트는 이 라벨을 nodeSelector로 본다. 라벨은 git에 스크립트(`cluster/label-nodes.sh`)로 남겼다. 노드를 다시 만들면 라벨이 없다.

### 2-3. 설계 결정: MySQL은 자동 전환 없이 수동 승격

| 방식 | 문제 |
| --- | --- |
| Operator(Group Replication·Orchestrator 등) | 자동 전환이 되지만 컴포넌트가 늘고 메모리를 더 먹는다. VM 넷에 Harbor·Jenkins·모니터링까지 올린 상태다 |
| Replica + 수동 승격 (채택) | 사람이 알아채고 승격해야 한다. 대신 구성이 단순하고 무엇을 하는지 전부 보인다 |

Primary는 다시 시작하지 않는다는 조건을 두었다. GTID를 켜려면 Primary 재시작이 필요해, 이미 켜져 있던 binlog(ROW)로 **파일·위치 복제**를 했다.

### 2-4. 그 밖의 결정

- **증설 전에 앱부터 둘로**(묶음 1): 노드를 하나씩 내리는데 replicas 1이면 그 노드를 내릴 때 서비스가 끊긴다
- **역할별 노드**(묶음 2): 전에는 local-path PVC가 노드 여기저기에 생겨 어느 워커를 내려도 Harbor 일부가 멈췄다(2-1절)
- **Harbor 이사는 새 PVC + 복사**: local-path는 PVC를 다른 노드로 옮길 수 없다. 원본을 지우지 않는다는 조건이라 새 이름의 PVC를 w3에 만들고 tar로 복사한 뒤 `existingClaim`으로 바꿨다
- **Grafana가 DB를 직접 읽는다**: 앱 코드를 고치지 않고 질문 · 답 지표를 얻는 길. Replica를 읽어 운영에 부하를 주지 않고, 컬럼 단위 권한으로 본문을 읽을 수 없게 했다([09_monitoring.md](09_monitoring.md))
- **ingress-nginx 2개**: 메트릭을 켜려면 재시작이 필요했고, 1개일 때 재시작이 12초 끊김을 냈다(묶음 1). 먼저 늘린 뒤 바꿨다

## 3. 진행 기록

### 3-1. 2026-11-10 묶음 1(낮)

#### 12-1단계: 앱 이중화 (runshoes replicas 2)

노드를 하나씩 내리며 증설하려면, 그 노드에 있던 앱이 끊기지 않아야 한다. petmint는 이미 replicas 2 + required anti-affinity + PDB였다([07_project_deploy.md](07_project_deploy.md)). runshoes를 같게 맞췄다.

```yaml
spec:
  replicas: 2
  template:
    spec:
      affinity:
        podAntiAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            - topologyKey: kubernetes.io/hostname
              labelSelector:
                matchLabels:
                  app.kubernetes.io/name: runshoes
```

**Pod가 둘이 되면 같이 도는 것을 먼저 봐야 한다.** runshoes의 `@Scheduled` 정리 작업(activity_logs 삭제)이 Pod마다 돈다. 두 Pod가 같은 시각 같은 행을 지운다. 분산 잠금(ShedLock)은 앱 일이라, 같은 커밋에서 env로 껐다.

```yaml
- name: ACTIVITY_CLEANUP_CRON
  value: "-"          # Spring 의 끄기 값. ShedLock 이 들어오면 이 줄을 뺀다
```

꺼졌는지는 로그가 아니라 **스레드**로 확인했다. 이 앱의 `@Scheduled`는 이것 하나라, 등록되면 `scheduling-1` 스레드가 생긴다.

```bash
kubectl -n runshoes exec $p -c runshoes -- sh -c 'cat /proc/1/task/*/comm | grep -ci "^scheduling"'
```

```txt
0
```

#### 12-2단계: Harbor DB 백업

Harbor의 프로젝트·로봇 계정·태그는 PostgreSQL `registry` 데이터베이스에 있다. petmint MySQL 백업과 같은 방식(CronJob → 호스트 NFS)으로 매일 `pg_dump -Fc`를 뜨고, **운영 DB를 덮지 않는 시험 Pod**에 복구해 49개 테이블 행 수가 운영과 같은 것을 확인했다([05_harbor.md](05_harbor.md)).

#### 12-3단계: 워커 추가(w4)와 메모리 증설(w1~w3)

절차는 [01_cluster.md](01_cluster.md)(워커 추가 · 메모리 증설)에 있다. 여기서는 순서와 그동안의 서비스만 남긴다.

```txt
w4 생성 → w2 → w3 → w1   (한 노드씩: cordon → 앱 Pod 먼저 drain → 나머지 drain → halt → 메모리 → up → uncordon)
```

**앱 Pod를 먼저 내보낸 이유**: 어느 노드를 내려도 Harbor 일부가 멈췄다. 앱 Pod가 옮겨갈 노드에서 이미지를 받으려면 Harbor가 살아 있어야 하므로, 같은 drain에서 함께 내보내지 않고 앱 Pod만 먼저 옮겼다.
첫 정비 순서는 그냥 `kubectl drain`이었는데, 앱 Pod가 옮겨가며 Harbor에서 이미지를 받아야 하는 때에 같은 drain이 Harbor를 멈추면 새 Pod가 ImagePullBackOff가 될 수 있어 이 순서로 바꿨다.

```bash
kubectl drain w3-k8s --ignore-daemonsets --delete-emptydir-data \
  --pod-selector='app.kubernetes.io/name in (petmint-app,runshoes)'
```

묶음 1 실행 기록:

| 단계 | 커밋 · 변경 | 확인 |
| --- | --- | --- |
| 1 runshoes replicas 2 | `fdc9600` deployment(replicas 2 · anti-affinity · env) · `pdb.yaml` | Pod w1 · w3, PDB ALLOWED 1, 두 Pod env `-`, `@Scheduled` 스레드(`scheduling-*`) 0개, 응답 200×6, ArgoCD Synced/Healthy |
| 2 petmint 확인 | 변경 없음(Sync 안 함) | 매니페스트 · 클러스터 모두 replicas 2 · required anti-affinity · PDB minAvailable 1 |
| 3 Harbor DB 백업 | `adbe654` · `e2c9b36`, 호스트 export(sudo) | 첫 덤프 500,480B · 테이블 데이터 49 · sha256 OK, 시험 DB 복구 49개 테이블 행 수 같음 |
| 4 w4 | Vagrantfile(+ DNS 프로비저너), setup-node.sh(버전 고정), kubeadm join | Ready, w4 고정 시험 Pod에서 Harbor pull · DNS · MySQL TCP · Service 200 · Ollama 200 · NFS |
| 5 w1~w3 8GB | Vagrantfile, virsh 메모리, w2 → w3 → w1 | 노드마다 Ready · 용량 8128536Ki · 묶인 Pod 복귀 · 응답(아래) |

호스트 메모리(available): 시작 35GB → w4 뒤 33GB → w2 뒤 32GB → w3 뒤 29GB → w1 뒤 25GB.

정비 중 응답. 호스트에서 1초마다 다섯 주소(VIP)를 찔러 실패 건수를 셌다.

| 구간 | petmint `/` | runshoes `/api/shoes` | Harbor ping | ArgoCD | Jenkins |
| --- | --- | --- | --- | --- | --- |
| w2 (19:07~19:20) | 실패 0 | 0 | 1 (core 재시작 순간) | 0 | 0 |
| w3 (19:20~19:26) | 0 | 0 | 0 | 1 | 235 (약 5분, PVC가 w3, 예정) |
| w1 (19:26~19:37) | 11 (19:27:20~31) | 90 | 92 | 11 | 11 |

w1의 runshoes 78건 · Harbor 81건은 MySQL · redis가 내려간 19:35:15~19:36:59(약 1분 40초, 예정된 중단, 사용자가 받아들임), 나머지(runshoes 12 · 그 밖 11건씩)는 ingress-nginx를 옮기며 생긴 12초 전체 끊김이다(아래 트러블슈팅).
petmint `/`는 정적 응답이라 MySQL이 멈춘 동안에도 200이었다(DB를 쓰는 API는 실패).

#### 트러블슈팅: 꺼진 직후의 Ready

**증상**: w2를 halt한 직후 `kubectl wait --for=condition=Ready`가 바로 통과했다.

**원인**: 노드가 꺼진 것을 kubelet 하트비트가 끊긴 뒤에야 알기 때문에, **꺼진 직후에는 Ready가 아직 남아 있다.**

**해결**: NotReady를 거쳐 다시 Ready가 된 것을 보고 uncordon한다(1-5절 5번). 이때는 NotReady 노드에 자동으로 붙는 taint 덕분에 실해는 없었다.

#### 트러블슈팅: 메모리를 올렸는데 게스트는 4GB

**증상**: Vagrantfile의 memory를 8192로 올리고 켰는데 게스트가 4GB만 봤다.

**원인**: vagrant-libvirt가 `<currentMemory>`를 그대로 두었다.

**해결**: w3 · w1은 켜기 전에 virsh로 맞춰 한 번에 됐다. 자세한 것은 [01_cluster.md](01_cluster.md)의 「메모리를 올렸는데 게스트가 4GB만 본다」 트러블슈팅.

#### 트러블슈팅: ingress-nginx 재시작 때 12초

**증상**: w1을 비우기 전, ingress-nginx(replicas 1)를 다른 노드로 옮기려 `rollout restart`를 했더니 12초 동안 다섯 주소가 모두 응답하지 않았다.

**원인**: 확인하지 못했다. Service는 `externalTrafficPolicy: Cluster`라 VIP가 컨트롤러 노드에 묶이지 않는다.

**해결**: 묶음 2에서 replicas 2로 늘렸고(12-8단계), 그 뒤 롤링에서는 1초 한 번이었다. 원인은 4절에 남은 한계로 둔다.

### 3-2. 2026-11-10 묶음 2(저녁)

#### 12-4단계: Harbor 이사 (w1·w2·w3 → w3)

local-path PVC는 다른 노드로 옮길 수 없다. 그리고 **원본은 지우지 않는다**는 조건이 있었다. 그래서 새 이름의 PVC 다섯을 w3에 만들고, 데이터를 복사한 뒤 Helm의 `existingClaim`으로 바꿨다.

```txt
1. w3 루트 디스크 62G → 92G (lvextend, 볼륨 그룹에 63G 남아 있었다. 01_cluster.md 「디스크 크기 정리」)
2. 새 PVC 다섯(harbor-*-w3) + w3 에 고정한 임시 Pod → local-path 가 w3 에 디렉터리를 만든다
3. 이사 직전 DB 백업, Jenkins 빌드가 없는지 확인
4. Harbor 정지 → 노드 간 tar 복사 → 목록 비교
5. StatefulSet 셋은 --cascade=orphan 으로 객체만 지우고 helm upgrade
```

복사는 호스트에서 두 VM을 ssh로 이었다. 노드끼리 직접 잇지 않아도 되고, tar가 소유자·권한을 그대로 옮긴다.

```bash
ssh -F ssh.cfg w2-k8s "sudo tar -C $P/<원본> -cf - ." | ssh -F ssh.cfg w3-k8s "sudo tar -C $P/<새것> -xpf - --numeric-owner"
```

```txt
database: 파일 1589 / 새 1589 / 2초
redis: 파일 1 / 새 1 / 0초
jobservice: 파일 85 / 새 85 / 1초
trivy: 파일 3 / 새 3 / 8초
registry: 파일 3408 / 새 3408 / 62초
```

`du` 바이트는 jobservice·registry에서 조금 달랐다. 디렉터리 항목 크기까지 세기 때문이다. 그래서 **파일 이름·크기·권한·소유자 목록의 md5**를 원본과 비교했고, 셋 다 같았다.

결과: Harbor 멈춘 시간 약 4분(노드 간 tar 73초, registry 3,408파일 16.9GB), DB 49개 테이블 행 수 이사 전과 같음, w4에서 `imagePullPolicy: Always`로 pull, 시험 이미지 push → 조회 → 삭제(404). 옛 PVC 다섯은 그대로 남겨 두었다(며칠 본 뒤 사람이 지운다). w3 루트 62G → 92G. 커밋 `d5bf708`.

#### 트러블슈팅: existingClaim을 주면 옛 PVC가 지워질 수 있다

**증상**: dry-run으로 바뀌는 리소스를 뽑아 보니 "빠지는 리소스"에 옛 PVC 둘이 있었다.

```txt
-- 빠지는 리소스
PersistentVolumeClaim/harbor-jobservice
PersistentVolumeClaim/harbor-registry
```

**원인**: 차트는 `existingClaim`이 있으면 PVC를 더 그리지 않는다. Helm은 그리지 않게 된 리소스를 지운다. local-path는 reclaimPolicy가 Delete라 **데이터까지 지워진다.**

**해결**: 두 겹으로 막았다. 차트가 그 PVC에 `helm.sh/resource-policy: keep`을 이미 달아 둔 것을 확인했고(Helm이 지우지 않는다), Harbor PV 전부를 Retain으로 바꾼 뒤 올렸다(PVC가 지워져도 데이터가 남는다).

#### 12-5단계: ArgoCD 이사 (→ w3)

ArgoCD는 이미 컨트롤 플레인 밖(w2·w4)에 있었다. m-k8s에는 control-plane taint가 있다. PVC가 없어(redis는 emptyDir) nodeSelector만 바꾸면 됐다. install.yaml로 깔았기 때문에 그 매니페스트는 저장소에 없다. 패치를 스크립트(`platform/argocd/pin-infra.sh`)로 남겼다. install.yaml을 다시 apply하면 이 스크립트도 다시 돌린다.

확인: 7개 모두 w3, Application 5개 Synced/Healthy, 커밋 뒤 웹훅으로 12초 만에 새 커밋을 봤다. 커밋 `61dbc5c`.

#### 12-6단계: MySQL Replica (w2)

```bash
bash scripts/mysql-replica-seed.sh runshoes runshoes-mysql-0 runshoes-mysql-0.runshoes-mysql runshoes-mysql-replica-0
```

```txt
덤프 시점 binlog: binlog.000004 1015 (2초)
           Replica_IO_Running: Yes
          Replica_SQL_Running: Yes
        Seconds_Behind_Source: 0
끝 6초
```

| 값 | 이유 |
| --- | --- |
| `--server-id=2`(Primary는 기본 1) | 복제는 서버마다 다른 id가 필요하다 |
| read_only를 `SET PERSIST`로 | 명령줄 인자는 PERSIST보다 앞선다. 인자로 걸면 승격 때 풀 수 없다 |
| Primary와 required anti-affinity | 같은 노드에 두면 Replica의 의미가 없다. app 노드 중 Primary가 없는 w2에 뜬다 |
| `mysqldump --single-transaction --source-data=2` | Primary를 잠그지 않고, 덤프 시점의 binlog 위치를 함께 받는다 |
| `mysql` 스키마까지 | 승격했을 때 앱 계정이 Replica에 있어야 한다 |
| 덤프를 디스크에 남기지 않음 | Primary → Replica로 바로 흘린다 |

확인 스크립트(`scripts/mysql-replica-check.sh`)는 앱 데이터베이스의 **테이블별 정확한 행 수**와 계정 목록을 비교하고, Primary에 시험 데이터베이스를 만들었다 지워 그 둘이 Replica로 넘어오는지 본다.

```txt
같음: 테이블 11개 행 수 · 계정 7개
쓰기 전달: 만들기 · 지우기 둘 다 Replica 에 넘어감
```

두 Replica 모두 w2, 테이블 행 수 · 계정 Primary와 같음, 쓰기 전달 확인. 커밋 `72d0716` · `25d94d0`.

#### 트러블슈팅: binlog 위치가 비어 있다

**증상**: 처음 스크립트는 덤프를 Replica로 흘리면서 `tee >(grep -m1 …)`로 머리의 위치 줄만 뽑았다. 위치가 비었다.

**원인**: 둘이었다.

1. `grep -m1`은 첫 줄을 찾으면 끝난다. 그 뒤 `tee`가 닫힌 파이프에 쓰다 SIGPIPE로 죽는다
2. MySQL 8.0.46 mysqldump는 `--source-data` 옵션을 써도 옛 문법으로 적는다

```txt
-- CHANGE MASTER TO MASTER_LOG_FILE='binlog.000004', MASTER_LOG_POS=1015;
```

**해결**: 한 프로세스(awk)가 흘려보내면서 위치 줄만 따로 적게 바꾸고, 두 문법을 다 받게 고쳤다. Replica는 다시 넣으면 덮이므로 그대로 다시 돌렸다.

#### 12-7단계: 승격 시험

운영 Primary와 앱은 건드리지 않고, runshoes Replica를 **실제로 승격**했다. 앱이 붙는 Service와 같은 모양의 시험 Service를 두고 selector를 바꿔, 그 이름으로 새 쪽에 붙는 시간까지 쟀다.

```sql
STOP REPLICA; RESET REPLICA ALL;
SET PERSIST super_read_only=OFF; SET PERSIST read_only=OFF;
```

| 단계 | 걸린 시간 |
| --- | --- |
| 따라잡음 확인 + 승격(SQL) | 0.2초 |
| Service selector 전환 → 새 쪽(server_id 2)에 붙음 | 0.1초 |
| 새 Primary에 쓰기 확인까지 합계 | 0.5초 |
| 앱 재시작(rollout restart) | runshoes 82초 · petmint 23초 |
| 시험 뒤 Replica 다시 만들기 + 확인 | 10초 |

> **기계가 하는 일은 약 2분이다.** 승격에 걸리는 시간은 사람이 정한다. 장애를 알아채고, w1이 돌아오지 않는다고 판단하고, git에 selector를 반영하는 시간이다. 앱 트래픽까지 옮기는 진짜 전환은 운영 쓰기를 멈춰야 하고 되돌리는 데 전환이 한 번 더 들어서 이번에는 하지 않았다.

#### 12-8단계: 배치 고정

| 대상 | 어디 | 방법 |
| --- | --- | --- |
| petmint · runshoes 앱 | app(w1·w2) | Deployment nodeSelector |
| MySQL Primary | w1 | PV가 이미 w1에 묶여 있다. StatefulSet을 고치면 Primary가 재시작되므로 손대지 않았다 |
| Harbor · ArgoCD · Jenkins | infra(w3) | Helm values · 패치 스크립트 · Helm `--reuse-values --set` |
| 모니터링 | platform(w4) | [09_monitoring.md](09_monitoring.md) |

**app 노드가 둘이 되면서 롤링을 바꿔야 했다.** required anti-affinity로 같은 노드에 둘을 두지 않는데, 새 Pod를 먼저 띄우는 롤링(maxSurge 1)은 세 번째 Pod가 갈 노드가 없어 영영 멈춘다.

|  | 전 | 지금 |
| --- | --- | --- |
| `maxSurge` / `maxUnavailable` | 1 / 0 | 0 / 1 |
| 롤링 동안 | Pod 셋(2+1) | Pod 하나 → 둘 |
| 필요한 노드 | 스케줄 가능한 워커 3대 | app 노드 2대 |

롤링 동안 잠깐 처리 용량이 반이 되지만 서비스는 이어진다. 배치를 옮기는 롤링과 시험 재시작 동안 1초 탐침 실패 0. 앱 w1 · w2(롤링 실패 0), Jenkins w3(재기동 66초), 앱 재시작 runshoes 82초 · petmint 23초. 커밋 `684774a`.

**ingress-nginx는 replicas 2로 늘렸다**(모니터링에 쓸 메트릭을 켜려면 재시작이 필요했다. [09_monitoring.md](09_monitoring.md)). 먼저 2개로 늘린 뒤 인자를 바꿔 한 개씩 롤링했고, 1초 탐침에서 21:13:29 한 번(1초) 다섯 주소 모두 응답이 없었다. 12초보다 짧지만 0은 아니다.

#### 최종 확인

```bash
kubectl get pods -A -o wide | grep -E "petmint-app|runshoes-|mysql|harbor-|argocd-|jenkins-0|prometheus|loki"
```

```txt
w1   mysql-0 · runshoes-mysql-0 · petmint-app · runshoes
w2   mysql-replica-0 · runshoes-mysql-replica-0 · petmint-app · runshoes
w3   harbor-(core·portal·registry·jobservice·database·redis·trivy) · argocd-(7개) · jenkins-0
w4   prometheus-0 · loki-0 · grafana · kube-state-metrics · json-exporter
```

> **"노드 하나가 죽으면 무엇이 멈추나"에 노드 이름으로 답할 수 있게 됐다.** w3이면 배포가, w4면 모니터링이, w1이면 DB 쓰기가 승격 전까지 멈추고, 상담과 러닝화 검색은 어느 노드 하나가 빠져도 돈다.

묶음 2 실행 기록:

| 단계 | 커밋 | 확인 |
| --- | --- | --- |
| 1 Harbor → w3 | `d5bf708` | 이사 직전 DB 백업, Jenkins 빌드 없음 확인 → Harbor 정지 → 노드 간 tar 73초(registry 3,408파일 16.9GB) → 파일 이름 · 크기 · 권한 · 소유자 목록 md5 원본과 같음 → helm upgrade. Harbor 멈춘 시간 약 4분. DB 49개 테이블 행 수 이사 전과 같음, w4에서 `imagePullPolicy: Always` pull, 시험 push → 조회 → 삭제(404). 옛 PVC 다섯 그대로, w3 루트 62G → 92G |
| 2 ArgoCD → w3 | `61dbc5c` | PVC 없음. 7개 모두 w3, Application 5개 Synced/Healthy, 커밋 뒤 웹훅으로 12초 만에 새 커밋을 봄 |
| 3 MySQL Replica | `72d0716` · `25d94d0` | 두 Replica w2, 테이블 행 수 · 계정 Primary와 같음, 쓰기 전달 확인. 승격 시험(runshoes): SQL 0.2초 · Service 전환 0.1초 · 다시 만들기 10초 |
| 4 배치 고정 | `684774a` | 앱 w1 · w2(롤링 실패 0), Jenkins w3(재기동 66초). 앱 재시작 runshoes 82초 · petmint 23초 |
| 5 모니터링 | `b15b7ff`(ingress) · `eb13e8f` | 전부 w4, 수집 대상 up(그때 milvus · nvidia-gpu 제외, 3-3절), Loki 12개 네임스페이스 · 챗봇 질문 줄 0건, Grafana 데이터소스 셋 OK, 읽기 계정이 질문 · 코멘트 컬럼에서 ERROR 1143 |

Harbor · ArgoCD · Jenkins를 옮기는 동안 앱 응답은 끊기지 않았다(앱 Pod는 이미지를 노드에 갖고 있다). 배치 고정 롤링 · 앱 재시작 동안 1초 탐침 실패 0,
ingress-nginx를 2개로 늘린 뒤 메트릭을 켜는 롤링에서 1초 한 번 다섯 호스트 모두 응답 없음.

### 3-3. 그 뒤 바뀐 것 (2026-11-11)

- petmint · monitoring 자동 Sync(runshoes는 전부터 자동). 롤링 규칙(1-3절)은 그대로
- Milvus 지표: 호스트 compose에서 9091을 사설망(192.168.122.1)에도 게시해 Prometheus 대상 milvus가 up이 됐다(디버그 경로도 함께 열림, 앱 리포 `~/AI_programming/petmint-rag-chatbot/docs/02_pipeline/15_monitoring.md` 4절)
- 거절률 · 검색 지연: petmint 턴 로그에 칸(refused · search_ms, 앱 0009)이 생겨 대시보드에 붙였다
- Grafana · Prometheus 바깥 주소: `grafana.ronanlab.dev` · `prometheus.ronanlab.dev` Ingress · 인증서 · 터널 호스트(`apps/monitoring/ingress.yaml`, `apps/cloudflared/configmap.yaml`). Cloudflare Access · DNS는 사람이 대시보드에서 한다
- GPU exporter: 호스트 컨테이너 `nvidia-gpu-exporter`(`scripts/host-gpu-exporter.sh`, 192.168.122.1:9835)를 띄웠다. 2026-11-12 09:18 호스트 조회에서 Up 24 hours, Prometheus 대상 nvidia-gpu up 1

## 4. 남은 한계

- **MySQL 자동 장애 전환이 없다.** Replica는 있지만 승격은 사람이 한다. Operator는 자원 제약으로 쓰지 않았다(2-3절). 기계 쪽 시간은 약 2분(승격 1초 안 + 앱 재시작 1~1.5분, 런북 시험 기록), 나머지는 알아채고 판단하는 시간이다. 앱 트래픽까지 옮기는 진짜 전환은 아직 해 보지 않았다
- **app 노드가 둘이다.** 롤링 때 잠깐 Pod 하나, app 노드 하나가 죽으면 Pod 하나로 버틴다
- **infra · platform 노드는 하나씩이다.** w3이 죽으면 배포 · 빌드가, w4가 죽으면 모니터링이 그 노드가 돌아올 때까지 멈춘다(목표대로)
- **백업이 운영 DB와 같은 물리 디스크에 있다.** 호스트 NFS(`~/backup/`)와 VM 디스크가 같은 서버 · 같은 NVMe다
- **VM이 모두 같은 물리 서버에 있다.** 서버 자체가 죽으면 전부 멈춘다. 노드 분산은 VM · kubelet 장애만 막는다
- **런슈즈 activity_logs 정리가 꺼져 있다(2026-11-10부터).** ShedLock 전까지 activity_logs가 쌓인다
- **Harbor 이미지 레이어는 백업하지 않는다.** DB만 있다. 레이어가 사라지면 앱 리포 커밋에서 다시 빌드한다
- **옛 Harbor PVC 다섯이 디스크를 쓰고 있다**(registry 16GB w2 등, 1-2절). 지울 때까지
- **Jenkins 빌드 Pod는 배치가 고정되지 않았다.** Jenkinsfile(앱 저장소)의 Pod 템플릿에 nodeSelector를 넣어야 한다. 빌드(상한 3Gi)가 app 노드에 뜨면 앱과 메모리를 나눈다(2026-11-12 runshoes · petmint-rag-chatbot Jenkinsfile에 nodeSelector 없음)
- **ingress-nginx 재시작 때 짧은 끊김.** 1개일 때 12초(묶음 1, 원인 미확인), 2개로 늘린 뒤 롤링에서 1초 한 번(2026-11-10 21:13:29). 0은 아니다
- **모니터링**: 알림(Alertmanager) 없음 · Prometheus · Loki 한 대씩 · Grafana · Prometheus 바깥 주소는 클러스터 쪽(Ingress · 인증서 · 터널)까지 했고, Access · DNS는 사람이 대시보드에서 한다(Prometheus는 자체 로그인이 없어 Access가 먼저). Milvus 9091은 디버그 경로(`/debug/pprof` · `/log/level`)도 인증 없이 사설망에 열려 있다(`~/AI_programming/petmint-rag-chatbot/docs/02_pipeline/15_monitoring.md` 4절). GPU exporter는 2026-11-11 띄워 끝났다(3-3절)

## 5. 확인 방법

m-k8s에서(`cd ~/k8s-cluster && vagrant ssh m-k8s -c '…'`):

```bash
kubectl get nodes -L node.ronanlab.dev/role
# 기대: m-k8s(역할 없음) · w1 app · w2 app · w3 infra · w4 platform, 모두 Ready

kubectl get pods -A -o wide | grep -E "petmint-app|runshoes-|mysql|harbor-|argocd-|jenkins-0|prometheus|loki"
# 기대: 3-2절 「최종 확인」과 같은 노드

kubectl get pv -o custom-columns=NAME:.metadata.name,CLAIM:.spec.claimRef.name,RECLAIM:.spec.persistentVolumeReclaimPolicy,NODE:.spec.nodeAffinity.required.nodeSelectorTerms[0].matchExpressions[0].values[0]
# 기대: 1-2절 표의 노드. Harbor PV 는 모두 Retain. 옛 Harbor PVC 다섯은 지울 때까지 남아 있다

kubectl get pdb -A
# 기대: petmint-app · runshoes minAvailable 1, ALLOWED DISRUPTIONS 1

kubectl get deploy -n petmint petmint-app -o jsonpath='{.spec.replicas} {.spec.strategy.rollingUpdate}{"\n"}'
kubectl get deploy -n runshoes runshoes -o jsonpath='{.spec.replicas} {.spec.strategy.rollingUpdate}{"\n"}'
# 기대: 2 {"maxSurge":0,"maxUnavailable":1}

kubectl get cronjob -A
# 기대: harbor-db-backup 45 3 * * * · mysql-backup(petmint) 30 3 * * *, TIMEZONE Asia/Seoul
```

Replica 복제 상태는 `bash scripts/mysql-replica-check.sh`(사용법은 [runbooks/mysql-replica.md](runbooks/mysql-replica.md)). 기대: `Replica_IO_Running: Yes` · `Replica_SQL_Running: Yes` · 행 수 · 계정 같음.

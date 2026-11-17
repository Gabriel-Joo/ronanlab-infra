<!--
다루는 곳: apps/petmint/data/nfs.yaml
읽은 커밋: 6290346
-->
# 공유 저장소

클러스터의 저장 공간 두 갈래, 기본 StorageClass local-path와 호스트 NFS 정적 PV를 다룬다. NFS 쓰기 PV(백업)는 `docs/10_database.md`와 `docs/07_registry.md`에서 다룬다. [code:apps/petmint/backup/cronjob.yaml:79-80] [code:apps/harbor-backup/cronjob.yaml:1-2]

## 지금 구성

| | local-path | 호스트 NFS (petmint 약관, 시드) |
| --- | --- | --- |
| 프로비저닝 | 동적, `rancher.io/local-path` | 정적 PV 셋 + PVC 셋 |
| 데이터 자리 | PVC를 처음 쓰는 Pod가 뜬 노드의 디스크 | 호스트 `192.168.122.1:/srv/nfs/petmint/{chunks,graph,fixtures}` |
| 접근 모드 | ReadWriteOnce | ReadOnlyMany |
| reclaimPolicy | Delete (기본) | Retain |
| 크기 강제 | 안 함 | 안 함 |

- local-path-provisioner v0.0.30, 업스트림 매니페스트 URL을 `kubectl apply`하고 기본 StorageClass로 patch했다. 저장소에 매니페스트가 없다. [code:platform/versions.yaml:23-26]
- local-path는 WaitForFirstConsumer라 처음 붙는 Pod의 노드에 PV가 생긴다. [code:platform/harbor/pvc-w3.yaml:4]
- local-path PV는 노드에 묶이고, Pod는 그 노드로만 다시 뜬다. [code:apps/monitoring/prometheus/statefulset.yaml:2]
- local-path 기본 reclaimPolicy는 Delete다. PVC를 지우면 데이터도 지워진다. Harbor의 `*-w3` PV 다섯은 손으로 Retain으로 바꿔 두었다. [code:platform/harbor/pvc-w3.yaml:6] [code:apps/runshoes/mysql/statefulset.yaml:8]
- local-path는 크기를 강제하지 않는다. 상한은 노드 디스크다. [code:apps/monitoring/README.md:109]
- NFS PV는 petmint만 쓴다. 호스트의 petmint-rag-chatbot 저장소 디렉터리를 bind로 `/srv/nfs/petmint/` 아래에 걸어 읽기 전용으로 내보낸 것이다. [code:apps/petmint/data/nfs.yaml:1-5] [code:apps/petmint/README.md:72-76]
- 복사본이 없다. Milvus 색인을 만든 그 파일을 앱이 읽는다. [code:apps/petmint/data/nfs.yaml:6]

local-path를 쓰는 곳:

| 무엇 | 자리 | 크기 |
| --- | --- | --- |
| petmint MySQL Primary, Replica | `apps/petmint/mysql/` | 10Gi씩 |
| runshoes MySQL Primary, Replica | `apps/runshoes/mysql/` | 2Gi씩 |
| Prometheus | `apps/monitoring/prometheus/statefulset.yaml` | 10Gi |
| Loki | `apps/monitoring/loki/loki.yaml` | 10Gi |
| Harbor (`existingClaim` `harbor-*-w3`) | `platform/harbor/pvc-w3.yaml` | 파일 참조 |
| Jenkins | `platform/jenkins/values.yaml` | 8Gi |

근거: [code:apps/petmint/mysql/statefulset.yaml:68-71] [code:apps/runshoes/mysql/statefulset.yaml:84-87] [code:apps/monitoring/prometheus/statefulset.yaml:1] [code:apps/monitoring/loki/loki.yaml:95-98] [code:platform/harbor/values.yaml:30-51] [code:platform/jenkins/values.yaml:261-264]

NFS를 붙이는 곳:

| PV / PVC | 붙이는 것 | Pod 안 경로 |
| --- | --- | --- |
| `petmint-chunks` | Deployment `petmint-app` | `/var/lib/petmint/chunks` |
| `petmint-graph` | Deployment `petmint-app` | `/var/lib/petmint/graph` |
| `petmint-fixtures` | Job `petmint-init-db`만 | `/var/lib/petmint/fixtures` |

근거: [code:apps/petmint/app/deployment.yaml:108-124] [code:apps/petmint/jobs/init-db.yaml:59-66]

## 설정 자리

`apps/petmint/data/nfs.yaml`:

- 1-10줄: 머리 주석. 호스트 경로와 저장소 디렉터리의 짝, 읽기 전용 세 겹, Retain과 claimRef. [code:apps/petmint/data/nfs.yaml:1-10]
- 18줄: `capacity: 1Gi`. NFS는 용량을 강제하지 않고 바인딩용 표시다. [code:apps/petmint/data/nfs.yaml:18]
- 19줄: `accessModes: ["ReadOnlyMany"]`. 어느 노드에서든 붙는다. [code:apps/petmint/data/nfs.yaml:19] [code:apps/petmint/data/nfs.yaml:8]
- 20줄: `persistentVolumeReclaimPolicy: Retain`. PV를 지워도 호스트 파일은 그대로다. [code:apps/petmint/data/nfs.yaml:20] [code:apps/petmint/data/nfs.yaml:10]
- 21줄: `storageClassName: ""`. 동적 프로비저닝을 타지 않는 정적 PV다. [code:apps/petmint/data/nfs.yaml:21]
- 22줄: `claimRef: { namespace: petmint, name: petmint-chunks }`. 이 PVC에만 묶인다. [code:apps/petmint/data/nfs.yaml:22]
- 23줄: `mountOptions: ["nfsvers=4.2", "ro"]`. v4만 연다. 호스트는 v3를 꺼 rpcbind와 mountd 포트가 필요 없다. [code:apps/petmint/data/nfs.yaml:23]
- 24줄: `nfs: { server: 192.168.122.1, path: /srv/nfs/petmint/chunks, readOnly: true }`. [code:apps/petmint/data/nfs.yaml:24]
- 26-54줄: `petmint-graph`, `petmint-fixtures` PV. 경로만 다르고 같은 꼴이다. [code:apps/petmint/data/nfs.yaml:26-54]
- 64줄: PVC `storageClassName: ""`. 비우지 않으면 기본 StorageClass local-path가 동적으로 만든다. [code:apps/petmint/data/nfs.yaml:64]
- 65줄: `volumeName: petmint-chunks`. PV와 이름으로 짝을 짓는다. [code:apps/petmint/data/nfs.yaml:65]
- 모든 PV, PVC에 `argocd.argoproj.io/sync-wave: "0"`. MySQL과 같은 첫 물결이라 초기화 Job(1)과 앱(2)보다 먼저 생긴다. [code:apps/petmint/data/nfs.yaml:15-16] [code:apps/petmint/jobs/init-db.yaml:6]

읽기 전용 세 겹: 호스트 export `ro`, PV `readOnly`와 mountOptions `ro`, Pod volumeMount `readOnly`. [code:apps/petmint/data/nfs.yaml:8-9]

호스트 쪽 설정(이 저장소 밖):

- petmint-rag-chatbot 저장소 `deploy/scripts/host-nfs-setup.sh`, sudo. 사람이 돌린다. nfs.yaml 2줄 주석의 `scripts/host-nfs-setup.sh`는 이 저장소에 없고 그 파일을 가리킨다. [code:apps/petmint/data/nfs.yaml:2] [code:apps/petmint/README.md:15] [code:apps/petmint/README.md:49]
- export는 사설망 `192.168.122.0/24`에만, `ro,all_squash`, NFSv4.2. [code:apps/petmint/README.md:70-75]

## 바꾸거나 다시 만들기

m-k8s에서 친다. 호스트에서는 `cd ~/k8s-cluster && vagrant ssh m-k8s`. [code:CLAUDE.md:27]

약관 파일을 바꾼 뒤 앱에 반영한다. 앱은 기동 때 읽는다. [code:apps/petmint/data/nfs.yaml:6-7]

```bash
kubectl -n petmint rollout restart deploy/petmint-app
kubectl -n petmint rollout status  deploy/petmint-app
```

`apps/petmint/data/nfs.yaml`을 고치면 push 뒤 petmint 자동 Sync로 들어간다. [docs:history/cluster_state_20261116.md:58] PV의 `spec.nfs`처럼 바꿀 수 없는 필드를 고치면 Sync가 실패한다. 그때 PV를 지우고 다시 만드는 일은 사람 승인이 필요하다. [code:CLAUDE.md:38]

local-path-provisioner를 다시 깐다. [code:platform/versions.yaml:23-26]

```bash
kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/v0.0.30/deploy/local-path-storage.yaml
kubectl patch storageclass local-path -p '{"metadata":{"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'
```

local-path PVC를 다른 노드로 옮기는 명령은 없다. 새 PVC를 목적 노드에 만들고 데이터를 복사한 뒤 바꿔 단다. [docs:history/build_log/08_scale_out.md:145]

## 확인

```bash
kubectl get storageclass
kubectl get pv petmint-chunks petmint-graph petmint-fixtures
kubectl -n petmint get pvc petmint-chunks petmint-graph petmint-fixtures
kubectl -n petmint exec deploy/petmint-app -c app -- ls /var/lib/petmint/chunks /var/lib/petmint/graph
```

기대 결과:

- `local-path (default)`, PROVISIONER `rancher.io/local-path`, RECLAIMPOLICY `Delete`, VOLUMEBINDINGMODE `WaitForFirstConsumer`. [code:platform/harbor/pvc-w3.yaml:4-6] [code:platform/versions.yaml:26]
- PV 셋 `Bound`, ACCESS MODES `ROX`, RECLAIM POLICY `Retain`, STORAGECLASS 빈칸, CLAIM `petmint/<같은 이름>`. [code:apps/petmint/data/nfs.yaml:18-24]
- PVC 셋 `Bound`, VOLUME이 같은 이름의 PV. [code:apps/petmint/data/nfs.yaml:56-90]
- 앱 Pod(컨테이너 `app`) 안에서 두 디렉터리가 보인다. 쓰기는 `Read-only file system`으로 실패한다. [code:apps/petmint/app/deployment.yaml:72] [code:apps/petmint/app/deployment.yaml:108-113]

## 알려진 한계

- local-path PV는 노드에 묶인다. 그 노드가 멈추면 Pod가 다른 노드로 가지 못한다. [code:apps/monitoring/prometheus/statefulset.yaml:2]
- local-path 기본 reclaimPolicy Delete. PVC 삭제가 곧 데이터 삭제다. [code:platform/harbor/pvc-w3.yaml:6]
- local-path, NFS 모두 크기를 강제하지 않는다. [code:apps/monitoring/README.md:109] [code:apps/petmint/data/nfs.yaml:18]
- local-path-provisioner 매니페스트와 기본 StorageClass 지정은 저장소에 없다. `platform/versions.yaml`에 판만 있다. [code:platform/versions.yaml:23-26]
- NFS 서버는 호스트 하나다. 호스트가 멈추면 VM도 같이 멈추므로 클러스터 전체가 멈춘다. [code:apps/petmint/data/nfs.yaml:1]
- 호스트 ufw가 inactive라 NFS를 좁히는 것은 export 대상 대역 하나뿐이다. [code:apps/petmint/README.md:102]
- 호스트 NFS 설정 스크립트가 이 저장소 밖에 있고, nfs.yaml 주석의 경로(`scripts/host-nfs-setup.sh`)는 이 저장소 기준으로 틀린다. [code:apps/petmint/data/nfs.yaml:2] [code:apps/petmint/README.md:15]

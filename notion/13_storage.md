<!--
다루는 곳: apps/petmint/data/nfs.yaml
읽은 커밋: 736d833
-->
# 13 공유 저장소

파드는 언제든 지워지고 다시 만들어진다. 파드 안에 쓴 파일은 파드와 함께 사라지므로, 남겨야 하는 데이터는 파드 바깥의 저장 공간에 둔다. 쿠버네티스에서는 이 저장 공간을 PV(PersistentVolume, 실제로 데이터가 놓이는 공간)라 하고, 파드가 「이만큼의 공간을 달라」고 내는 요청을 PVC(PersistentVolumeClaim)라 한다. [docs:history/build_log/02_metrics_storage_ingress.md:179] 이 클러스터는 저장 공간을 두 갈래로 쓴다. 하나는 노드의 로컬 디스크를 그대로 쓰는 local-path이고, 다른 하나는 호스트(VM들을 돌리는 물리 서버)의 디렉터리를 네트워크로 나눠 받는 NFS다. 이 편은 두 갈래가 어떻게 다르고 무엇이 어느 쪽을 쓰는지를 다룬다.

## 기본 저장소 local-path

local-path-provisioner는 PVC가 생기면 노드의 로컬 디스크에 디렉터리를 하나 만들어 PV로 바로 이어 주는 도구다. 사람이 PV를 미리 만들어 둘 필요가 없어서 이런 방식을 동적 프로비저닝이라 한다. [docs:history/build_log/02_metrics_storage_ingress.md:181] 업스트림 매니페스트 v0.0.30을 그대로 넣고, 이 저장소를 클러스터의 기본 StorageClass(PVC가 저장소를 따로 고르지 않으면 쓰이는 저장소 종류)로 지정했다. 매니페스트는 이 저장소에 없고 판만 기록해 두었다. [code:platform/versions.yaml:23-26]

클라우드에서는 디스크를 네트워크로 붙였다 떼었다 하는 저장소를 쓰지만, 이 클러스터는 한 대의 서버 위에 VM으로 꾸린 것이라 그런 저장소가 없다. 노드 디스크를 바로 쓰는 local-path가 이 환경에 맞았다. [docs:history/build_log/02_metrics_storage_ingress.md:183]

local-path의 디렉터리는 그 PVC를 처음 쓰는 파드가 뜬 노드에 만들어진다. [code:platform/harbor/pvc-w3.yaml:4] 한 번 만들어지면 PV는 그 노드에 묶이고, 파드는 그 노드로만 다시 뜬다. 노드를 비우면 그 파드도 멈춘다. [code:apps/monitoring/prometheus/statefulset.yaml:2] 다른 노드로 옮기려면 새 PVC를 그 노드에 만들고 데이터를 복사하는 수밖에 없다. [docs:history/build_log/08_scale_out.md:145] 그래서 상태를 가진 것들은 노드 역할에 맞춰 자리를 고정해 두었다. 두 앱의 MySQL은 app 노드에, 이미지 저장소는 infra 노드에 있다. [code:cluster/label-nodes.sh:6-8]

local-path의 기본 반환 규칙은 Delete다. PVC를 지우면 노드에 있던 데이터 디렉터리도 함께 지워진다는 뜻이다. [code:platform/harbor/pvc-w3.yaml:6] [code:apps/runshoes/mysql/statefulset.yaml:8] 크기도 강제하지 않는다. PVC에 적은 크기는 표시일 뿐이고 실제 상한은 노드 디스크다. [code:apps/monitoring/README.md:109]

이 저장소를 쓰는 것은 두 앱의 MySQL, Prometheus와 Loki, 이미지 저장소 Harbor, 빌드 서버 Jenkins다. [code:apps/petmint/mysql/statefulset.yaml:68] [code:apps/runshoes/mysql/statefulset.yaml:84] [code:apps/monitoring/prometheus/statefulset.yaml:66] [code:apps/monitoring/loki/loki.yaml:95] [code:platform/harbor/pvc-w3.yaml:17] [code:platform/jenkins/values.yaml:263] 각각의 자리는 → 「데이터베이스 복제와 백업」, → 「모니터링」, → 「이미지 저장소」, → 「빌드와 태그 고정」에서 다룬다.

## 호스트 NFS를 읽기 전용으로 붙이기

펫퍼민트 앱은 약관 데이터인 chunks와 graph 두 묶음의 파일을 읽어야 돌아간다. 초기화 작업은 고객 시드 데이터(fixtures)를 읽는다. 이 파일들은 이미지 안에 들어 있지 않다. [code:apps/petmint/data/nfs.yaml:1] 대신 호스트에 있는 펫퍼민트 저장소의 디렉터리를 NFS(한 컴퓨터의 디렉터리를 네트워크로 다른 컴퓨터에 나눠 주는 방식)로 공유하고, 클러스터는 그것을 그대로 붙인다. [code:apps/petmint/data/nfs.yaml:1-5]

복사본을 따로 두지 않은 데는 까닭이 있다. 펫퍼민트의 검색 색인은 호스트에서 이 파일들로 만든다. 앱이 같은 파일을 읽으면 색인과 앱이 보는 약관이 어긋날 일이 없다. 복사본을 두면 한쪽만 바뀌는 일이 생긴다. [code:apps/petmint/data/nfs.yaml:6] 앱은 이 파일을 켜질 때 한 번 읽으므로, 파일을 바꾼 뒤에는 앱을 다시 띄워야 반영된다. [code:apps/petmint/data/nfs.yaml:6-7]

PV는 셋이다. `petmint-chunks`와 `petmint-graph`는 앱이 붙이고, `petmint-fixtures`는 초기화 작업만 붙인다. 앱은 fixtures를 붙이지 않는다. [code:apps/petmint/data/nfs.yaml:3-5] [code:apps/petmint/app/deployment.yaml:108-124] [code:apps/petmint/jobs/init-db.yaml:59-66]

이 PV들은 여러 노드에서 동시에 읽기로 붙일 수 있는 ReadOnlyMany 모드다. 앱 파드 둘이 서로 다른 노드에 떠도 같은 파일을 붙인다. local-path처럼 한 노드에 묶이지 않으므로 앱이 노드 하나를 잃어도 다른 노드의 파드가 계속 약관을 읽는다. [code:apps/petmint/data/nfs.yaml:8] [code:apps/petmint/app/deployment.yaml:2]

읽기 전용은 세 겹으로 걸었다. 호스트가 디렉터리를 읽기 전용으로 내보내고, PV가 읽기 전용으로 붙이고, 파드도 읽기 전용으로 붙인다. [code:apps/petmint/data/nfs.yaml:8-9] 약관은 바깥으로 나가면 안 되는 데이터라, 클러스터 쪽에서 실수로 파일을 고치거나 지우는 길을 막아 두었다. 호스트는 NFS를 VM들이 쓰는 사설망 대역에만 내보낸다. [code:apps/petmint/README.md:70]

NFS는 4.2판만 쓴다. 호스트 쪽에서 옛 판인 3판을 꺼 두었기 때문인데, 3판이 따로 필요로 하는 연결 지점들을 열지 않아도 된다. [code:apps/petmint/data/nfs.yaml:23]

이 PV들은 local-path가 만든 것이 아니라 사람이 미리 적어 둔 고정 PV다. 각 PV는 펫퍼민트 네임스페이스의 같은 이름 PVC에만 묶이도록 짝을 정해 두었다. [code:apps/petmint/data/nfs.yaml:10] [code:apps/petmint/data/nfs.yaml:22] PVC 쪽은 저장소 종류를 일부러 빈칸으로 둔다. 비워 두지 않으면 기본 저장소인 local-path가 끼어들어 빈 디스크를 새로 만들어 버린다. [code:apps/petmint/data/nfs.yaml:64-65] PV에 적은 크기는 짝을 맞추기 위한 표시일 뿐이고 NFS는 크기를 강제하지 않는다. [code:apps/petmint/data/nfs.yaml:18]

PV를 지워도 호스트의 파일은 그대로 남는다. 반환 규칙을 Retain으로 두었고, 데이터의 원본은 호스트의 펫퍼민트 저장소이기 때문이다. [code:apps/petmint/data/nfs.yaml:10] [code:apps/petmint/data/nfs.yaml:20]

호스트에서 NFS를 내보내는 설정은 이 저장소에 없다. 펫퍼민트 저장소에 남은 스크립트이고, 관리자 권한이 필요해 사람이 돌린다. [code:apps/petmint/data/nfs.yaml:2] [code:apps/petmint/README.md:15]

## 호스트 NFS에 쓰는 것

호스트 NFS는 읽기에만 쓰이지 않는다. 펫퍼민트 MySQL 백업과 이미지 저장소의 데이터베이스 백업은 각각 호스트의 백업 디렉터리 하나만 쓰기로 열어 받은 NFS에 덤프를 쌓는다. 앞의 약관 PV와 달리 쓰기 전용 자리이고, 열린 범위가 백업 디렉터리 하나다. [code:apps/petmint/backup/cronjob.yaml:79-80] [code:apps/harbor-backup/cronjob.yaml:1-2] 자세한 것은 → 「데이터베이스 복제와 백업」과 → 「이미지 저장소」에 있다.

## 알려진 한계

- local-path는 PVC를 지우면 데이터도 지운다. Harbor처럼 손으로 Retain으로 바꿔 둔 PV만 예외다. [code:platform/harbor/pvc-w3.yaml:6]
- local-path와 NFS 모두 크기를 강제하지 않는다. 실제 상한은 노드 디스크와 호스트 디스크다. [code:apps/monitoring/README.md:109] [code:apps/petmint/data/nfs.yaml:18]
- 약관 파일을 바꿔도 앱을 다시 띄우기 전에는 반영되지 않는다. [code:apps/petmint/data/nfs.yaml:6-7]
- local-path PV가 노드에 묶여 분산 저장소가 없는 것과 NFS가 호스트 하나에 있는 것은 여러 편에 걸리는 한계와 조건이라 → 「알려진 한계」에 모았다

## 용어 풀이

- PV: 실제로 데이터가 놓이는 저장 공간
- PVC: 파드가 저장 공간을 달라고 내는 요청. 알맞은 PV와 짝이 지어지면 파드가 붙여 쓴다
- StorageClass: PVC가 어떤 저장소에서 공간을 받을지 정하는 종류. 기본으로 지정된 것이 하나 있다
- 동적 프로비저닝: PVC가 생기면 도구가 PV를 알아서 만들어 주는 것. 반대로 사람이 PV를 미리 적어 두는 것은 고정 PV다
- local-path: 노드의 로컬 디스크에 디렉터리를 만들어 PV로 쓰는 저장소
- NFS: 한 컴퓨터의 디렉터리를 네트워크로 다른 컴퓨터에 나눠 주는 방식
- ReadOnlyMany: 여러 노드에서 동시에 읽기 전용으로 붙일 수 있는 모드
- ReadWriteOnce: 한 노드에서만 읽고 쓰기로 붙일 수 있는 모드. local-path PV가 이 모드다
- 반환 규칙(reclaimPolicy): PVC를 지웠을 때 PV와 데이터를 어떻게 할지. Delete는 지우고, Retain은 남긴다

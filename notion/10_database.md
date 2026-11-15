<!--
다루는 곳: apps/petmint/mysql/, apps/runshoes/mysql/, apps/petmint/backup/, scripts/mysql-replica-seed.sh, scripts/mysql-replica-check.sh
읽은 커밋: e8e24ea
-->
# 데이터베이스 복제와 백업

클러스터에 올라간 두 앱, 펫퍼민트와 런슈즈는 각자 MySQL을 하나씩 쓴다. 앱 파드는 둘씩 떠서 하나가 죽어도 다른 하나가 요청을 받지만, 데이터베이스는 그렇게 쉽게 늘릴 수 없다. 데이터는 한 곳에만 있어야 하고, 두 곳에 나눠 쓰기 시작하면 어느 쪽이 맞는지 알 수 없게 된다. 그래서 이 클러스터는 쓰기를 받는 데이터베이스(Primary)를 하나 두고, 그 내용을 그대로 따라 적는 사본(Replica)을 다른 노드에 하나 더 둔다. 여기에 더해 펫퍼민트는 하루 한 번 덤프(데이터베이스 내용을 SQL 파일로 떠 둔 것)를 호스트에 남긴다. 이 편은 두 데이터베이스가 어디에 붙어 있는지, 사본을 어떻게 처음 맞추고 맞는지를 어떻게 보는지, 백업이 어디로 가는지를 다룬다.

## 두 앱의 데이터베이스

펫퍼민트의 MySQL은 petmint 네임스페이스의 StatefulSet(파드마다 고정된 이름과 저장 공간을 붙여 주는 쿠버네티스 묶음) `mysql`이다. 인스턴스 하나 안에 데이터베이스 petmint와 insurance_core 둘을 나눠 둔다. [code:apps/petmint/mysql/statefulset.yaml:1-2] 런슈즈의 MySQL은 runshoes 네임스페이스의 StatefulSet `runshoes-mysql`이고 데이터베이스는 runshoes 하나다. [code:apps/runshoes/mysql/statefulset.yaml:1-2] 두 쪽 모두 같은 판의 공식 MySQL 이미지 `mysql:8.0.46`을 쓴다. [code:apps/petmint/mysql/statefulset.yaml:31] [code:apps/runshoes/mysql/statefulset.yaml:41]

처음에는 MySQL 하나에 두 앱을 함께 넣을 생각이었다. 그런데 쿠버네티스의 Secret(암호 같은 비밀값을 담는 객체)은 네임스페이스 안에서만 보인다. 펫퍼민트 쪽 초기화 작업이 런슈즈의 계정 암호를 읽을 수 없으니, 런슈즈는 자기 네임스페이스에 MySQL을 따로 두었다. [docs:history/build_log/07_project_deploy.md:160]

앱은 데이터베이스를 파드 이름이 아니라 Service 이름으로 찾는다. 펫퍼민트는 `mysql`, 런슈즈는 `runshoes-mysql`이라는 이름을 부른다. 두 Service는 클러스터 안 주소를 따로 받지 않는 headless 방식이고, 클러스터 밖으로는 열지 않는다. [code:apps/petmint/mysql/service.yaml:1-11] [code:apps/runshoes/mysql/service.yaml:1-11] 이 Service는 Primary 파드만 고른다. 사본은 이름이 다른 Service(`mysql-replica`, `runshoes-mysql-replica`)를 따로 가지므로 앱은 사본을 보지 않는다. [code:apps/petmint/mysql/replica.yaml:8-20]

데이터는 노드의 로컬 디스크에 둔다. 펫퍼민트는 10Gi, 런슈즈는 2Gi를 기본 저장소 local-path에서 받는다. [code:apps/petmint/mysql/statefulset.yaml:63-71] [code:apps/runshoes/mysql/statefulset.yaml:79-87] 저장소가 무엇이고 왜 노드에 묶이는지는 → 「공유 저장소」에서 다룬다.

## Primary와 Replica가 붙는 노드

워커 노드에는 역할 라벨이 붙어 있고, w1과 w2가 앱을 맡는 app 역할이다. [code:cluster/label-nodes.sh:6-12] 사본(Replica)은 app 역할 노드에만 뜨고, 같은 앱의 Primary가 있는 노드에는 뜨지 못하게 막아 두었다. 이 막음은 「되도록」이 아니라 반드시 지키는 규칙이다. [code:apps/petmint/mysql/replica.yaml:50-58] [code:apps/runshoes/mysql/replica.yaml:44-52] 사본이 Primary와 같은 노드에 있으면 그 노드가 멈출 때 둘이 같이 멈추니, 사본을 둔 뜻이 없어지기 때문이다. [docs:history/build_log/08_scale_out.md:325]

Primary는 w1에 있다. 런슈즈 Primary는 w1을 고르도록 선호를 걸어 두었고, 펫퍼민트 Primary에는 노드를 고르는 규칙이 따로 없다. [code:apps/runshoes/mysql/statefulset.yaml:32-38] 그래도 펫퍼민트 Primary가 w1을 떠나지 않는 것은 저장 공간 때문이다. local-path 저장 공간은 처음 파드가 뜬 노드에 만들어지고 그 노드에 묶이는데, 두 Primary의 저장 공간이 모두 w1에 있다. [code:apps/runshoes/mysql/statefulset.yaml:6-7] 그 결과 app 노드 둘 중 Primary가 없는 w2에 두 사본이 함께 뜬다. [code:apps/petmint/mysql/replica.yaml:7]

## 복제가 도는 방식

MySQL은 바뀐 내용을 binlog(데이터를 바꾼 기록을 차례대로 적는 파일)에 남긴다. 사본은 Primary의 binlog를 받아 같은 순서로 다시 실행해 Primary를 따라간다. 따라갈 자리는 binlog 파일 이름과 그 안의 위치로 가리킨다. 거래마다 번호를 붙이는 GTID라는 방식도 있지만, 그것을 켜려면 Primary를 다시 시작해야 했다. 운영 중인 Primary를 멈추지 않는다는 조건이 있어서 이미 켜져 있던 binlog로 파일과 위치를 쓰는 복제를 골랐다. [code:apps/petmint/mysql/replica.yaml:3] [docs:history/build_log/08_scale_out.md:139]

복제는 서버마다 다른 번호가 필요해 사본의 server-id를 2로 두었다. Primary는 기본값 1이다. 사본에 쓰기가 들어가면 Primary와 어긋나므로 사본은 읽기 전용으로 둔다. 이 읽기 전용은 시작 인자로 걸지 않고 MySQL 안에서 영구 설정(SET PERSIST)으로 건다. 시작 인자는 영구 설정보다 앞서기 때문에, 인자로 걸어 두면 나중에 사본을 Primary로 올릴 때 풀 수가 없다. [code:apps/petmint/mysql/replica.yaml:4-5] [code:apps/petmint/mysql/replica.yaml:62-63]

Primary가 죽었을 때 사본이 저절로 Primary가 되지는 않는다. 자동 전환을 해 주는 도구(Group Replication이나 Orchestrator 같은 Operator)는 붙는 부품이 늘고 메모리를 더 먹는다. VM 몇 대에 이미지 저장소, 빌드 서버, 모니터링까지 올린 클러스터라 그 짐을 지지 않았다. 대신 사람이 알아채고 올려야 하지만, 구성이 단순하고 무엇을 하는지가 다 보인다. [docs:history/build_log/08_scale_out.md:132-137]

앱은 사본을 보지 않지만 사본을 읽는 곳이 하나 있다. Grafana는 두 앱의 기록을 사본에서 읽는다. 운영 중인 Primary에 짐을 주지 않기 위해서다. [code:apps/monitoring/grafana/datasource.yaml:26] [code:apps/monitoring/grafana/datasource.yaml:43] 자세한 것은 → 「대시보드」에 있다.

## 사본을 처음 맞추기

사본은 빈 데이터베이스로 뜬다. 여기에 Primary의 지금 내용을 붓고, 그 순간 이후의 binlog부터 따라가게 해야 한다. 이 일을 하는 스크립트가 `scripts/mysql-replica-seed.sh`이고, 컨트롤 플레인 노드 m-k8s에서 앱마다 한 번씩 돌린다. [code:scripts/mysql-replica-seed.sh:2-4]

스크립트는 먼저 사본의 복제를 멈추고 쓰기를 잠깐 연다. 그다음 Primary에서 덤프를 뜨는데, 거래 하나 안에서 읽는 방식이라 Primary의 표를 잠그지 않고, 덤프 머리에 그 시점의 binlog 자리를 주석으로 적는다. 덤프는 디스크에 내려놓지 않고 Primary에서 사본으로 바로 흘려 넣는다. [code:scripts/mysql-replica-seed.sh:5-6] [code:scripts/mysql-replica-seed.sh:17-27] 이때 계정이 든 mysql 시스템 데이터베이스까지 옮긴다. 사본을 Primary로 올렸을 때 앱 계정이 그곳에 있어야 앱이 붙을 수 있기 때문이다. [code:scripts/mysql-replica-seed.sh:7] 마지막으로 덤프 머리에서 뽑은 자리부터 복제를 시작하고, 사본을 다시 읽기 전용으로 잠근다. [code:scripts/mysql-replica-seed.sh:36-41]

이 스크립트는 사본의 데이터를 덮어쓴다. 실수로 Primary를 덮지 않도록, 사본 자리에 들어온 파드 이름에 replica가 없거나 Primary 자리에 replica가 들어 있으면 바로 멈춘다. [code:scripts/mysql-replica-seed.sh:8] [code:scripts/mysql-replica-seed.sh:12-13] 복제가 깨졌을 때도 같은 스크립트로 사본을 처음부터 다시 만든다. [docs:runbooks/mysql-replica.md:40]

복제에 쓰는 계정 repl은 복제 권한만 가진다. 그 암호는 사람이 네임스페이스마다 Secret `mysql-repl`로 만들고, 저장소에는 없다. [docs:runbooks/mysql-replica.md:15] 사본 파드는 이 Secret이 없어도 뜨도록 해 두어서, Secret을 나중에 만들었다면 사본 파드를 한 번 다시 띄워야 값을 읽는다. [code:apps/petmint/mysql/replica.yaml:6] [docs:runbooks/mysql-replica.md:28]

## 사본이 맞는지 보기

`scripts/mysql-replica-check.sh`가 세 가지를 본다. [code:scripts/mysql-replica-check.sh:5-6] 첫째는 복제 상태다. 받아 오는 쪽과 적용하는 쪽이 모두 돌고 있는지, 얼마나 뒤처졌는지, 오류가 있는지, 사본이 읽기 전용인지를 띄운다. [code:scripts/mysql-replica-check.sh:10-12] 둘째는 내용이다. 앱 데이터베이스의 표마다 정확한 행 수를 세고 계정 목록을 더해 Primary와 사본에서 똑같이 뽑은 뒤 둘을 견준다. 어림값이 아니라 실제로 센 수를 쓴다. [code:scripts/mysql-replica-check.sh:13-20] 셋째는 쓰기가 실제로 넘어가는지다. Primary에 시험용 데이터베이스를 만들어 값 하나를 넣고 사본에서 그 값을 읽은 뒤, Primary에서 지워 그 지움도 사본에 넘어가는지 본다. [code:scripts/mysql-replica-check.sh:21-28]

## Primary를 사본으로 바꾸기

Primary가 있는 w1이 오래 돌아오지 않으면 사람이 사본을 Primary로 올린다. 절차는 런북(운영 절차서) `docs/runbooks/mysql-replica.md`에 있다. 노드 재부팅처럼 잠깐 끊긴 것이면 기다리는 편이 낫다. 한 번 올리면 되돌리는 데 사본을 다시 만드는 일이 따라오기 때문이다. [docs:runbooks/mysql-replica.md:44-45]

올리는 일은 네 단계다. 사본이 받은 기록을 다 적용했는지 보고, 복제를 끊고 쓰기를 연다. 그다음 앱이 보는 Service가 사본 파드를 고르도록 바꾸고, 앱을 다시 띄워 새 쪽에 붙게 한다. [docs:runbooks/mysql-replica.md:51-68] Service를 바꿀 때는 클러스터에 먼저 반영하고 저장소의 같은 파일도 고쳐야 한다. 두 앱은 저장소 내용이 자동으로 클러스터에 반영되므로, 저장소를 고치지 않으면 다음 반영 때 옛 설정으로 돌아간다. [docs:runbooks/mysql-replica.md:60-64]

옛 Primary가 살아나도 그대로 쓰지 않는다. 그 데이터는 바꾼 순간에서 멈춘 옛것인데 쓰기가 열린 채로 뜨기 때문이다. 먼저 멈춰 두고, 새 Primary의 사본으로 다시 만든 뒤 계획된 전환을 한 번 더 해서 원래 배치로 돌린다. [docs:runbooks/mysql-replica.md:73-85]

## 백업

사본은 백업이 아니다. Primary에서 지운 것은 사본에서도 곧 지워진다. 실수로 지운 데이터를 되살리려면 그 앞 시점의 덤프가 따로 있어야 한다. [docs:history/build_log/08_scale_out.md:79]

펫퍼민트는 CronJob(정해진 시각마다 파드를 띄워 일을 하고 끝나는 작업) `mysql-backup`이 서울 시간 새벽 세 시 반에 하루 한 번 덤프를 뜬다. [code:apps/petmint/backup/cronjob.yaml:12-17] 대상은 petmint와 insurance_core 두 데이터베이스다. 계정이 든 mysql 시스템 데이터베이스는 뜨지 않는데, 계정은 펫퍼민트의 초기화 작업이 Secret 값으로 다시 만들기 때문이다. [code:apps/petmint/backup/cronjob.yaml:2-3] 앱이 계속 쓰는 중에도 표를 잠그지 않고 한 시점의 내용을 떠 낸다. [code:apps/petmint/backup/cronjob.yaml:4]

반쯤 쓴 파일이 백업처럼 남지 않게 한다. 덤프는 임시 이름으로 쓰고, 압축이 온전한지와 마지막 줄에 덤프가 끝났다는 표시가 있는지를 본 뒤에야 제 이름으로 바꾼다. 하나라도 어긋나면 작업이 실패로 끝난다. 다 쓴 파일에는 내용 검사값(sha256) 파일을 붙인다. [code:apps/petmint/backup/cronjob.yaml:6] [code:apps/petmint/backup/cronjob.yaml:55-63] 오래된 것은 30일이 지나면 지우지만, 최신 7개는 날짜와 상관없이 남긴다. 작업이 오래 멈췄다가 다시 돌 때 백업을 모두 지워 버리는 일을 막기 위해서다. [code:apps/petmint/backup/cronjob.yaml:7] [code:apps/petmint/backup/cronjob.yaml:65-68]

덤프는 클러스터 안이 아니라 호스트(VM들을 돌리는 물리 서버)의 디렉터리에 쌓인다. 호스트가 NFS(네트워크로 디렉터리를 나눠 쓰는 방식)로 백업 디렉터리 하나만 쓰기용으로 열고, 클러스터는 그것을 고정 PV(미리 만들어 둔 저장 공간) `petmint-backup`으로 붙인다. [code:apps/petmint/backup/cronjob.yaml:79-94] 호스트 쪽 NFS를 여는 설정은 펫퍼민트 저장소에 있고, 관리자 권한이 필요해 사람이 돌린다. [code:apps/petmint/backup/cronjob.yaml:79] 호스트가 NFS를 어떻게 나눠 주는지는 → 「공유 저장소」에서 다룬다. 이미지 저장소의 데이터베이스도 같은 방식으로 호스트에 백업하는데, 그것은 → 「이미지 저장소」에서 다룬다.

런슈즈는 정기 백업이 없다. 데이터베이스 구조를 바꾸는 배포 직전에 사람이 덤프를 뜨고 되살리기까지 확인한다. [code:apps/runshoes/README.md:54]

## 지우는 일은 사람이 정한다

StatefulSet이나 파드를 지워도 저장 공간 요청(PVC)은 남도록 해 두었다. [code:apps/petmint/mysql/statefulset.yaml:3] [code:apps/petmint/mysql/statefulset.yaml:18-20] 하지만 기본 저장소의 규칙상 PVC를 지우면 노드 디스크의 데이터도 함께 지워진다. [code:apps/runshoes/mysql/statefulset.yaml:8] 그래서 운영 데이터베이스의 데이터를 지우는 일, PVC와 PV를 지우는 일, 네임스페이스를 지우는 일은 사람의 승인 없이 하지 않는다. 이 저장소에서 일하는 세션도 같은 규칙을 따른다. [code:CLAUDE.md:35-38]

## 알려진 한계

- Primary가 죽으면 자동으로 넘어가지 않는다. 사람이 알아채고 올리기 전까지 두 앱의 쓰기는 실패한다. [docs:history/build_log/08_scale_out.md:28]
- 두 앱의 Primary가 모두 w1에 있다. w1 하나가 멈추면 두 데이터베이스의 쓰기가 같이 멈춘다. [code:apps/runshoes/mysql/statefulset.yaml:6-7]
- 펫퍼민트 Primary는 노드를 고르는 규칙 없이 저장 공간이 있는 자리에만 기대어 w1에 있다. 저장 공간을 새로 만들면 어느 노드에 뜰지 정해져 있지 않다. [code:apps/petmint/mysql/statefulset.yaml:21-29]
- 런슈즈는 정기 백업이 없다. 구조를 바꾸는 배포 앞의 손 덤프가 전부다. [code:apps/runshoes/README.md:54]
- 펫퍼민트 백업에는 계정이 없다. 덤프만으로 되살리면 계정은 초기화 작업으로 다시 만들어야 한다. [code:apps/petmint/backup/cronjob.yaml:2-3]
- 백업은 VM을 돌리는 같은 호스트에 쌓인다. 호스트의 디스크를 잃으면 클러스터와 백업을 함께 잃는다. [code:apps/petmint/backup/cronjob.yaml:1]
- 사본의 데이터베이스 설정 일부가 Primary와 한 파일에 있지 않다. 사본은 Primary 파일과 같은 값을 손으로 맞춰 적었으므로, Primary 설정을 바꾸면 사본 파일도 함께 고쳐야 한다. [code:apps/petmint/mysql/replica.yaml:61-67]

## 용어 풀이

- Primary: 쓰기를 받는 원래 데이터베이스
- Replica(사본): Primary의 기록을 받아 같은 내용을 따라 적는 데이터베이스. 읽기만 연다
- binlog: MySQL이 데이터를 바꾼 기록을 차례대로 남기는 파일. 복제는 이것을 다시 실행한다
- GTID: 거래마다 붙는 전역 번호. 이 클러스터는 쓰지 않고 파일 이름과 위치로 복제한다
- 승격: 사본의 복제를 끊고 쓰기를 열어 새 Primary로 쓰는 일
- 덤프: 데이터베이스 내용을 다시 넣을 수 있는 SQL 문장으로 떠 둔 파일
- StatefulSet: 파드마다 고정된 이름과 저장 공간을 붙여 주는 쿠버네티스 묶음
- headless Service: 따로 주소를 받지 않고 이름으로 파드를 바로 찾게 해 주는 Service
- PV, PVC: PV는 실제 저장 공간, PVC는 파드가 그만큼의 공간을 달라고 내는 요청
- CronJob: 정해진 시각마다 파드를 띄워 일을 하고 끝나는 작업
- NFS: 한 컴퓨터의 디렉터리를 네트워크로 다른 컴퓨터에 나눠 주는 방식

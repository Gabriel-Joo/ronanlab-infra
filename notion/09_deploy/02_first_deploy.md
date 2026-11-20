<!--
다루는 곳: apps/petmint/scripts/, apps/runshoes/scripts/create-secrets.sh, apps/petmint/jobs/
읽은 커밋: 736d833
-->
# 09-02 처음 배포와 시크릿

이 저장소에는 Secret(비밀번호나 키를 담는 쿠버네티스 리소스)이 하나도 없다. 매니페스트에는 「이 이름의 Secret에서 이 키를 읽어라」라는 참조만 있고, 실제 값은 사람이 스크립트를 돌려 클러스터에 직접 만든다. [code:apps/petmint/kustomization.yaml:28] [code:apps/runshoes/kustomization.yaml:23] 그래서 빈 클러스터에 앱을 처음 세울 때는 ArgoCD가 매니페스트를 적용하기 전에 사람이 해 둘 일이 몇 가지 있다. 이 편은 그 순서와, 비밀값을 저장소 밖에 두는 구조를 다룬다.

## 비밀값은 저장소 밖에 있다

비밀값을 git에 두지 않는 것은 이 저장소 전체의 원칙이고, 매니페스트 단계에서도 같다. 각 앱 폴더의 `scripts/create-secrets.sh`가 무작위 값을 만들어 클러스터에 바로 넣고, 값은 저장소에도 매니페스트에도 남지 않는다. [code:apps/petmint/scripts/create-secrets.sh:2] [docs:history/build_log/07_project_deploy.md:74-83]

네임스페이스도 사람이 만든다. ArgoCD는 설정 한 줄로 네임스페이스까지 만들어 줄 수 있지만, 그러면 ArgoCD가 네임스페이스를 소유하게 된다. 그 상태에서 Application을 지우거나 정리(prune)가 한 번 돌면 네임스페이스가 지워지고, 그 안에 사람이 넣은 Secret도 함께 사라진다. 처음 한 번 손이 더 가는 쪽을 골랐다. [code:apps/petmint/kustomization.yaml:13-14] [docs:history/build_log/07_project_deploy.md:74-81]

## 스크립트가 만드는 것

두 스크립트는 같은 규칙으로 움직인다. 네임스페이스가 없으면 만들고, Secret마다 이미 있는지 먼저 보고, 없을 때만 무작위 값으로 만든다. 이미 있는 Secret은 건드리지 않는다. [code:apps/petmint/scripts/create-secrets.sh:12-24] MySQL 관리자 비밀번호는 데이터 폴더를 처음 만들 때만 쓰이므로, 나중에 Secret 값을 바꾸면 데이터베이스와 Secret이 어긋나 접속이 끊긴다. 스크립트를 몇 번 돌려도 같은 결과가 나오게 한 까닭이다. [code:apps/petmint/scripts/create-secrets.sh:3] 값은 화면에 나오지 않는다. [code:apps/runshoes/scripts/create-secrets.sh:4]

| 네임스페이스 | Secret | 담는 것 |
| --- | --- | --- |
| petmint | `mysql-root` | MySQL 관리자 비밀번호 [code:apps/petmint/scripts/create-secrets.sh:26] |
| petmint | `petmint-db` | 앱 계정 비밀번호 [code:apps/petmint/scripts/create-secrets.sh:27] |
| petmint | `insurance-seed-db` | 원장 적재 계정 비밀번호 [code:apps/petmint/scripts/create-secrets.sh:28] |
| runshoes | `runshoes-mysql` | MySQL 관리자 비밀번호와 앱 계정 비밀번호 [code:apps/runshoes/scripts/create-secrets.sh:25-31] |
| runshoes | `runshoes-auth` | 로그인 토큰 서명 키, 시드 사용자와 관리자의 첫 비밀번호 [code:apps/runshoes/scripts/create-secrets.sh:43-50] |
| 둘 다 | `harbor-pull` | 사설 이미지 저장소의 받기 전용 로봇 계정 [code:apps/runshoes/scripts/create-secrets.sh:33-41] |

`harbor-pull`만은 무작위 값이 아니다. 사람이 Harbor에서 받기 권한만 있는 로봇 계정을 만들고, 그 이름과 비밀번호를 환경변수로 넘겨 스크립트를 돌린다. 로봇 이름에는 `$` 기호가 들어 있어 작은따옴표로 감싸야 한다. [code:apps/petmint/scripts/create-secrets.sh:6-8] [code:apps/petmint/scripts/create-secrets.sh:30-38] Harbor의 앱 프로젝트는 비공개라서 이 Secret이 없으면 파드가 이미지를 받지 못하고 멈춘다. [repo:apps/petmint/README.md:97-99] 노드가 이미지를 받는 데는 받기 권한만 있으면 되므로, Jenkins가 이미지를 올릴 때 쓰는 로봇과 따로 둔다. [docs:history/build_log/07_project_deploy.md:158] 올리는 쪽은 → 「빌드와 태그 고정」에서 다룬다. 두 네임스페이스에는 MySQL 복제 계정 Secret도 하나씩 더 있는데, 이것은 복제본을 세울 때 사람이 만든다. [code:apps/petmint/mysql/replica.yaml:6] 자세한 것은 → 「데이터베이스 복제와 백업」에 있다.

비밀번호를 바꾸는 길도 정해져 있다. 펫퍼민트 앱 계정은 Secret을 지우고 스크립트를 다시 돌린 뒤 초기화 Job을 돌리면, Job이 데이터베이스 쪽 비밀번호를 새 값으로 맞춘다. [code:apps/petmint/scripts/create-secrets.sh:4] 런슈즈의 시드 사용자와 관리자 비밀번호는 앱이 처음 뜰 때 비밀번호가 비어 있는 계정에만 쓰여서, 나중에 Secret을 바꿔도 이미 채운 계정은 그대로다. 서명 키를 바꾸면 이미 나간 로그인 토큰이 모두 무효가 되고, 바꾼 뒤에는 파드를 다시 띄워야 한다. [code:apps/runshoes/scripts/create-secrets.sh:9-10]

## 처음 세우는 순서

펫퍼민트는 먼저 GPU 호스트에서 약관과 시드 파일 폴더를 NFS 읽기 전용으로 공유한다. 이 일은 호스트 관리자 권한이 필요해 사람이 한 번 한다. [repo:apps/petmint/README.md:47-49] 고객 시드 파일은 가짜 데이터지만 이름과 전화번호 모양이라 git에서 뺐고, 예시 파일을 복사해 채워 둔다. [repo:apps/petmint/README.md:44-45] 그다음 네임스페이스와 Secret을 만들고, ArgoCD Application이 생기면 Sync한다. Application은 루트 Application이 앱 폴더의 `app.yaml`을 읽어 만들므로 손으로 넣지 않는다. [repo:apps/petmint/README.md:50-55] 공유 저장소의 구조는 → 「공유 저장소」에서 다룬다.

첫 Sync에서는 초기화 Job이 데이터베이스와 계정을 만들고, 스키마 두 벌을 맞추고, 원장이 비어 있으면 시드를 넣는다. [code:apps/petmint/jobs/init-db.yaml:1-5] Job은 MySQL 관리자 비밀번호로 계정을 만들고, 앱 계정과 적재 계정 비밀번호를 같은 Secret에서 읽어 맞춘다. [code:apps/petmint/jobs/init-db.yaml:46-54] 첫 배포에서는 MySQL이 뜨기 전에 Job이 시작할 수 있어서, 실패해도 여러 번 다시 시도하며 기다린다. [code:apps/petmint/jobs/init-db.yaml:19] 끝난 Job은 하루 뒤 저절로 지워진다. [code:apps/petmint/jobs/init-db.yaml:20] 이 순서는 실제 클러스터에 넣기 전에 버려도 되는 로컬 클러스터에서 먼저 돌려 보았다. 빈 볼륨이면 Job이 재시도하며 기다리고, 약관이 없으면 앱이 빠진 파일을 밝히며 멈추는 것까지 확인했다. [repo:apps/petmint/README.md:106-113]

런슈즈는 Harbor에 비공개 프로젝트와 로봇 계정 둘(Jenkins가 올리는 것, 노드가 받는 것)을 먼저 만든다. 그다음 네임스페이스와 Secret, Jenkins가 읽을 올리기 자격 증명 Secret을 만든다. [repo:apps/runshoes/README.md:38-47] `kustomization.yaml`의 첫 태그 값은 Harbor에 없는 자리값이었다. 첫 Jenkins 빌드가 그 줄을 실제 태그로 바꾼 뒤에 Sync해야 이미지를 받을 수 있다. [code:apps/runshoes/kustomization.yaml:29] MySQL 이미지는 빈 데이터 폴더에서 처음 뜰 때 Secret 값으로 데이터베이스와 앱 계정을 만들고, 앱은 MySQL이 준비된 뒤 Flyway로 스키마와 시드를 넣는다. [repo:apps/runshoes/README.md:45] [repo:apps/runshoes/README.md:51-52]

런슈즈의 로그인 Secret은 앱 파드에 반드시 있어야 하는 것으로 붙어 있다. 이 Secret 없이 새 이미지를 올리면 새 파드가 시작하지 못하고 롤링이 멈춘다. 그래서 로그인 기능을 처음 넣을 때는 Secret을 먼저 만들고, 그것을 읽는 설정을 이미지보다 먼저 적용했다. 옛 이미지는 그 설정을 읽지 않아 아무 일도 일어나지 않는다. [code:apps/runshoes/app/deployment.yaml:108-110] [repo:apps/runshoes/runbooks/auth-v3.md:16-19]

## 알려진 한계

- 비밀값이 클러스터에만 있는 것은 여러 편에 걸리는 한계라 → 「알려진 한계」에 모았다
- 네임스페이스, Secret, 호스트 NFS 공유는 사람이 하는 단계라 ArgoCD가 대신해 주지 않는다. [repo:apps/petmint/README.md:47-52]

### 조건

아래는 고른 것이 아니라 바탕이 그러해서 따라오는 것이다.

- Harbor 로봇 비밀번호는 만들 때 한 번만 보인다. 잃으면 로봇을 다시 만들어야 한다. [docs:history/build_log/06_jenkins.md:174]
- 런슈즈 서명 키를 바꾸면 모든 사용자가 다시 로그인해야 한다. [code:apps/runshoes/scripts/create-secrets.sh:10]

## 용어 풀이

- Secret: 비밀번호나 키를 담아 파드에 넘겨 주는 쿠버네티스 리소스
- 네임스페이스: 클러스터 안을 앱별로 나눈 칸. Secret은 칸 단위로 보인다
- prune: git에서 사라진 리소스를 클러스터에서도 지우는 ArgoCD 동작
- 로봇 계정: 프로그램이 쓰도록 권한을 좁혀 만든 Harbor 계정
- 초기화 Job: 앱보다 먼저 데이터베이스와 계정, 스키마를 맞추는 한 번짜리 작업
- 시드: 처음 넣어 두는 기본 데이터
- Flyway: 스키마 변경 파일을 번호 순서대로 한 번씩 적용하는 도구

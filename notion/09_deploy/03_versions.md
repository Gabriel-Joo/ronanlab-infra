<!--
다루는 곳: apps/runshoes/runbooks/, apps/runshoes/scripts/check-image-migrations.sh
읽은 커밋: 6290346
-->
# 09-03 버전이 바뀌는 길

앱의 새 버전이 운영에 들어가는 길은 둘이다. 데이터베이스 스키마가 그대로인 배포는 push 한 번으로 저절로 들어간다. 스키마를 바꾸는 배포는 사람이 단계마다 멈추고 확인하며 넣는다. 이 편은 이 저장소의 런슈즈 폴더 `apps/runshoes/runbooks/`에 남은 런북(절차와 실행 기록을 한 파일에 적은 문서) 열다섯 편을 실제 예시로 삼아 두 번째 길을 따라간다. 런북마다 바뀐 기능이 다르지만 여기서는 기능을 보지 않고, 앱 하나가 어떤 경로로 클러스터에 올라가고 버전이 어떻게 바뀌어 가는지만 본다. [code:apps/runshoes/runbooks/]

## 이미지를 바꾸는 순간 스키마가 바뀐다

런슈즈의 스키마는 Flyway가 바꾼다. 스키마 변경 파일은 앱 이미지 안에 들어 있고, 새 이미지의 파드가 뜰 때 Flyway가 아직 적용하지 않은 파일을 차례로 적용한다. 그래서 MySQL 매니페스트는 바뀌지 않고, 이미지를 Sync하는 일이 곧 스키마를 바꾸는 일이다. [code:apps/runshoes/runbooks/auth-v3.md:6-7] 런슈즈 MySQL에는 정기 백업이 없다. 스키마를 바꾸기 전에는 반드시 덤프를 뜨고 복원까지 확인한다. [code:apps/runshoes/README.md:54]

스키마가 그대로인 배포는 평소의 길로 간다. 앱 저장소 main에 push하면 Jenkins가 태그 커밋을 남기고, ArgoCD 자동 Sync가 3분 안에 받아 파드를 하나씩 바꾼다. [code:apps/runshoes/README.md:27] [code:apps/runshoes/README.md:35] 런북에도 이런 배포가 기록돼 있다. 새 스키마 변경 파일이 없는 배포는 이미지 Sync 하나로 끝났고 덤프는 뜨지 않았다. [code:apps/runshoes/runbooks/auth-v3.md:204-206] 빌드가 바깥 저장소에 닿지 못해 실패한 뒤 다시 빌드한 이미지도, 스키마 변경이 없어 덤프 없이 Sync했다. [code:apps/runshoes/runbooks/catalog-v4-v5.md:252-254]

문제는 스키마를 바꾸는 배포다. 자동 Sync가 켜진 채로 push하면 Jenkins의 태그 커밋이 3분 안에 운영에 들어가 덤프와 확인을 건너뛴다. [code:apps/runshoes/runbooks/auth-v3.md:25-26] 그래서 이 배포는 자동 Sync를 잠시 끄고 사람이 한 단계씩 넣는다. [code:apps/runshoes/app.yaml:9] 펫퍼민트도 같은 사정이다. 펫퍼민트는 초기화 Job이 Sync마다 스키마를 맞추므로, 앱 커밋에 든 스키마 변경이 push만으로 운영 데이터베이스에 들어간다. 되돌리기 어려운 변경은 먼저 자동 Sync를 끄고 한다. [code:apps/petmint/README.md:30-36]

## 스키마를 바꾸는 배포의 단계

지금 쓰는 순서는 V24 런북 1절의 표에 있다. 자동 Sync 끄기, 끈 것을 확인하기, push와 태그 커밋, Sync 전 확인과 덤프, 복원 확인, Sync, 자동 Sync 다시 켜기의 일곱 단계다. [code:apps/runshoes/runbooks/v24-chatbot-miss-note.md:40-50] 이 순서는 처음부터 이 모양이 아니었다. 단계마다 그 단계가 생긴 까닭을 가장 잘 보여 주는 런북이 있다.

**자동 Sync를 끈다.** ArgoCD Application의 자동 Sync를 켜고 끄는 실제 스위치는 클러스터에서 그 Application을 고치는 명령이고, 저장소의 `app.yaml`은 기록이다. [code:apps/runshoes/runbooks/catalog-v4-v5.md:55] [code:apps/runshoes/README.md:36] V4와 V5 런북은 이 단계를 사람이 직접 하는 일로 정했다. 배포를 막는 장치이기 때문이다. [code:apps/runshoes/runbooks/catalog-v4-v5.md:37] V6부터 V9까지 네 개를 한 번에 배포한 것도 자동 Sync를 두 번 껐다 켜지 않으려는 것이었다. [code:apps/runshoes/runbooks/admin-demo-v6-v9.md:5]

**끈 것을 push 전에 확인한다.** 이 단계는 나중에 더해졌다. V19와 V20을 배포할 때 ArgoCD 이력만으로는 push 시점에 자동 Sync가 정말 꺼져 있었는지 확인할 수 없었다. 그 뒤부터 사람이 친 확인 명령의 출력을 앱 쪽 관리자에게 붙여 보이고 나서 push한다. [code:apps/runshoes/runbooks/v21-grafana-compare-views.md:54] 이 단계가 왜 중요한지는 V22와 V23 배포에서 드러났다. 자동 Sync가 켜진 채 앱 push가 먼저 나갔고, Jenkins 빌드가 끝나 태그 커밋이 생기기 전에 자동 Sync를 꺼서 겨우 피했다. 빌드가 더 빨랐다면 덤프 없이 스키마가 바뀌었을 것이다. [code:apps/runshoes/runbooks/v22-v23-review-hide-miss-status.md:151-152] [code:apps/runshoes/runbooks/v22-v23-review-hide-miss-status.md:158] 그래서 V24 런북은 「끄기와 확인은 반드시 push 전에」를 첫머리에 다시 적었다. [code:apps/runshoes/runbooks/v24-chatbot-miss-note.md:63]

**앱을 push하고 Jenkins가 태그 커밋을 남긴다.** 자동 Sync가 꺼져 있으므로 ArgoCD는 「저장소와 클러스터가 다르다」는 표시(OutOfSync)만 띄우고, 운영은 옛 이미지 그대로 돈다. [code:apps/runshoes/runbooks/v24-chatbot-miss-note.md:46] 처음 로그인 기능을 넣은 V3 배포에서는 이 앞에 한 단계가 더 있었다. 새 이미지가 읽을 Secret을 만들고, 그것을 파드에 붙이는 설정만 먼저 Sync했다. Jenkins가 태그 커밋을 main에 직접 올리므로, 설정과 새 태그가 같은 main에 함께 있게 되면 Sync하는 순간 백업 없이 스키마가 바뀐다. 그래서 설정 Sync를 push보다 먼저 끝냈다. [code:apps/runshoes/runbooks/auth-v3.md:16-20] [code:apps/runshoes/runbooks/auth-v3.md:31-32]

**이미지 안의 스키마 변경 파일을 확인한다.** 로컬에서 시험한 그 파일이 정말 이미지에 들어갔는지 Sync 전에 본다. 스키마 파일만 고치고 앱을 다시 빌드하지 않아 어긋난 적이 있었기 때문이다. [code:apps/runshoes/runbooks/auth-v3.md:160-162] `apps/runshoes/scripts/check-image-migrations.sh`가 이 일을 한다. 태그를 주면 Harbor에 올라간 이미지를 워커 노드의 컨테이너 런타임으로 받아, 이미지 안 앱 파일에 든 스키마 변경 파일마다 sha256 지문을 낸다. 그 값을 앱 저장소의 같은 커밋 파일과 견준다. [code:apps/runshoes/scripts/check-image-migrations.sh:2] [code:apps/runshoes/scripts/check-image-migrations.sh:7-9] 노드로 받는 것은 kubelet이 이미지를 받는 것과 같은 길, 같은 받기 전용 계정이라서다. 호스트의 docker로 받으면 바깥 공개 경로로 나가 인증 관문에 막힌다. 받은 이미지는 쿠버네티스와 섞이지 않게 따로 떼어 둔 칸에 두고 끝나면 지운다. [code:apps/runshoes/scripts/check-image-migrations.sh:3-5] [code:apps/runshoes/scripts/check-image-migrations.sh:36-44] 이 방법이 막히면 빌드 직후 로컬 이미지에서 꺼내 보는 것으로 대신하고, 「Harbor를 거친 이미지는 확인하지 못했다」고 기록에 남긴다. [code:apps/runshoes/runbooks/auth-v3.md:174]

**도는 배치가 없는지 보고 덤프를 뜬다.** V14부터 런슈즈에는 매일 새벽 도는 요약 CronJob이 있다. 그 시각에 Sync하면 옛 이미지의 Job이 도는 중에 스키마가 바뀐다. 그래서 Sync 전에 도는 Job이 없는지 보고, 배치 시각 근처를 피한다. [code:apps/runshoes/runbooks/v15-weight-norm.md:44] [code:apps/runshoes/runbooks/v24-chatbot-miss-note.md:69-74] 덤프는 운영 MySQL 파드 안에서 뜬다. 테이블을 잠그지 않고 한 시점의 모습으로 떠서 앱은 그대로 돈다. 데이터베이스 이름을 덤프에 넣지 않아 다른 이름으로 복원해 볼 수 있고, 관리자 비밀번호는 파드 안의 환경변수로만 쓰여 화면이나 파일에 나오지 않는다. [code:apps/runshoes/runbooks/auth-v3.md:61-63] 덤프에는 비밀번호 해시와 활동 기록이 들어 있어, 읽기 권한을 주인에게만 두고 git 밖에 둔다. [code:apps/runshoes/runbooks/v24-chatbot-miss-note.md:85]

**복원을 확인한다.** 덤프를 개발용 MySQL에 다른 이름으로 넣어 보고, 그 안의 리뷰 개수와 지문(행 번호를 이어 붙여 낸 sha256)이 운영 공개 API의 값과 같은지 견준다. 셋 중 하나라도 맞지 않으면 Sync하지 않는다. [code:apps/runshoes/runbooks/auth-v3.md:65-87] 리뷰가 많아진 뒤에는 이어 붙인 글이 기본 길이에서 잘려 지문이 틀리는 일이 있어, 길이 제한을 먼저 늘린다. [code:apps/runshoes/runbooks/catalog-v4-v5.md:107] 덤프와 Sync 사이는 끊지 않고 잇는다. 덤프 뒤에 들어온 쓰기는 덤프에 없어서, 덤프로 복원하면 그 사이의 쓰기가 사라진다. 사이가 길어졌으면 덤프부터 다시 뜬다. [code:apps/runshoes/runbooks/auth-v3.md:28-29]

**태그 커밋을 Sync한다.** Sync는 사람이 Jenkins의 태그 커밋을 지정해 한 번 돌린다. [code:apps/runshoes/runbooks/v24-chatbot-miss-note.md:57-58] 파드가 둘이므로 옛 파드 하나가 내려가고 새 파드가 스키마를 바꾸며 뜬다. 그동안 남은 옛 파드는 바뀐 스키마 위에서 돈다. 그래서 스키마 변경은 옛 이미지가 모르는 열이나 표를 더하는 꼴로 짜고, 새 기능은 새 파드 둘이 다 뜬 뒤에 쓴다. [code:apps/runshoes/runbooks/v22-v23-review-hide-miss-status.md:61-62] [code:apps/runshoes/runbooks/v24-chatbot-miss-note.md:64-65]

**확인하고 자동 Sync를 다시 켠다.** 새 파드 로그에 스키마 변경을 적용했다는 줄이, 둘째 파드에는 「이미 최신」이라는 줄이 있어야 한다. 웹, 챗봇, CronJob이 모두 같은 새 태그인지, 원본과 복제본 데이터베이스 둘 다 새 버전인지, 공개 API의 개수와 지문이 Sync 전과 같은지 본다. 다르면 자동 Sync를 꺼 둔 채 멈추고 알린다. [code:apps/runshoes/runbooks/v24-chatbot-miss-note.md:110-128] 다 맞으면 자동 Sync를 끄기 전 값으로 다시 켠다. [code:apps/runshoes/runbooks/v24-chatbot-miss-note.md:59-60]

**기록한다.** 런북마다 끝에 실행 기록 표가 있다. 단계마다 누가 했고, 덤프 크기와 지문, 새 파드가 무엇을 적용했는지, 순서가 런북과 달랐다면 왜 괜찮았는지를 적는다. [code:apps/runshoes/runbooks/v24-chatbot-miss-note.md:144-153] 덤프는 언제 지울지도 정해 둔다. 다음 스키마 변경이 운영에서 탈 없이 돈 뒤에 지운다. [code:apps/runshoes/runbooks/auth-v3.md:176-185]

## 실패하면

새 파드가 준비되지 못하면 롤링이 멈추고 옛 파드가 계속 받으므로, 급하게 할 일은 없다. [code:apps/runshoes/runbooks/auth-v3.md:121-122] 되돌리는 길은 어디서 멈췄느냐에 따라 셋이다. [code:apps/runshoes/runbooks/auth-v3.md:124-128]

첫째, 스키마 변경이 첫 가드(조건이 맞지 않으면 아무것도 바꾸지 않고 멈추는 첫 구문)에서 멈추면 데이터베이스는 그대로다. 바뀐 것은 Flyway 이력의 실패 줄 하나뿐이고, 원인을 정한 뒤 그 줄만 지운다. [code:apps/runshoes/runbooks/auth-v3.md:126] [code:apps/runshoes/runbooks/auth-v3.md:132-138] 둘째, 가드 뒤 어디선가 멈추면 일부만 적용된 채 남는다. MySQL에서 스키마 변경은 되돌려지지 않기 때문이다. 이때는 앱을 내리고, 데이터베이스를 다시 만들고, 덤프를 넣고, 지문을 확인한 뒤 태그 커밋을 revert해 Sync한다. [code:apps/runshoes/runbooks/auth-v3.md:140-152] [code:apps/runshoes/runbooks/v22-v23-review-hide-miss-status.md:129] 셋째, 스키마는 잘 바뀌었는데 새 앱이 이상하면 이미지만 되돌린다. 인프라 저장소의 태그 커밋을 revert하고 Sync하면 된다. 옛 이미지는 바뀐 스키마 위에서도 뜬다. Flyway는 자기가 모르는 앞선 버전을 넘기고, 앱의 스키마 검사는 늘어난 열과 표를 문제 삼지 않는다. [code:apps/runshoes/runbooks/auth-v3.md:154-158] [code:apps/runshoes/runbooks/v24-chatbot-miss-note.md:135] 그래서 런북마다 옛 이미지가 새 스키마에서 뜨는지 로컬에서 미리 확인해 둔다. [code:apps/runshoes/runbooks/catalog-v4-v5.md:31] 더한 열은 지우지 않는다. 남아도 해가 없고, 다시 새 이미지로 올리면 그 값이 그대로 보인다. [code:apps/runshoes/runbooks/v22-v23-review-hide-miss-status.md:131] [code:apps/runshoes/runbooks/v24-chatbot-miss-note.md:136]

태그 커밋 revert는 이미지만 되돌리고 데이터베이스는 되돌리지 않는다. 데이터까지 돌아가야 하면 Sync 직전 덤프로 복원해야 하고, 그 덤프 뒤의 쓰기는 사라진다. [code:apps/runshoes/README.md:29] [code:apps/runshoes/README.md:64-65]

## 열다섯 편이 보여 주는 것

같은 뼈대 위에서 런북마다 조금씩 다른 것이 붙었다. 아래 표는 기능이 아니라 배포의 모양만 적었다.

| 런북 | 스키마를 바꿨나 | 배포 구조에서 달랐던 것 |
| --- | --- | --- |
| `auth-v3` | V3, 표와 데이터 | 절차의 원형. Secret과 그것을 붙이는 설정을 이미지보다 먼저 적용 [code:apps/runshoes/runbooks/auth-v3.md:14-32] |
| `catalog-v4-v5` | V4, V5 | 한 이미지에 변경 둘. Sync 뒤 관리자 API로 데이터를 묶음별로 적재 [code:apps/runshoes/runbooks/catalog-v4-v5.md:33-51] |
| `admin-demo-v6-v9` | V6 ~ V9 | 넷을 한 번에 배포해 자동 Sync를 한 번만 끄고 켬. 새 설정 값을 이미지보다 먼저 커밋 [code:apps/runshoes/runbooks/admin-demo-v6-v9.md:36-53] |
| `v10-auto-increment` | V10 | 표를 다시 만드는 변경이라 그동안 그 표의 쓰기가 잠깐 기다림 [code:apps/runshoes/runbooks/v10-auto-increment.md:51-52] |
| `v11-admin-history` | V11 | Sync 뒤 운영 쓰기를 승인을 다시 받아 따로 함 [code:apps/runshoes/runbooks/v11-admin-history.md:61-73] |
| `v12-wide-scope` | V12, 열 추가 | 단계를 줄인 짧은 판 [code:apps/runshoes/runbooks/v12-wide-scope.md:22-31] |
| `v13-model-en` | V13, 열 추가 | V12와 같은 짧은 판 [code:apps/runshoes/runbooks/v13-model-en.md:22-31] |
| `v14-shoe-summaries` | V14, 새 표 | 같은 Sync에 새 CronJob을 멈춘 채 넣고, 첫 실행 뒤 git에서 풀었음 [code:apps/runshoes/runbooks/v14-shoe-summaries.md:54-64] |
| `v15-weight-norm` | V15, V16 | 데이터를 다시 쓰지 않는 계산 열이라도 Sync가 곧 스키마 변경이라 같은 절차 [code:apps/runshoes/runbooks/v15-weight-norm.md:15] |
| `v17-v18-chatbot` | V17, V18 | 기존 값을 고치는 변경에 첫 구문 가드. 사이드카 이미지 구조가 바뀌어도 매니페스트는 그대로 [code:apps/runshoes/runbooks/v17-v18-chatbot.md:16-18] [code:apps/runshoes/runbooks/v17-v18-chatbot.md:28] |
| `v19-v20-observability` | V19, V20, 새 표 | 검사 경로를 바꾸는 매니페스트 변경은 새 이미지가 오른 것을 본 뒤 따로 [code:apps/runshoes/runbooks/v19-v20-observability.md:152-163] |
| `v21-grafana-compare-views` | V21, 뷰 | 끈 것을 사람 출력으로 확인하는 단계를 더함. 지표 수집 주석은 이미지 뒤 따로 [code:apps/runshoes/runbooks/v21-grafana-compare-views.md:54] [code:apps/runshoes/runbooks/v21-grafana-compare-views.md:150-158] |
| `v22-v23-review-hide-miss-status` | V22, V23, 열 추가 | 자동 Sync가 켜진 채 push가 먼저 나간 사고 [code:apps/runshoes/runbooks/v22-v23-review-hide-miss-status.md:147-158] |
| `v24-chatbot-miss-note` | V24, 열 추가 | 지금 쓰는 순서 표 [code:apps/runshoes/runbooks/v24-chatbot-miss-note.md:40-65] |
| `reviews-1500` | 없음 | 이미지와 Sync 없이 운영 MySQL에 SQL 한 묶음. 덤프, 복원본 리허설, 적용, 확인. 되돌리기는 덤프 [code:apps/runshoes/runbooks/reviews-1500.md:5] [code:apps/runshoes/runbooks/reviews-1500.md:20-29] [code:apps/runshoes/runbooks/reviews-1500.md:69-73] |

표에서 보이는 흐름이 둘 있다. 하나는 매니페스트와 이미지의 순서다. 새 이미지가 읽을 Secret이나 설정은 이미지보다 먼저 넣고, 새 이미지에만 있는 것(검사 경로, 지표 경로)을 가리키는 매니페스트 변경은 이미지가 운영에 오른 것을 확인한 뒤에 넣는다. 거꾸로 하면 롤링이 멈춘다. [code:apps/runshoes/runbooks/auth-v3.md:31-32] [code:apps/runshoes/runbooks/v19-v20-observability.md:163] 다른 하나는 스키마 변경의 꼴이다. 뒤로 갈수록 맨 뒤에 빈 열이나 새 표를 더하기만 하는 변경이 많아졌다. 옛 파드와 옛 이미지가 그대로 뜨므로 롤링 중에도, 되돌릴 때도 덤프 복원이 필요한 일이 드물다. [code:apps/runshoes/runbooks/v24-chatbot-miss-note.md:31-33] [code:apps/runshoes/runbooks/v19-v20-observability.md:149]

`reviews-1500`은 결이 다르다. 스키마를 바꾸지 않고 데이터만 다시 만든 일이라 이미지나 Sync와 상관이 없다. 그래도 운영 데이터베이스를 바꾸는 일이라 같은 원칙을 따랐다. 사람이 덤프를 뜨고, 그 덤프를 로컬에 복원해 같은 SQL을 미리 돌려 보고, 쓰기 전과 뒤의 조건을 가드 열두 개로 걸어 하나라도 틀리면 한 트랜잭션 전체가 취소되게 했다. [code:apps/runshoes/runbooks/reviews-1500.md:18] [code:apps/runshoes/runbooks/reviews-1500.md:20-29] 운영 데이터베이스에 직접 쓰는 명령은 사람이 친다. [code:apps/runshoes/runbooks/reviews-1500.md:6]

## 알려진 한계

- 자동 Sync를 끄고 켜는 일이 사람 손에 달려 있다. 끄기를 잊고 push하면 덤프 없이 스키마가 바뀔 수 있다. [code:apps/runshoes/runbooks/v22-v23-review-hide-miss-status.md:158]
- 자동 Sync를 끈 정확한 시각은 ArgoCD에 남지 않는다. [code:apps/runshoes/runbooks/v21-grafana-compare-views.md:167]
- 덤프와 Sync 사이에 들어온 쓰기는 덤프로 복원하면 사라진다. [code:apps/runshoes/runbooks/auth-v3.md:28]
- 덤프는 호스트 디스크 한 곳에만 있다. [code:apps/runshoes/runbooks/auth-v3.md:180]
- 이미지 안 파일 확인 스크립트는 호스트에서 노드로 접속해 돌며, 노드에서 잠깐 받기 계정 비밀번호가 명령 인자로 보인다. [code:apps/runshoes/scripts/check-image-migrations.sh:11]
- 오래된 런북에는 지금과 다른 값이 남아 있다. 롤링 설정, 파드 수, 자동 Sync 스위치를 고치는 파일 자리가 그때 기준이다. 지금 값은 매니페스트를 따른다. [code:apps/runshoes/runbooks/auth-v3.md:122] [code:apps/runshoes/runbooks/catalog-v4-v5.md:55] [code:apps/runshoes/app/deployment.yaml:22-28]

## 용어 풀이

- 런북: 한 번의 운영 작업을 위한 절차와 그 실행 기록을 한 파일에 적은 문서
- 스키마: 데이터베이스의 표와 열의 생김새
- 마이그레이션: 스키마를 한 판에서 다음 판으로 바꾸는 변경 파일
- 덤프: 데이터베이스 내용을 SQL 파일로 떠 둔 것
- 지문: 데이터를 이어 붙여 해시 함수로 계산한 값. 하나라도 다르면 값이 달라진다
- 가드: 조건이 맞지 않으면 아무것도 바꾸지 않고 멈추게 하는 구문
- OutOfSync: 저장소의 선언과 클러스터의 실제가 다르다는 ArgoCD 표시
- 수동 Sync: 자동 Sync를 끈 채 사람이 정한 커밋으로 한 번 적용하는 것
- revert: 앞선 커밋의 변경을 거꾸로 적용하는 새 커밋

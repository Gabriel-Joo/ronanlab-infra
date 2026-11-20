<!--
다루는 곳: apps/petmint/app/, apps/petmint/jobs/, apps/petmint/scripts/, apps/petmint/README.md, apps/runshoes/app/, apps/runshoes/scripts/, apps/runshoes/README.md, apps/runshoes/runbooks/
읽은 커밋: 736d833
-->
# 09 앱이 올라가는 길

클러스터에는 앱이 둘 올라가 있다. 펫퍼민트(`petmint`)와 러닝화 스펙 아카이브인 런슈즈(`runshoes`)다. [repo:apps/runshoes/README.md:3] 두 앱은 같은 길로 클러스터에 들어간다. 개발자가 앱 저장소 main에 push하면 Jenkins가 이미지를 굽고 인프라 저장소의 태그 한 줄을 바꿔 커밋하고, ArgoCD가 그 커밋을 받아 클러스터에 적용한다. 클러스터에서는 앱 파드 두 개가 하나씩 차례로 새 이미지로 바뀐다. [repo:apps/petmint/README.md:23-27] [repo:apps/runshoes/README.md:27-31] 이 가운데 빌드와 태그 커밋까지는 → 「빌드와 태그 고정」, 커밋을 클러스터가 받아 가는 장치는 → 「GitOps」에서 다룬다. 이 편은 그 뒤, 앱 하나가 어떤 매니페스트로 서 있고 처음에 어떻게 세우며 버전이 어떻게 바뀌어 가는지를 다룬다.

두 앱은 모양이 닮았다. 상태(데이터)는 모두 MySQL에 있고 앱 파드는 상태가 없어서, 파드 둘을 서로 다른 노드에 나눠 띄우고 하나씩 바꿔 끼울 수 있다. [code:apps/petmint/app/deployment.yaml:1-7] [code:apps/runshoes/app/deployment.yaml:1-13] 다른 점은 데이터베이스 스키마를 바꾸는 방법이다. 펫퍼민트는 앱 파드보다 먼저 도는 초기화 Job이 스키마를 맞추고, 런슈즈는 앱이 뜰 때 Flyway(스키마 변경 파일을 차례로 적용하는 도구)가 스스로 맞춘다. [code:apps/petmint/jobs/init-db.yaml:1-7] [repo:apps/runshoes/README.md:52] 어느 쪽이든 새 이미지가 뜨는 순간 운영 데이터베이스가 바뀐다는 점은 같고, 이 사실이 버전을 바꾸는 절차 전체를 정한다.

하위 편은 셋이다. → 「매니페스트의 꼴」은 앱 하나를 이루는 Deployment, Service, Ingress, PDB, ConfigMap, Job, CronJob이 무엇이고 왜 그 값인지를 본다. → 「처음 배포와 시크릿」은 빈 클러스터에 앱을 처음 세우는 순서와, 저장소에 없는 비밀값을 사람이 만드는 구조를 다룬다. → 「버전이 바뀌는 길」은 런슈즈의 실행 기록(런북) 열다섯 편을 실제 예시로 삼아, 스키마를 바꾸는 배포가 어떤 단계를 거치고 실패하면 어떻게 되돌리는지를 따라간다. [code:apps/runshoes/runbooks/]

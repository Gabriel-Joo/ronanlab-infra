# ronanlab-infra — 세션 규칙

이 저장소에서 도는 Claude 세션(관리자 · 그 밖)이 읽는 규칙이다. 2026-11-11 처음 씀.
모르는 것은 「정해지지 않음」으로 둔다 — 지어내지 않는다.

## 1. 이 저장소가 무엇인가

- 홈랩 쿠버네티스(kubeadm 1.35.9, VM m-k8s · w1~w4)의 선언 저장소. 원격 `git@github.com:Gabriel-Joo/ronanlab-infra.git`
- **`main`이 곧 운영이다.** ArgoCD 루트 Application(`bootstrap/root-app.yaml`, App of Apps)이 `main`의 `apps/*/app.yaml`을 읽어 앱 Application을 만들고, 각 앱도 `targetRevision: main`을 본다
  - 자동 Sync인 앱은 push하면 3분 안에 클러스터에 들어간다. 2026-11-11 클러스터 기준 자동: runshoes · petmint · monitoring · harbor-backup, 수동: cloudflared
  - 자동 Sync 켜고 끄기의 실제 스위치는 클러스터의 `kubectl patch`이고 `app.yaml`은 기록이다(루트가 `spec.syncPolicy`를 덮지 않는다 — `bootstrap/root-app.yaml` 머리 주석)
  - 수동 Sync: `kubectl -n argocd patch app <앱> --type merge -p '{"operation":{"sync":{"revision":"<커밋>"}}}'`
- `platform/`(cert-manager · coredns · ingress-nginx · metallb · harbor · jenkins · argocd ingress)은 **ArgoCD 밖**이다 — push해도 바뀌지 않는다. helm · kubectl로 사람이(또는 지시받은 세션이) 손으로 넣는다
- **`cluster/`와 호스트 `~/k8s-cluster/`** — 2026-11-11 직접 본 것:
  - `~/k8s-cluster/`(git 아님): `Vagrantfile` · `setup-node.sh` · `.vagrant/`(VM 다섯 대의 상태 · SSH 키 — `machines/m-k8s` · `w1-k8s` ~ `w4-k8s`) · `backup/`(작업 날짜별 폴더 33개, 195M — 덤프 · 되돌리기 · 매니페스트 스냅숏, 호스트용 kubectl 래퍼 `backup/2026-10-15-before-metallb/mk`). 실제로 `vagrant`가 도는 자리
  - `cluster/`(git): `Vagrantfile` · `setup-node.sh` · `label-nodes.sh`(노드 역할 라벨 — 저장소에만 있다). 기록 · 검토용
  - 겹치는 둘(`Vagrantfile` · `setup-node.sh`)은 **링크가 아니라 따로 복사한 파일**이고(서로 다른 inode) 지금 내용이 같다(`cmp`). `Vagrantfile`은 `setup-node.sh`를 부르지 않는다 — 노드 설치는 `cat setup-node.sh | vagrant ssh <노드> -- 'bash -s'`로 사람이 넣는다(`docs/01_cluster.md`)
  - **어디로 가나**: VM 만들기 · 끄기 · `vagrant ssh`는 `~/k8s-cluster`에서(`.vagrant/` 상태가 거기에만 있다 — `cluster/`에서 `vagrant up`을 치면 기존 VM을 모르고 새로 만들려 한다). 설정을 바꾸면 **양쪽을 같이 고치고** `cluster/`를 커밋한다. 백업 · 덤프는 `~/k8s-cluster/backup/<날짜>-<일>/`(git에 올리지 않는다)
- `main`에는 다른 쓰는 이가 있다: Jenkins(`Jenkins runshoes-app` · `Jenkins petmint-app`)가 이미지 태그를 커밋하고, 다른 세션도 문서를 커밋한다

## 2. 일하는 방식

- **클러스터를 만지는 일(kubectl · helm · vagrant · Sync)은 원본 폴더 `~/ronanlab-infra`의 `main`에서 한 번에 한 세션만 한다.** worktree나 다른 브랜치는 ArgoCD가 보지 않아 클러스터에서 확인할 수 없다. 파일만 고치는 일(문서 · 매니페스트 초안)은 worktree에서 한다 — 나누기와 까닭은 8절
- 지워도 되는 것은 시험용으로 자기가 만든 것뿐이다. 지우기 · 덮어쓰기 전에 대상을 먼저 본다
- 커밋 전 `git status` — 남이 고친 것(커밋 안 된 변경)은 건드리지 않고 **자기 파일만 `git add`**. push 전에 `git pull --rebase`(Jenkins 태그 커밋과 엇갈린다)
- **push는 관리자가 한다. 세션은 커밋까지만 한다**(2026-11-11 사용자 지시). 자동 Sync 앱은 push가 곧 배포라는 것을 관리자가 알고 push한다
- 클러스터는 호스트에 kubectl이 없다 — `cd ~/k8s-cluster && vagrant ssh m-k8s -c '…'`로 m-k8s에서 kubectl을 친다
- 단계마다 확인한다. **확인에 실패하면 되돌리고 멈춰서 보고한다**
- 맡은 범위 밖이 막히면 혼자 우회하지 말고 멈추고 알린다(2026-11-11 FOREMAN 297이 막혔다고 알리는 대신 링크를 직접 만들어 우회한 일이 있었다)
- 서비스가 끊기는 단계(재시작 · 노드 정비 등) 직전에는 사용자에게 알린다
- `apps/cloudflared/configmap.yaml`을 바꾸면 Sync만으로는 반영되지 않는다 — `rollout restart`까지(그 README)

## 3. 사람 승인이 필요한 것

되돌릴 수 없거나 운영이 끊기는 것은 하지 않고 사용자에게 묻는다:
- 운영 DB `DROP` · 데이터 지우기, PVC · PV · 네임스페이스 삭제, `vagrant destroy`
- 서버 · VM 재부팅 · 끄기(`vagrant halt`, `virsh` 메모리 바꾸기 포함)
- `sudo`가 필요한 호스트 명령 — 직접 치지 않고 사용자에게 한 줄로 알린다(예: `scripts/host-*.sh`)
- Cloudflare(터널 DNS · Access) 바꾸기 — 대시보드는 사람이 한다

## 4. 비밀값

- `.env*` · kubeconfig · 토큰 · DB 암호를 화면 · 로그 · 커밋에 내지 않는다. 저장소에는 Secret이 없다 — 사람이 `kubectl create secret`으로 만든다(각 README 「처음 한 번」)
- 비밀값이 든 파일은 Edit · Write로 고치지 않는다. 값이 있는지는 개수로만 센다(`/usr/bin/grep -cF`)
- 값을 셀 때는 `/usr/bin/grep`을 쓴다 — 셸의 `grep`은 CC 실행 파일에 기대는 함수라 CC가 스스로 업데이트하는 순간 실패한다. 개수가 0으로 보여도 못 센 것일 수 있다(2026-11-11 FOREMAN에서 실제로 겪음)
- Loki에는 서버 로그만 넣는다 — 대화 기록(질문 · 답 원문)은 넣지 않는다(`apps/monitoring/alloy/alloy.yaml`이 버린다)

## 5. 문서 자리

- `docs/README.md` — 인프라 문서 원본(노션 「쿠버네티스 설치」와 다르면 이쪽이 맞다). `00_server.md` ~ `09_monitoring.md`(차례는 README 표, 2026-11-12 노션에서 옮김) · `TODO.md`(남은 일, 끝나면 줄을 지운다)
- `docs/runbooks/` — 절차(지금 `mysql-replica.md`). 앱 절차는 `apps/runshoes/runbooks/`
- 앱별 운영 문서는 `apps/<앱>/README.md`, 모니터링은 `apps/monitoring/README.md`
- 바꾼 것은 그 자리 문서에 날짜와 함께 적는다

## 6. 커밋 메시지

꼴: `타입: 설명`

| 타입 | 쓰는 곳 |
| --- | --- |
| feat | 새 기능 |
| fix | 버그 고침 |
| docs | 문서만 |
| refactor | 동작은 그대로, 구조만 바꿈 |
| perf | 빠르게 만든 것 |
| test | 시험 추가 · 고침 |
| ops | 인프라 · 배포 · 모니터링 · 백업 · 복구(이 저장소에서 주로 쓴다) |
| build | 빌드 · 의존성 |
| ci | CI 설정 |
| chore | 나머지 잡일 |
| revert | 되돌리기 |

설명
- 한글로 쓴다
- 한 줄 50자 안
- 마침표로 끝내지 않는다
- 한 줄에 안 들어가면 커밋을 나눈다. 메시지가 길다는 것은 커밋이 크다는 뜻이다
- 더 쓸 말이 있으면 한 줄 비우고 본문에 까닭을 쓴다. 무엇을 했는지는 diff가 말해주니 본문에는 왜 그렇게 했는지를 쓴다

범위(scope)는 지금 쓰지 않는다. Jenkins가 만드는 이미지 태그 커밋(`<앱>: 이미지 태그 <해시>`)은 기계가 쓰는 것이라 이 꼴을 따르지 않는다

## 7. 공통 규칙

- 항상 한국어로 답하고 쓴다
- 파일은 Edit · Write로 고친다 — `sed -i` · `perl -i` · heredoc 덧붙이기(`cat >> f <<EOF`) · `tee`를 저장소 파일을 고치는 데 쓰지 않는다. 읽기만 하는 것(`sed -n` · `grep` 등)은 괜찮다. 임시 파일은 세션 스크래치에
- 다른 저장소(foreman · runshoes · petmint-rag-chatbot)는 읽기만 한다. 그쪽 일은 그 프로젝트 관리자에게 부탁한다(아래)

## 8. 관리자

- 이 저장소 관리자는 원본 폴더에서 도는 역할 manager 세션 하나다
- 일 나누기(2026-11-11 사용자 결정):
  - **파일만 고치는 일**(문서 · 매니페스트 초안): worktree에서 일하고 커밋만 한다. 관리자가 합치고 push한다
  - **클러스터를 만지는 일**(kubectl · helm · vagrant · Sync): 원본 폴더 `main`에서 한 번에 한 세션만 한다
  - 까닭: 클러스터는 하나라 worktree로 갈라도 갈라지지 않는다. 같은 앱을 둘이 동시에 patch하거나, `helm upgrade --reuse-values`로 앞의 값을 덮거나, 노드를 비우면 남의 작업도 끊긴다. 이 저장소는 확인과 되돌리기가 클러스터에서 일어나므로, 그 일을 worktree로 쪼개면 고치고 확인하고 되돌리는 고리가 끊긴다
- FOREMAN API는 이 프로젝트 토큰으로만 부른다:
  `T=$(sed -n 's/^FOREMAN_TOKEN_RONANLAB_INFRA=//p' ~/AI_programming/foreman/.env.project_tokens)` — 셸 변수로만 쓰고 값은 화면 · 로그 · 커밋에 내지 않는다. 이 토큰은 이 프로젝트 세션 · 방 API만 연다
  - 토큰 파일: `~/AI_programming/foreman/.env.project_tokens` 있음(2026-11-11 확인 — 권한 600, 소유 kopo17, `FOREMAN_TOKEN_RONANLAB_INFRA=` 줄 1개)
  - 싣는 법: `-H "Authorization: Bearer $T"`
- 다른 프로젝트에 부탁할 일: `curl -s -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"text": "…"}' http://127.0.0.1:8000/api/managers/<프로젝트>/ask`. 관리자가 없으면 사람에게 텔레그램으로 간다
- 교장이 넘긴 계획(입력 칸에 「[교장 계획 #N …]」)은 고칠 것이 없으면 적힌 명령(`/api/foreman/start` `{"dispatch_id": N, "use_saved": true}`)으로 띄운다. 틀렸으면 띄우지 말고 사람에게 묻는다

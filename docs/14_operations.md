<!--
다루는 곳: CLAUDE.md, .foreman/notion.toml, .foreman/docs.toml, .gitignore, scripts/docs-check.py, scripts/docs_for_code.py, scripts/foreman_tool.py
읽은 커밋: cab7ace
-->
# 운영 규칙과 문서 게시

저장소를 고치는 규칙(누가, 어디서, 어떤 차례로)과 문서를 노션에 게시하는 구조를 적는다. 세션이 읽는 규칙 원문은 `CLAUDE.md`다.

## 지금 구성

### main이 곧 운영

- 루트 Application이 `main`의 `apps/*/app.yaml`을 읽어 앱 Application을 만들고, 각 앱도 `targetRevision: main`을 본다 [code:CLAUDE.md:9] [code:bootstrap/root-app.yaml:22-28]
- 자동 Sync: runshoes, petmint, monitoring, harbor-backup. 수동: cloudflared [docs:history/cluster_state_20261116.md:54-61]
- 자동 Sync 앱은 push하면 3분 안에 클러스터에 들어간다 [code:CLAUDE.md:10] [code:bootstrap/root-app.yaml:3]
- 자동 Sync 켜고 끄기의 실제 스위치는 클러스터의 `kubectl patch`다. `app.yaml`의 `syncPolicy`는 기록이다(루트가 `/spec/syncPolicy`를 무시) [code:CLAUDE.md:11] [code:bootstrap/root-app.yaml:8-10] [code:bootstrap/root-app.yaml:33-43]
- `platform/`은 ArgoCD 밖이다. push해도 바뀌지 않고 helm, kubectl로 손으로 넣는다 [code:CLAUDE.md:13]
- `main`에 Jenkins(`Jenkins runshoes-app`, `Jenkins petmint-app`)가 이미지 태그를 커밋한다 [code:CLAUDE.md:19]

### 역할과 일 나누기

- 관리자: 원본 폴더 `~/ronanlab-infra`에서 도는 manager 세션 하나. 합치기와 push를 한다 [code:CLAUDE.md:99-101]
- 파일만 고치는 일(문서, 매니페스트 초안): worktree에서 커밋까지만 [code:CLAUDE.md:101]
- 클러스터를 만지는 일(kubectl, helm, vagrant, Sync): 원본 폴더 `main`에서 한 번에 한 세션만 [code:CLAUDE.md:23] [code:CLAUDE.md:102-103]
- push는 관리자만 한다. 자동 Sync 앱은 push가 곧 배포다 [code:CLAUDE.md:26]
- 다른 저장소(foreman, runshoes, petmint-rag-chatbot)는 읽기만 한다 [code:CLAUDE.md:95]

### 사람 승인이 필요한 것

- 운영 DB `DROP`, 데이터 지우기, PVC, PV, 네임스페이스 삭제, `vagrant destroy` [code:CLAUDE.md:40]
- 서버, VM 재부팅과 끄기(`vagrant halt`, `virsh` 메모리 바꾸기 포함) [code:CLAUDE.md:41]
- `sudo`가 필요한 호스트 명령(예: `scripts/host-*.sh`) [code:CLAUDE.md:42]
- Cloudflare 터널 DNS와 Access 바꾸기 [code:CLAUDE.md:43]
- 호스트 Ollama의 `OLLAMA_KEEP_ALIVE`는 바꾸지 않는다 [code:CLAUDE.md:34]

### 비밀값

- 저장소에 Secret이 없다. 각 `apps/<앱>/scripts/create-secrets.sh` 또는 README 「처음 한 번」의 `kubectl create secret`으로 사람이 만든다 [code:CLAUDE.md:47]
- 비밀값 파일은 Edit, Write로 고치지 않고 값은 `/usr/bin/grep -cF`로 개수만 센다 [code:CLAUDE.md:48-49]
- Loki에는 서버 로그만 넣는다. 대화 원문은 `apps/monitoring/alloy/alloy.yaml`이 버린다 [code:CLAUDE.md:50]
- `.gitignore`가 막는 꼴 [code:.gitignore:1-6]

| 꼴 | 뜻 |
| --- | --- |
| `*credentials*.json` | 터널 자격증명 등 |
| `*secret*.yaml` | Secret 매니페스트 |
| `secrets/` | 비밀값 폴더 |
| `*.key`, `*.pem` | 키, 인증서 |

### 커밋 메시지

- 꼴 `타입: 설명`. 타입은 feat, fix, docs, refactor, perf, test, ops, build, ci, chore, revert. 이 저장소는 주로 ops [code:CLAUDE.md:61-75]
- 설명은 한글, 한 줄 50자 안, 마침표 없음. 본문에는 까닭 [code:CLAUDE.md:77-82]
- em dash와 가운뎃점 금지, 줄임말과 번호 코드는 풀어 쓴다 [code:CLAUDE.md:84-87]
- scope는 쓰지 않는다. Jenkins 태그 커밋은 이 꼴 밖이다 [code:CLAUDE.md:89]

### 문서 두 벌

| 벌 | 자리 | 독자 | 게시 |
| --- | --- | --- | --- |
| 원고 | `notion/` | 비개발자까지 | 노션에 올린다 |
| 개발자 문서 | `docs/NN_*.md` | 운영하는 사람 | 올리지 않는다 |

- 두 벌은 같은 번호와 편 나눔을 쓴다 [docs:style_guide.md:3] [docs:style_guide.md:41]
- 개발자 문서는 노션에 올리지 않는다 [code:.foreman/notion.toml:14]
- 모든 편 맨 위에 「다루는 곳」과 「읽은 커밋」 머리 주석. 다루는 곳은 그 편이 덮는 파일(덮기 점검만 읽는다), 읽은 커밋은 편마다 [docs:style_guide.md:45-59]
- 줄 번호만 밀렸으면 읽은 커밋을 올리지 않는다. 읽은 커밋은 그 편을 열어 확인한 커밋 [docs:style_guide.md:61]
- 근거 표시는 세 종류(code 뒤에 저장소 경로와 줄, docs 뒤에 docs 아래 경로와 줄, c 뒤에 커밋)를 대괄호로 단다. 줄 번호는 그 편의 읽은 커밋 기준 [docs:style_guide.md:63-71]
- 원고 금지어: IP 주소, 도메인, 홈 경로, 토큰 꼴, 포트 번호 [docs:style_guide.md:91]

### 점검과 거꾸로 찾기: FOREMAN 문서 도구의 껍데기

- `scripts/docs-check.py`, `scripts/docs_for_code.py`는 FOREMAN `tools/docs.py`의 `check`, `refs`를 부르는 껍데기다. 규칙은 FOREMAN에 있다 [code:scripts/docs-check.py:2] [code:scripts/docs-check.py:6] [code:scripts/docs_for_code.py:2] [docs:style_guide.md:150]
- FOREMAN 폴더: 환경 변수 `FOREMAN_DIR`가 먼저, 없으면 `scripts/foreman_tool.py`의 `DEFAULT`. 둘 다 못 찾으면 한 줄 안내와 종료 코드 2 [code:scripts/foreman_tool.py:3-6] [code:scripts/foreman_tool.py:12]
- 이 저장소만의 값은 `.foreman/docs.toml`(아래 「설정 자리」) [code:.foreman/docs.toml:1]
- 점검: 틀린 것이 있으면 종료 코드 1, `-v`는 숫자나 인용이 있는데 근거 표시가 없는 줄을 「의심」으로 더 보인다 [code:scripts/docs-check.py:4] [code:scripts/docs-check.py:7] [docs:style_guide.md:145]
- 점검 묶음은 notion, portfolio, docs. 덮기는 notion 원고의 다루는 곳으로 본다. 포트폴리오 도메인은 ronanlab.dev만 [code:.foreman/docs.toml:10] [code:.foreman/docs.toml:20] [code:.foreman/docs.toml:4]
- 거꾸로 찾기: 코드를 고치는 세션은 그 코드를 가리키는 문서도 같은 브랜치에서 고친다. 고칠 수 없으면 무엇이 걸리는지 보고한다 [code:CLAUDE.md:35]
- 거꾸로 찾기 인자는 옛 스크립트와 같다(파일, `--range`, `--rev`, `--unfixed`, `--brief`, `--json`). 머리 주석의 다루는 곳은 읽지 않고 근거 표시만 읽는다 [code:scripts/docs_for_code.py:6-7]
- `docs/history/`는 기록이라 문서로도 코드로도 보지 않는다. `docs/NN_*.md`가 바뀌면 같은 번호 `notion/NN*`도 걸린다 [code:.foreman/docs.toml:2-3]
- `--self-test`는 FOREMAN 시험으로 옮겼다. 껍데기에서 부르면 종료 코드 2 [code:scripts/docs_for_code.py:16-18]

### 노션 게시

- FOREMAN Notion 게시기가 `.foreman/notion.toml`을 읽는다. origin/main에 push된 판만, 5분마다 다시 읽는다. 깨진 파일이면 옛 설정을 쓰고 알림을 보낸다 [code:.foreman/notion.toml:3-4]
- 저장소 몫 칸: docs, src, quiet_min, skip, create, archive, title, order, header, headings [code:.foreman/notion.toml:6-7]
- FOREMAN 몫 칸(root, docs_page, portfolio_page, github, ref)과 Notion 토큰은 FOREMAN `config/notion.toml [ronanlab-infra]`에 있다. 저장소 파일에 적으면 쓰지 않고 경고 [code:.foreman/notion.toml:8-9]
- `notion/`의 폴더 나무가 노션 [기술문서] 아래 페이지 나무가 된다. 옛 「쿠버네티스 설치」 01~09 페이지는 게시 대상에서만 빠져 있다 [code:.foreman/notion.toml:12-13]

## 설정 자리

| 파일:줄 | 값 | 뜻 |
| --- | --- | --- |
| `.foreman/notion.toml:16` | `docs = "manual"` | 게시 차례를 손으로 정한다 [code:.foreman/notion.toml:16] |
| `.foreman/notion.toml:17` | `src = "notion/"` | 원고 폴더. 머리 주석, 근거 표시, 저장소 링크를 떼고 올린다 [code:.foreman/notion.toml:17] |
| `.foreman/notion.toml:18` | `quiet_min = 30` | 값만 확인했다. 뜻은 파일에 적혀 있지 않다 [code:.foreman/notion.toml:18] |
| `.foreman/notion.toml:19` | `create = true` | 짝 없는 원고는 새 페이지로 만든다 [code:.foreman/notion.toml:19] |
| `.foreman/notion.toml:20` | `archive = false` | 원본이 사라져도 페이지를 휴지통으로 보내지 않는다 [code:.foreman/notion.toml:20] |
| `.foreman/notion.toml:21` | `headings = "md"` | 값만 확인했다 [code:.foreman/notion.toml:21] |
| `.foreman/notion.toml:22` | `title = "h1"` | 페이지 제목은 원고의 첫 `# ` 줄 [code:.foreman/notion.toml:22] |
| `.foreman/notion.toml:23` | `header = "footer"` | 맨 아래 갱신 줄에 읽은 커밋을 적는다 [code:.foreman/notion.toml:23] |
| `.foreman/docs.toml:2` | `records = ["docs/history/"]` | 기록 폴더. 문서로도 코드로도 보지 않는다 [code:.foreman/docs.toml:2] |
| `.foreman/docs.toml:3` | `pair_numbers = true` | 개발자 문서가 바뀌면 같은 번호 원고도 건다 [code:.foreman/docs.toml:3] |
| `.foreman/docs.toml:4` | `allowed_domains` | 포트폴리오에 쓸 수 있는 도메인 [code:.foreman/docs.toml:4] |
| `.foreman/docs.toml:16` | `files_at = "read"` | 근거 파일과 줄을 그 편의 읽은 커밋 판에서 본다 [code:.foreman/docs.toml:16] |
| `.foreman/docs.toml:19` | `banned` | 금지어를 보는 묶음(notion, portfolio). 개발자 문서는 사설 주소를 숫자로 적는다 [code:.foreman/docs.toml:19] |
| `.foreman/docs.toml:20` | `cover_by` | 덮기를 보는 묶음(notion) [code:.foreman/docs.toml:20] |
| `scripts/foreman_tool.py:12` | `DEFAULT` | `FOREMAN_DIR`가 없을 때 쓰는 FOREMAN 폴더 [code:scripts/foreman_tool.py:12] |
| `.gitignore:1-6` | 자격증명 꼴 | 위 「비밀값」 표 [code:.gitignore:1-6] |

`skip`과 `order`는 지금 파일에 없다 [code:.foreman/notion.toml:16-23]

## 바꾸거나 다시 만들기

- 커밋 전 `git status`, 자기 파일만 `git add`. push 전 `git pull --rebase`(Jenkins 태그 커밋과 엇갈린다) [code:CLAUDE.md:25]
- 수동 Sync(cloudflared 등) [code:CLAUDE.md:12]

```
cd ~/k8s-cluster && vagrant ssh m-k8s -c "kubectl -n argocd patch app <앱> --type merge -p '{\"operation\":{\"sync\":{\"revision\":\"<커밋>\"}}}'"
```

- `apps/cloudflared/configmap.yaml`을 바꾸면 Sync 뒤 `rollout restart`까지 한다 [code:CLAUDE.md:31]
- 노션 게시가 사람이 고친 블록 때문에 멈추면 force를 쓰지 않고 사람에게 알린 뒤 원인을 고친다 [code:CLAUDE.md:32]
- 게시 설정을 바꾸려면 `.foreman/notion.toml`을 고쳐 커밋하고 관리자가 push한다. 게시기는 push된 판만 읽는다 [code:.foreman/notion.toml:3]

## 확인

```
python3 scripts/docs-check.py        # 틀린 것 0, 종료 코드 0
python3 scripts/docs-check.py -v     # 의심 줄까지
python3 scripts/docs_for_code.py --range main...HEAD --unfixed   # 이 브랜치가 바꾼 코드로 걸리는데 안 고친 문서
git status                           # 자기 파일만 바뀌었는지
```

- 점검 명령과 기대: [docs:style_guide.md:6] [code:scripts/docs-check.py:4] [docs:style_guide.md:144-147] [code:scripts/docs_for_code.py:4]
- FOREMAN을 못 찾으면 종료 코드 2와 「FOREMAN_DIR를 주거나 기본 경로를 맞추라」는 안내가 나온다 [code:scripts/foreman_tool.py:6]

## 알려진 한계

- 점검은 근거의 파일과 줄 범위가 있는지만 본다. 줄이 사실과 맞는지는 사람이 연다 [docs:style_guide.md:71]
- 점검과 거꾸로 찾기는 FOREMAN이 있어야 돈다. 규칙을 고칠 일은 FOREMAN 관리자에게 부탁한다 [docs:style_guide.md:150]
- 자동 Sync의 실제 스위치가 클러스터에 있어 `app.yaml`만으로 지금 Sync 방식을 단정할 수 없다 [code:CLAUDE.md:11]

# Cloudflare Tunnel 세팅 (vcluster 시절)

지금 클러스터가 아니라 2026-09~10 학교 vcluster(vc-kopo17) 시절 기록이다.
RUNSHOES가 학교 vcluster에 있을 때 runshoes-tunnel로 사이트를 학교 밖에 내고, ollama-tunnel로 서버의 Ollama를 부르던 구성과 그때 겪은 일을 남긴다.
지금 터널 구성은 [../03_cloudflare_tunnel.md](../03_cloudflare_tunnel.md)를 본다.

- 날짜: 2026-09-22 구축, 2026-10-18 RUNSHOES 이주로 끝남(runshoes-tunnel은 2026-11-12 `cloudflared tunnel list`에 없다)
- 범위: runshoes-tunnel → vcluster traefik, 앱 코드 환경변수 · 인증 헤더, 사이드카 챗봇, gitops 레포 매니페스트, kaniko Jenkinsfile, 그때의 트러블슈팅. 도메인 구매 · cloudflared 설치 · ollama-tunnel · Access Service Token · `route dns` 함정 · https/noTLSVerify/httpHostHeader · Host 헤더 403 · Secret 이야기는 지금도 사실이라 [../03_cloudflare_tunnel.md](../03_cloudflare_tunnel.md)로 옮겼다
- 코드: 이 저장소에 없다. 그때 매니페스트는 학교 GitLab `std-gitlab.kopoctc.kr/kopo17/gitops`의 `apps/runshoes/`, 앱 코드는 runshoes 저장소. 지금 런슈즈 배포 문서는 런슈즈 저장소 `~/AI_programming/runshoes/docs/06_deployment.md`

## 1. 지금 구성

해당 없음(옛 환경, 지금은 [03_cloudflare_tunnel.md](../03_cloudflare_tunnel.md)).

## 2. 왜 이렇게 했나

### 전체 아키텍처

RUNSHOES는 학교 vcluster(vc-kopo17) 안에 떠 있고, 리뷰 요약 · 챗봇 기능은 학교 GPU 서버의 Ollama를 쓴다. 둘은 물리적으로 같은 학교 안에 있어도 **서로 다른 사설 네트워크**라 직접 통신이 안 된다.

```txt
[학교 GPU 서버]                    [학교 vcluster (vc-kopo17)]
- 사설 IP: 192.168.0.17             - runshoes pod (Node.js + Python 챗봇)
- 공유기 뒤(192.168.23.18)          - traefik Ingress (192.168.26.195)
- Ollama 실행 중 (localhost:11434)  - kopo17-runshoes.std.kopoctc.kr (학교 내부망 전용)
```

해결: Cloudflare Tunnel(가입 필요).

- 개인 도메인 `ronanlab.dev` 구매(Cloudflare Registrar, $12.20/년)
- GPU 서버에 `cloudflared` 설치 → 아웃바운드 연결만으로 터널을 뚫는다(포트포워딩 · 공인 IP 불필요)
- 터널 2개:
  - `ollama-tunnel`: `ollama.ronanlab.dev` → GPU 서버 Ollama(11434)
  - `runshoes-tunnel`: `runshoes.ronanlab.dev` → vcluster traefik → runshoes 사이트(학교 외부망 접속용)

최종 그림:

```txt
브라우저(HTTPS)
   │
   ├─→ https://kopo17-runshoes.std.kopoctc.kr  (학교 내부망 전용, 기존)
   │
   └─→ https://runshoes.ronanlab.dev  (Cloudflare, 외부망 접속용, 신규)
              │
              ▼
        [Cloudflare 엣지]
              │ runshoes-tunnel (systemd, GPU 서버에서 상시 실행)
              ▼
        [traefik Ingress, vcluster] ── path 기반 라우팅
              ├─ /ws/chat → Service(ws:8766) → chatbot 컨테이너 (Python, websockets)
              └─ /        → Service(http:80) → runshoes 컨테이너 (Node.js, Express)
                                                      │
                                                      │ fetch(OLLAMA_URL) + CF Access Service Token 헤더
                                                      ▼
                                          https://ollama.ronanlab.dev
                                                      │
                                        [Cloudflare Access, Service Token 검증]
                                                      │
                                              [Cloudflare 엣지]
                                                      │ ollama-tunnel (systemd, GPU 서버)
                                                      ▼
                                          GPU 서버 Ollama (localhost:11434)
```

> **가용성 조건**: GPU 서버와 vcluster 둘 다 살아 있어야 정상 작동한다. 서로 독립적인 장애 지점이라, 한쪽만 죽어도 전체 서비스에 영향을 준다.

### 리뷰 요약이 안 되던 까닭 (원인 분석)

증상: `{"summary":null,"reason":"요약을 불러오지 못했습니다"}`

1. `server.cjs`의 `OLLAMA_URL = "http://localhost:5012"`가 눈에 띄었다. 이건 **로컬 PC에서 PuTTY로 GPU 서버에 SSH 터널링했을 때만 유효한 주소**였다. "이 서버 자체에서 Ollama를 부를 수 있으면 이대로, 아니면 PuTTY 터널 포트로 변경"이라는 원래 주석 그대로, 배포 환경에서는 의미 없는 주소였다.
2. "같은 학교 네트워크인데 왜 안 되지?" → vcluster pod의 오버레이 네트워크(`10.42.x.x`)와 GPU 서버의 사설망(`192.168.0.x`)은 같은 건물에 있어도 **완전히 분리된 대역**이다. GPU 서버는 자체 공유기(`192.168.23.18`) 뒤에 있고, 그 공유기에는 SSH(포트 5001)만 포트포워딩되어 있어 Ollama 포트는 애초에 밖에 나가지 않는다.
3. "vcluster pod를 ClusterIP로 하면 되지 않냐" → ClusterIP는 클러스터 **내부** 서비스 디스커버리용이지, 클러스터 밖의 임의 사설 IP를 끌어오는 메커니즘이 아니다. 방향 자체가 틀렸다.

### 검토한 대안과 기각 이유

- **GPU 서버 공유기에 포트포워딩 직접 열기** → 유동 공인 IP(ISP가 다시 할당하면 다시 설정), 포트를 인증 없이 인터넷에 그대로 내는 보안 위험
- **Ollama도 Gemini API로 통일** → 리뷰 요약은 예전에 이 방향으로 바꾼 전례가 있었다(vcluster 사설망 문제로). 이번엔 GPU 서버에서 직접 LoRA 학습한 커스텀 모델을 프로젝트에 붙이고 싶다는 목표가 있어 기각
- **Cloudflare Tunnel → 채택.** 아웃바운드 연결만으로 뚫리므로 유동 IP · 포트포워딩 문제가 없다

### GPU 서버에 사이트 터널을 얹는 것

GPU 서버(LoRA 실습 목적)에 runshoes 사이트 노출용 터널까지 얹는 것은 정리정돈 관점에서 최선은 아니었다. 안전성 문제는 아니고 역할 분리라는 설계 취향의 문제다(공유 서버에 영향이 없는 까닭은 03 「Cloudflare와 Cloudflare Tunnel」).

## 3. 진행 기록

도메인 구매, cloudflared 설치 · 로그인, ollama-tunnel, Access + Service Token 발급 절차는 [../03_cloudflare_tunnel.md](../03_cloudflare_tunnel.md) 「진행 기록」에 있다. 여기는 그 나머지다.

### 4단계: runshoes-tunnel 세팅 (2026-09-22)

```bash
# 터널 생성 (반드시 새 세션에서, 기존 ollama-tunnel 실행 창은 그대로 둔다)
cloudflared tunnel create runshoes-tunnel
cloudflared tunnel route dns runshoes-tunnel runshoes.ronanlab.dev
```

`route dns` 뒤 CNAME이 엉뚱한 터널을 가리키면 대시보드에서 Target을 `<runshoes-tunnel의 UUID>.cfargotunnel.com`으로 고친다(아래 트러블슈팅, 원인은 03 9-2단계).

설정 파일(`~/.cloudflared-runshoes/config.yml`):

```bash
mkdir -p ~/.cloudflared-runshoes
cat > ~/.cloudflared-runshoes/config.yml << 'EOF'
tunnel: runshoes-tunnel
credentials-file: /home/kopo17/.cloudflared/<runshoes-tunnel의 터널ID>.json
ingress:
  - hostname: runshoes.ronanlab.dev
    service: https://192.168.26.195:443
    originRequest:
      httpHostHeader: kopo17-runshoes.std.kopoctc.kr
      noTLSVerify: true
  - service: http_status:404
EOF
```

- `service`: vcluster traefik Ingress의 LoadBalancer IP(`192.168.26.195`)를 **HTTPS(443)**로(HTTP로 하면 traefik이 301을 건다)
- `originRequest.httpHostHeader`: traefik은 Host 헤더로 라우팅하므로 cloudflared가 원점에 학교 도메인(`kopo17-runshoes.std.kopoctc.kr`)을 넣게 한다. 사용자는 `https://runshoes.ronanlab.dev`로만 접속하면 된다
- `noTLSVerify: true`: traefik 내부 인증서 검증 생략(Cloudflare Tunnel 자체가 암호화된 통로)

세 설정의 까닭은 03 「원점 설정 세 가지」.

테스트 실행 · 검증:

```bash
cloudflared tunnel --config ~/.cloudflared-runshoes/config.yml run runshoes-tunnel
```

다른 세션에서:

```bash
curl -v https://runshoes.ronanlab.dev/
```

`HTTP/2 200`과 `<title>RUNSHOES</title>`가 보이면 성공.

#### 트러블슈팅: 잘못된 터널로 DNS가 연결됨

**증상**: `cloudflared tunnel create runshoes-tunnel` 직후 `route dns` 로그에

```txt
Added CNAME runshoes.ronanlab.dev which will route to this tunnel tunnelID=81af3e6c-... (ollama-tunnel의 ID)
```

새로 만든 `runshoes-tunnel`(`3f8ecf07-...`)이 아니라 **기존 `ollama-tunnel`의 ID로 연결**됐다.

**원인**: 그때는 명령을 연속으로 붙여 실행하다 터미널 입력이 꼬인 것으로 추정했다. 2026-10-13 같은 일을 다시 겪고서야 `~/.cloudflared/config.yml`(`tunnel: ollama-tunnel`)을 기본으로 읽어서라는 것을 알았다(03 9-2단계).

**해결**: 시도한 것

1. `cloudflared tunnel route dns --overwrite-dns runshoes-tunnel runshoes.ronanlab.dev` → 여러 번 해도 계속 기존 터널 ID. `--overwrite-dns`가 기대대로 동작하지 않았다
2. 새 터미널 세션에서 다시 → 그래도 안 됐다
3. **Cloudflare 대시보드에서 DNS 레코드를 직접 수정**: `ronanlab.dev` → DNS → Records → `runshoes` CNAME의 Target을 `3f8ecf07-62fb-40a7-a9c4-07c1fb57fbe2.cfargotunnel.com`으로. 이것만 확실히 먹혔다

#### 트러블슈팅: Host 헤더를 바꿔 curl했다가 403, 그다음 301

**증상**: `curl -H "Host: kopo17-runshoes.std.kopoctc.kr" https://runshoes.ronanlab.dev/` → Cloudflare 엣지의 403. Host 헤더를 빼고 `curl https://runshoes.ronanlab.dev/` → `301 → https://kopo17-runshoes.std.kopoctc.kr/`.

**원인**: 403은 도메인 프런팅 차단(03 「원점 설정 세 가지」). 301은 config.yml의 origin을 `http://192.168.26.195:80`으로 지정했는데, traefik이 Ingress 설정(`router.tls: "true"`)에 따라 HTTP를 HTTPS로 강제 리다이렉트했기 때문이다.

**해결**: Host는 `httpHostHeader`로 cloudflared 안에서 바꾸고, `service`를 `https://192.168.26.195:443` + `noTLSVerify: true`로. 세 조각이 한 번에 안 맞아서 403 → 301 → 200 순서로 하나씩 벗겨 냈다.

### 4-1단계: 앱 코드에 Access 인증 헤더 추가 (2026-09-22)

Access 정책과 Service Token(그때 이름 `runshoes-ollama-token`) 발급은 03. 그때 이 엔드포인트를 부르는 것은 **우리 앱(server.cjs, chatbot_server.py)뿐**이라 서버 대 서버용 Service Token을 썼다.

**`server.cjs`**: `summaryHandler`의 fetch 호출에 헤더 추가

```javascript
const response = await fetch(`${OLLAMA_URL}/api/generate`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "CF-Access-Client-Id": process.env.CF_ACCESS_CLIENT_ID,
    "CF-Access-Client-Secret": process.env.CF_ACCESS_CLIENT_SECRET,
  },
  body: JSON.stringify({ model: "gemma4:e4b", prompt, stream: false }),
  signal: AbortSignal.timeout(40000),
});
```

**`chatbot_server.py`**: 상단에 환경변수 읽기, `ask_ollama`의 `requests.post`에 헤더 추가

```py
import os

CF_ACCESS_CLIENT_ID = os.environ.get("CF_ACCESS_CLIENT_ID", "")
CF_ACCESS_CLIENT_SECRET = os.environ.get("CF_ACCESS_CLIENT_SECRET", "")

# ... ask_ollama 함수 안:
response = requests.post(
    f"{OLLAMA_URL}/api/generate",
    json={...},
    headers={
        "CF-Access-Client-Id": CF_ACCESS_CLIENT_ID,
        "CF-Access-Client-Secret": CF_ACCESS_CLIENT_SECRET,
    },
    timeout=40,
)
```

**k8s Secret 생성 · 주입**: Client ID/Secret 값을 코드나 git에 노출하지 않으려고 k8s Secret으로 관리했다(Secret이 암호화가 아니라는 점은 03 「k8s Secret은 암호화가 아니다」).

```bash
kubectl create secret generic cf-access-credentials \
  -n runshoes \
  --from-literal=client-id='<Client ID>' \
  --from-literal=client-secret='<Client Secret>'
```

`deployment.yaml`의 두 컨테이너에 `secretKeyRef`로 연결했다(아래 7단계).

검증: 토큰 없이 `curl https://ollama.ronanlab.dev/api/tags`는 차단(로그인/거부 페이지), 앱을 통한 호출(리뷰 요약, 챗봇)은 사이트에서 직접 시험해 정상.

### 5단계: systemd 등록, runshoes-tunnel (2026-09-22)

ollama-tunnel 유닛은 03. runshoes-tunnel도 같이 등록했다.

```bash
sudo tee /etc/systemd/system/cloudflared-runshoes.service << 'EOF'
[Unit]
Description=Cloudflare Tunnel for Runshoes
After=network.target

[Service]
Type=simple
User=kopo17
ExecStart=/usr/bin/cloudflared tunnel --config /home/kopo17/.cloudflared-runshoes/config.yml run runshoes-tunnel
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable cloudflared-ollama.service cloudflared-runshoes.service
sudo systemctl start cloudflared-ollama.service cloudflared-runshoes.service

systemctl status cloudflared-ollama.service --no-pager
systemctl status cloudflared-runshoes.service --no-pager
```

두 서비스 다 `active (running)`이면 끝. 이 시점부터 터미널 창을 다 닫아도 터널은 유지됐다. (2026-11-12 호스트에 `cloudflared-runshoes` 유닛과 `~/.cloudflared-runshoes/`는 없다.)

### 6단계: 애플리케이션 코드, 환경변수 정리

**`server.cjs`**(리뷰 요약, Node.js)

```javascript
const OLLAMA_URL = process.env.OLLAMA_URL || "http://localhost:5012";
```

환경변수로 받는 구조라 코드 수정이 필요 없다. `CF_ACCESS_CLIENT_ID` · `CF_ACCESS_CLIENT_SECRET`은 4-1단계에서 반영했다.

**`chatbot_server.py`**(파이썬 챗봇)

```py
# 컨테이너 밖에서 접근 가능하도록 바인딩
host, port = "0.0.0.0", 8766  # "localhost" → "0.0.0.0"

# Ollama 주소를 Cloudflare Tunnel 주소로
OLLAMA_URL = "https://ollama.ronanlab.dev"  # 기존 PuTTY 터널 전용 주소에서 변경
```

**`src/api.ts`**(프론트, 웹소켓 URL): HTTPS 페이지에서는 웹소켓도 `wss://`여야 하므로 프로토콜을 동적으로 정한다.

```ts
const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";

export const CHATBOT_WS_URL = isDev
  ? "ws://localhost:8766"
  : `${wsProtocol}//${window.location.host}/ws/chat`;
```

### 7단계: k8s 매니페스트 (gitops 레포)

**`deployment.yaml`**: 사이드카 컨테이너 + 환경변수(Secret 포함, 최종본)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: runshoes
  namespace: runshoes
spec:
  replicas: 1
  strategy:
    type: Recreate
  selector:
    matchLabels:
      app: runshoes
  template:
    metadata:
      labels:
        app: runshoes
    spec:
      initContainers:
        - name: seed-db
          image: std-harbor.kopoctc.kr/kopo17/runshoes:v1
          command:
            - sh
            - -c
            - "[ -f /data/db.json ] || cp /app/db.json.seed /data/db.json"
          volumeMounts:
            - name: data
              mountPath: /data
      containers:
        - name: runshoes
          image: std-harbor.kopoctc.kr/kopo17/runshoes:v1
          ports:
            - name: http
              containerPort: 3000
          env:
            - name: PORT
              value: "3000"
            - name: DB_PATH
              value: /data/db.json
            - name: OLLAMA_URL
              value: https://ollama.ronanlab.dev
            - name: CF_ACCESS_CLIENT_ID
              valueFrom:
                secretKeyRef:
                  name: cf-access-credentials
                  key: client-id
            - name: CF_ACCESS_CLIENT_SECRET
              valueFrom:
                secretKeyRef:
                  name: cf-access-credentials
                  key: client-secret
          volumeMounts:
            - name: data
              mountPath: /data
          readinessProbe:
            httpGet:
              path: /api/shoes
              port: http
            initialDelaySeconds: 5
          livenessProbe:
            httpGet:
              path: /
              port: http
            initialDelaySeconds: 15
          resources:
            requests:
              cpu: 50m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 512Mi
        - name: chatbot
          image: std-harbor.kopoctc.kr/kopo17/runshoes-chatbot:v1
          ports:
            - name: ws
              containerPort: 8766
          env:
            - name: CF_ACCESS_CLIENT_ID
              valueFrom:
                secretKeyRef:
                  name: cf-access-credentials
                  key: client-id
            - name: CF_ACCESS_CLIENT_SECRET
              valueFrom:
                secretKeyRef:
                  name: cf-access-credentials
                  key: client-secret
          resources:
            requests:
              cpu: 50m
              memory: 128Mi
            limits:
              cpu: 300m
              memory: 256Mi
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: runshoes-data
```

**`service.yaml`**: 챗봇 포트 추가

```yaml
apiVersion: v1
kind: Service
metadata:
  name: runshoes
  namespace: runshoes
spec:
  type: ClusterIP
  selector:
    app: runshoes
  ports:
    - name: http
      port: 80
      targetPort: http
    - name: ws
      port: 8766
      targetPort: ws
```

**`ingress.yaml`**: `/ws/chat` 경로 라우팅(구체적인 경로를 위에)

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: runshoes
  namespace: runshoes
  annotations:
    traefik.ingress.kubernetes.io/router.entrypoints: web,websecure
    traefik.ingress.kubernetes.io/router.tls: "true"
spec:
  ingressClassName: traefik
  tls:
    - hosts: [kopo17-runshoes.std.kopoctc.kr]
  rules:
    - host: kopo17-runshoes.std.kopoctc.kr
      http:
        paths:
          - path: /ws/chat
            pathType: Prefix
            backend:
              service: {name: runshoes, port: {name: ws}}
          - path: /
            pathType: Prefix
            backend:
              service: {name: runshoes, port: {name: http}}
```

**`kustomization.yaml`**: 챗봇 이미지도 태그 관리 대상으로

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: runshoes
resources:
  - pvc.yaml
  - deployment.yaml
  - service.yaml
  - ingress.yaml
images:
  - name: std-harbor.kopoctc.kr/kopo17/runshoes
    newTag: "58"
  - name: std-harbor.kopoctc.kr/kopo17/runshoes-chatbot
    newTag: "58"
```

> `cf-access-credentials` Secret은 kustomization 리소스로 관리하지 않고 `kubectl create secret`으로 클러스터에 직접 만들었다. Secret 매니페스트를 git에 커밋하지 않기 위해서다.

### 8단계: CI/CD (Jenkinsfile), 챗봇 이미지 빌드 스테이지 추가

**`Dockerfile.chatbot`**(신규)

```docker
FROM python:3.12-alpine
WORKDIR /app

COPY chatbot_server.py .
RUN pip install --no-cache-dir websockets requests

EXPOSE 8766
CMD ["python", "chatbot_server.py"]
```

**`Jenkinsfile`**: kaniko 컨테이너를 이미지별로 나눴다. kaniko는 빌드할 때 자기 컨테이너의 파일시스템 자체를 조작하므로 **같은 kaniko 컨테이너로 이미지 두 개를 연속 빌드하면 안 된다**(아래 트러블슈팅). podTemplate에 각각 선언한다.

```groovy
pipeline {
  options {
    disableConcurrentBuilds()
  }

  agent {
    kubernetes {
      yaml """
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: kaniko
    image: gcr.io/kaniko-project/executor:debug
    command: ["/busybox/cat"]
    tty: true
    resources:
      requests:
        memory: "512Mi"
        cpu: "200m"
      limits:
        memory: "2Gi"
        cpu: "2"
    volumeMounts:
    - name: harbor-config
      mountPath: /kaniko/.docker
  - name: kaniko-chatbot
    image: gcr.io/kaniko-project/executor:debug
    command: ["/busybox/cat"]
    tty: true
    resources:
      requests:
        memory: "256Mi"
        cpu: "100m"
      limits:
        memory: "1Gi"
        cpu: "1"
    volumeMounts:
    - name: harbor-config
      mountPath: /kaniko/.docker
  - name: git
    image: alpine/git:latest
    command: ["cat"]
    tty: true
  volumes:
  - name: harbor-config
    secret:
      secretName: harbor-credentials
      items:
      - key: .dockerconfigjson
        path: config.json
"""
    }
  }

  environment {
    IMAGE = "std-harbor.kopoctc.kr/kopo17/runshoes"
    NS    = "runshoes"
    TAG   = "${BUILD_NUMBER}"
  }

  stages {
    stage('Build & Push') {
      steps {
        container('kaniko') {
          sh """
            /kaniko/executor \
              --context=dir://${WORKSPACE} \
              --dockerfile=${WORKSPACE}/Dockerfile \
              --snapshot-mode=redo \
              --single-snapshot \
              --destination=${IMAGE}:${BUILD_NUMBER} \
              --destination=${IMAGE}:latest
          """
        }
      }
    }

    stage('Build & Push Chatbot') {
      steps {
        container('kaniko-chatbot') {
          sh """
            /kaniko/executor \
              --context=dir://${WORKSPACE} \
              --dockerfile=${WORKSPACE}/Dockerfile.chatbot \
              --snapshot-mode=redo \
              --single-snapshot \
              --destination=${IMAGE}-chatbot:${BUILD_NUMBER} \
              --destination=${IMAGE}-chatbot:latest
          """
        }
      }
    }

    stage('Update GitOps Manifest') {
      steps {
        container('git') {
          withCredentials([usernamePassword(
            credentialsId: 'gitlab-token',
            usernameVariable: 'GIT_USER',
            passwordVariable: 'GIT_TOKEN'
          )]) {
            sh '''
              rm -rf gitops
              git clone https://oauth2:${GIT_TOKEN}@std-gitlab.kopoctc.kr/kopo17/gitops.git
              cd gitops/apps/runshoes
              sed -i "s|newTag:.*|newTag: \\"${TAG}\\"|" kustomization.yaml
              git config user.email "jenkins@kopo17"
              git config user.name "jenkins-ci"
              git add kustomization.yaml
              git commit -m "deploy: runshoes 이미지 :${TAG} [skip ci]"
              git push origin main
            '''
          }
        }
      }
    }
  }
}
```

(`${GIT_TOKEN}`은 Jenkins 자격증명 `gitlab-token`에서 실행 때 들어오는 변수 이름이다. 값은 여기 없다.)

> `student-quota`(CPU 리소스 할당량)에 걸리지 않도록 `requests`(quota 계산 기준)는 작게, `limits`(최대 허용치)는 여유 있게 잡는다.

### 9단계: 전체 배포 흐름 요약

```txt
1. 로컬/우분투 서버에서 코드 수정
2. git pp  → GitHub(origin) + GitLab(gitlab) 동시 push
3. GitLab webhook → Jenkins 트리거 (즉시)
4. Jenkins: Build & Push(runshoes) → Build & Push Chatbot(runshoes-chatbot)
   → Update GitOps Manifest (gitops 레포의 kustomization.yaml newTag 갱신 후 push)
5. ArgoCD가 gitops 레포 변경 감지 (기본 polling ~3분, webhook 미설정 시)
6. ArgoCD sync → k8s Deployment 갱신 → 새 pod 기동
```

`git pp` alias(`~/.gitconfig`, global):

```bash
git config --global alias.pp '!f() { echo "== GitHub push =="; git push origin main; echo "== GitLab push =="; git push gitlab main; }; f'
```

> 레포별 `.git/config`(local)에 같은 이름 alias가 있으면 global보다 먼저 적용되어 충돌한다. `git config --local --unset alias.pp`로 지워야 global이 동작한다. `gitops` 레포는 GitHub 미러가 없으므로 `git pp` 대신 `git push origin main`.

#### 트러블슈팅: curl → fetch 전환

**증상**: `OLLAMA_URL`을 정상 주소로 바꾼 뒤에도 `요약을 불러오지 못했습니다`가 계속 났다.

**원인**: pod 로그에

```txt
summary error: spawn curl ENOENT
```

Node Alpine 이미지에는 curl이 없었다. 로컬 개발 환경에만 있던 것을 당연하게 여겨 알아채는 데 시간이 걸렸다. pod 안에서 `curl`을 직접 실행해도 "not found".

**해결**: Dockerfile에 curl을 설치하는 길도 있었지만, Node 18+ 내장 `fetch`로 바꾸는 쪽이 간결해 코드를 고쳤다.

#### 트러블슈팅: kaniko가 두 번째 빌드에서 죽음

**증상**: `Build & Push Chatbot` 스테이지가 같은 `kaniko` 컨테이너를 다시 쓰도록 짰더니

```txt
[Pipeline] { (Build & Push Chatbot)
[Pipeline] sh
ERROR: Process exited immediately after creation.
```

첫 빌드(`Build & Push`)는 push까지 끝났는데, 바로 이은 두 번째 kaniko 실행에서 컨테이너 프로세스가 즉시 죽었다.

**원인**: kaniko는 이미지를 만들 때 **자기가 떠 있는 컨테이너의 파일시스템을 직접 조작**해 스냅숏을 뜬다. 첫 빌드가 끝나는 과정에서 컨테이너를 살려 두던 프로세스(`/busybox/cat`)나 관련 바이너리가 훼손된 것으로 추정한다. kaniko는 "한 컨테이너당 한 번의 빌드"를 상정한 도구다.

**해결**: podTemplate에 `kaniko-chatbot`이라는 별도 kaniko 컨테이너를 더해 이미지별로 독립된 컨테이너에서 빌드한다.

#### 트러블슈팅: student-quota 초과

**증상**: kaniko 컨테이너를 하나 더하자마자 파이프라인 pod가 계속 `Pending`.

```txt
exceeded quota: student-quota, requested: requests.cpu=950m, used: requests.cpu=770m, limited: requests.cpu=1500m
```

**원인**: 처음엔 "옛 pending pod가 안 지워져서인가?" 하고 좀비 pod를 찾아 헤맸다. 실제로는 새 pod 하나가 **정상적으로 스케줄링을 시도했다가 quota 때문에 거절**당하고 있었다(`kubectl get pods -n cicd`에 pending pod는 하나뿐).

**해결**: kaniko · kaniko-chatbot 두 컨테이너의 `requests`(quota 계산 기준)를 낮추고 `limits`는 넉넉히 둔다.

**추가로 겪은 것**: Abort · 삭제해도 같은 빌드 번호(`#54`, `#56`)의 pod가 다시 생겼다. `disableConcurrentBuilds()`와 Jenkins가 "빌드가 아직 안 끝났다"고 보고 executor pod를 계속 새로 만드는 탓이다. pod만 지워서는 안 되고 **Jenkins 웹 UI에서 빌드 자체를 Abort**해야 정리된다.

#### 트러블슈팅: 챗봇 코드 들여쓰기 에러

**증상**: pod가 `CrashLoopBackOff`. `kubectl logs -n runshoes <pod> -c chatbot --previous`:

```txt
File "/app/chatbot_server.py", line 109
    async with websockets.serve(handler, host, port):
IndentationError: unexpected indent
```

**원인**: `host, port = "0.0.0.0", 8766`으로 고치다 `async with` 블록의 들여쓰기 레벨이 어긋났다.

**해결**: `cat -A`로 탭 · 공백까지 보이게 출력해 정확한 줄을 찾아 고쳤다.

> 교훈: 터미널에서 붙여넣기 · 직접 편집할 때는 들여쓰기가 깨지기 쉽다. 파이썬처럼 들여쓰기에 민감한 언어는 고친 뒤 `cat -A`나 에디터 렌더링으로 한 번 더 확인한다.

#### 트러블슈팅: 챗봇 웹소켓 연결 안 됨 (Service/Ingress 누락)

**증상**: 이미지 빌드 성공, pod `2/2 Running`인데 브라우저에서 계속

```txt
WebSocket connection to 'wss://runshoes.ronanlab.dev/ws/chat' failed
```

**원인**: 컨테이너가 pod 안에 떠 있다고 밖에서 닿는 것이 아니다. `service.yaml`에 8766 포트가 없었고 `ingress.yaml`에 `/ws/chat` 규칙도 없었다. **컨테이너는 살아 있지만 거기까지 가는 길이 없는 상태**였다.

**해결**: Service에 포트, Ingress에 path 규칙을 더했다(더 구체적인 `/ws/chat`을 `/`보다 위에).

#### 트러블슈팅: ArgoCD가 느림

**증상**: Jenkins 빌드 · GitOps manifest push까지 성공했는데 pod가 몇 분째 안 바뀌었다.

**원인**: `kubectl get application -A`로 Application을 찾아 강제 sync를 걸려 했으나 **아무것도 안 나왔다**. 이 vcluster 안에서는 Application CRD 자체가 조회되지 않았다(호스트 클러스터에서 관리되는 것으로 추정, 정확한 원인은 못 풀었다). ArgoCD 웹 UI도 Ingress로 나와 있지 않아 port-forward가 필요했다. 알아보는 사이 **기본 polling 주기(약 3분)**가 돌아와 자동으로 sync됐다.

**해결**: 기다렸다.

> 교훈: `runshoes` 코드 레포는 GitLab webhook → Jenkins로 즉시 반응하는데, `gitops` 레포는 webhook이 없어 ArgoCD가 polling으로만 감지한다. 이 속도 차이 때문에 "빌드는 성공했는데 왜 안 바뀌지?"가 반복됐다. 급할 때는 강제 sync 방법을 찾느라 시간 쓰기보다 3분 기다리는 게 빠른 경우가 많았다.

#### 트러블슈팅: READY 2/2의 의미

**증상**: `kubectl get pods -n runshoes`의 `READY`가 `2/2`라 "pod가 2개 떴나" 하고 오해했다.

**원인**: pod는 1개다. `2/2`는 그 pod 안 **컨테이너 2개**(`runshoes`, `chatbot`)가 다 Ready라는 뜻이다. 두 컨테이너는 같은 pod 안에서 네트워크 네임스페이스를 공유하는 사이드카 패턴이라 목록에는 pod 하나로만 나온다.

**해결**: 오해였다. 고칠 것 없음.

#### 그 밖의 자잘한 것

- **`git pp` alias가 로컬 config에 가려짐**: global(`~/.gitconfig`)에 `pp`를 새로 만들어도 레포별 `.git/config`에 예전에 만든 같은 이름 alias(`push gitlab main`만 하는 버전)가 있으면 그게 먼저 적용된다. `git config --local --unset alias.pp`로 지우고 나서야 동작했다
- **두 리모트 push 방향 헷갈림**: `gitlab` remote의 push URL에 GitHub 주소가 잘못 섞여 있던 적이 있다. `git remote -v`로 fetch/push URL을 따로 확인한다
- **Jenkins는 GitHub이 아니라 GitLab만 감시**: 로컬 PC에서 GitHub에만 push하는 습관이 있었고, 우분투 서버의 `origin`은 GitHub, `gitlab`은 GitLab이었다. 우분투 서버에서 `git pull`(origin=GitHub)만 하고 GitLab에는 반영 안 된 상태가 이어져 webhook이 전혀 안 걸렸다
- **PVC 덕분에 데이터는 안전했다**: 재배포 중 잠깐 "리뷰가 하나도 없다"고 떠 당황했지만, 새 pod가 다 뜨기 전 과도기였고 PVC에 데이터가 남아 곧 정상화됐다. Deployment 재배포로 DB 데이터가 날아가지 않는다는 것을 다시 확인했다

### 끝 (2026-10-18)

RUNSHOES가 이 홈랩 클러스터로 옮겨지며 `runshoes.ronanlab.dev`는 클러스터 공용 터널 `ronanlab-tunnel`의 다섯 번째 호스트가 됐다. 런슈즈 Pod는 Ollama를 `http://192.168.122.1:11434`로 직접 부르므로 Service Token 헤더도 더는 쓰지 않는다. ollama-tunnel은 학교 PC 전용으로 남았다(03).

## 4. 남은 한계

해당 없음(옛 환경). 그때 알려진 위험은 GPU 서버와 vcluster가 서로 독립된 장애 지점이라 한쪽만 죽어도 서비스가 멈춘다는 것이었다.

## 5. 확인 방법

해당 없음(옛 환경). runshoes-tunnel이 사라졌는지는 호스트에서 `cloudflared tunnel --config /dev/null list`(2026-11-12: ollama-tunnel · ronanlab-tunnel만 있다).

# frontend

브라우저에서 도는 화면 세 벌. 셋 다 **정적 HTML 한 장**이라 빌드 도구가 없다.

```
frontend/
  client/          LXP 웹 클라이언트 — 실제 사용자가 보는 화면
  demo-console/    데모 콘솔 — 사가를 한 단계씩 돌려보는 시연용
  tutor-console/   튜터 콘솔. AI 튜터가 왜 그렇게 답했는지 보는 개발용
```

## 왜 셋인가

목적이 다르다.

| | client | demo-console | tutor-console |
|---|---|---|---|
| 보는 사람 | 사용자 | 발표자 · 개발자 | 개발자 |
| 흐름 | 가입 → 강의 → 구독 → 재생 | 시나리오를 버튼으로 한 단계씩 | 질문 하나와 그 답 |
| 강조 | 화면 자체 | 요청 · 응답 · traceId | route · intent · 근거 |
| 붙는 곳 | gateway :8080 | gateway :8080 | ai-service :8086 (직접) |

데모 콘솔은 발표 영상을 찍으려고 만들었다(D-65). 대시보드만 움직이면
"무엇 때문에 그렇게 됐는지"가 안 보여서, **클릭이라는 원인**을 화면에 두려는 것이다.

튜터 콘솔은 다른 이유다. 튜터를 확인할 수단이 파이썬 스크립트와 `curl` 뿐인데,
Git Bash 가 한글 본문을 깨뜨려 질문 하나 바꿀 때마다 임시 파일을 쓴다. 브라우저
`fetch` 는 본문을 UTF-8 로 고정해 보내므로 그 함정이 없어진다(AI-08).
계획은 [ai-service/docs/2026-08-20-테스트-콘솔-계획.md](../ai-service/docs/2026-08-20-테스트-콘솔-계획.md)에 있다.

## 실행

셋 다 nginx 컨테이너로 뜬다.

```bash
docker compose -f compose.demo.yaml up -d

# http://localhost:8091   데모 콘솔
# http://localhost:8092   웹 클라이언트
# http://localhost:8093   튜터 콘솔
```

앞의 둘은 백엔드(`compose.yaml`)가 먼저 올라와 있어야 한다.

**튜터 콘솔은 다르다.** 붙을 상대가 컨테이너가 아니라 호스트에서 도는 프로세스다.
ai-service 는 아직 compose 에 없다(AI-02).

```bash
docker compose -f compose.demo.yaml up -d tutor-console
```

띄우기 전에 `ai-service/` 에서 튜터를 먼저 올린다.

```bash
uv run uvicorn app.main:app --port 8086
```

## 튜터 콘솔은 CORS 를 안 쓴다

ai-service 는 CORS 를 열지 않는다. 게이트웨이 뒤에 설 서비스라서 그렇고, 지금 열면
닫는 것을 잊기 때문이다. 그런데 `X-Member-Id` 가 커스텀 헤더라 브라우저가
preflight(OPTIONS)를 보내고 서버는 405 를 준다.

그래서 nginx 가 정적 파일과 `/api/ai/` 를 **같은 출처(8093)** 로 묶는다. 같은
출처면 preflight 자체가 생기지 않는다. 게이트웨이가 붙으면(B2) 화면은 안 고치고
`tutor-console/nginx.conf` 의 `proxy_pass` 한 줄만 바꾼다.

컨테이너 안에서 `localhost` 는 컨테이너 자신이다. 그래서 upstream 이
`host.docker.internal:8086` 이고, 리눅스에서는 `extra_hosts` 가 있어야 502 가 안 난다.

## 포트를 바꾸려면 두 곳을 같이 고친다

client 와 demo-console 이야기다. CORS 허용 출처와 실제 포트가 다르면 브라우저가
preflight(OPTIONS)에서 전부 막아 **화면이 아무것도 못 한다.** 에러 메시지도
브라우저 콘솔에만 남는다.

```
compose.demo.yaml            ports
config-repo/gateway.yml      allowedOrigins
```

환경변수로도 바꿀 수 있다 — `DEMO_CONSOLE_ORIGIN`, `LXP_CLIENT_ORIGIN`.

튜터 콘솔은 게이트웨이를 안 거치므로 `allowedOrigins` 에 넣지 않는다. 포트를 바꾸면
`compose.demo.yaml` 한 곳만 고친다.

## 프레임워크를 쓰지 않는 이유

이 화면들의 목적은 **백엔드가 실제로 도는 것을 보여주는 것**이지
프론트엔드를 보여주는 것이 아니다. React를 붙이면 `node_modules`와 빌드 단계가
저장소에 들어오는데, 그 대가로 얻는 것이 여기서는 없다.

제대로 된 프론트엔드가 필요해지면 그때 별도 저장소나 하위 프로젝트로 만드는 편이 맞다.

## 백엔드 주소

client 와 demo-console 은 `index.html` 안의 `CONFIG`에 기본값이 박혀 있다.

```js
apiBase:     'http://localhost:8080'      // gateway
keycloakUrl: 'http://localhost:8180/...'  // 토큰 발급
zipkinBase:  'http://localhost:9411/...'  // traceId 링크
```

응답 헤더 `X-Trace-Id`로 Zipkin 링크를 만든다(D-65). 그 헤더는 gateway가 붙인다.

튜터 콘솔에는 이 값이 없다. 같은 출처라 `API = ''` 이고, 실제 주소는
`nginx.conf` 가 안다.

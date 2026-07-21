# frontend

브라우저에서 도는 화면 두 벌. 둘 다 **정적 HTML 한 장**이라 빌드 도구가 없다.

```
frontend/
  client/          LXP 웹 클라이언트 — 실제 사용자가 보는 화면
  demo-console/    데모 콘솔 — 사가를 한 단계씩 돌려보는 시연용
```

## 왜 둘인가

목적이 다르다.

| | client | demo-console |
|---|---|---|
| 보는 사람 | 사용자 | 발표자 · 개발자 |
| 흐름 | 가입 → 강의 → 구독 → 재생 | 시나리오를 버튼으로 한 단계씩 |
| 강조 | 화면 자체 | 요청 · 응답 · traceId |

데모 콘솔은 발표 영상을 찍으려고 만들었다(D-65). 대시보드만 움직이면
"무엇 때문에 그렇게 됐는지"가 안 보여서, **클릭이라는 원인**을 화면에 두려는 것이다.

## 실행

둘 다 nginx 컨테이너로 뜬다. 백엔드(`compose.yaml`)가 먼저 올라와 있어야 한다.

```bash
docker compose -f compose.demo.yaml up -d

# http://localhost:8091   데모 콘솔
# http://localhost:8092   웹 클라이언트
```

## 포트를 바꾸려면 두 곳을 같이 고친다

CORS 허용 출처와 실제 포트가 다르면 브라우저가 preflight(OPTIONS)에서
전부 막아 **화면이 아무것도 못 한다.** 에러 메시지도 브라우저 콘솔에만 남는다.

```
compose.demo.yaml            ports
config-repo/gateway.yml      allowedOrigins
```

환경변수로도 바꿀 수 있다 — `DEMO_CONSOLE_ORIGIN`, `LXP_CLIENT_ORIGIN`.

## 프레임워크를 쓰지 않는 이유

이 화면들의 목적은 **백엔드가 실제로 도는 것을 보여주는 것**이지
프론트엔드를 보여주는 것이 아니다. React를 붙이면 `node_modules`와 빌드 단계가
저장소에 들어오는데, 그 대가로 얻는 것이 여기서는 없다.

제대로 된 프론트엔드가 필요해지면 그때 별도 저장소나 하위 프로젝트로 만드는 편이 맞다.

## 백엔드 주소

`index.html` 안의 `CONFIG`에 기본값이 박혀 있다.

```js
apiBase:     'http://localhost:8080'      // gateway
keycloakUrl: 'http://localhost:8180/...'  // 토큰 발급
zipkinBase:  'http://localhost:9411/...'  // traceId 링크
```

응답 헤더 `X-Trace-Id`로 Zipkin 링크를 만든다(D-65). 그 헤더는 gateway가 붙인다.

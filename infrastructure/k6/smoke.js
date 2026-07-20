// k6 부하 테스트 (D-56)
//
// 게이트웨이를 실제 사용자 경로로 때린다 — Keycloak에서 토큰을 받고,
// 그 토큰으로 인증 경로를 호출한다. 공개 경로만 때리면 이 프로젝트에서
// 정작 무거운 부분(JWKS 검증 + introspection + 서비스 토큰 발급)을
// 건너뛰게 된다.
//
//   docker compose -f compose.load.yaml run --rm k6 run /scripts/smoke.js
//
// 임계값을 넘으면 k6가 종료 코드 99로 실패한다. "느려도 통과"가 되지
// 않도록 판정 기준을 스크립트에 박아둔다.

import http from 'k6/http';
import { check, group } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const GATEWAY = __ENV.GATEWAY_URL || 'http://gateway:8080';
const KEYCLOAK = __ENV.KEYCLOAK_URL || 'http://keycloak:8080';
const REALM = __ENV.KEYCLOAK_REALM || 'lxp';
const CLIENT = __ENV.KEYCLOAK_CLIENT || 'lxp-web';

const TEST_EMAIL = __ENV.TEST_EMAIL || 'k6-load@lxp.test';
const TEST_PASSWORD = __ENV.TEST_PASSWORD || 'Passw0rd!23';

// 인증이 필요한 경로. 회원 조회는 게이트웨이의 전 과정을 거친다 —
// JWKS 검증 + introspection(D-35) + 서비스 토큰 발급·부착(D-33).
const AUTHED_PATH = __ENV.AUTHED_PATH || '/api/members/4';

// 인증 경로와 공개 경로를 따로 본다. 둘을 섞어 평균내면
// 어느 쪽이 느린지 알 수 없다.
const authedLatency = new Trend('lxp_authed_latency', true);
const publicLatency = new Trend('lxp_public_latency', true);
const authFailures = new Rate('lxp_auth_failures');

export const options = {
  scenarios: {
    // 천천히 올렸다 내린다. 처음부터 최대로 때리면 JVM 워밍업 구간의
    // 지연이 전체 통계를 오염시킨다.
    ramp: {
      executor: 'ramping-vus',
      startVUs: 1,
      stages: [
        { duration: '20s', target: 5 },
        { duration: '40s', target: 20 },
        { duration: '20s', target: 0 },
      ],
      gracefulRampDown: '10s',
    },
  },
  thresholds: {
    // 하나라도 넘으면 실패다.
    http_req_failed: ['rate<0.01'],
    lxp_authed_latency: ['p(95)<1500'],
    lxp_public_latency: ['p(95)<500'],
    lxp_auth_failures: ['rate<0.01'],
  },
};

// 토큰 발급은 VU마다 한 번만 한다. 매 요청마다 받으면
// Keycloak 부하를 재는 테스트가 되어버린다.
export function setup() {
  const res = http.post(
    `${KEYCLOAK}/realms/${REALM}/protocol/openid-connect/token`,
    { client_id: CLIENT, grant_type: 'password', username: TEST_EMAIL, password: TEST_PASSWORD },
    { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } },
  );

  if (res.status !== 200) {
    // 토큰을 못 받으면 인증 경로는 전부 401이 되어 결과가 무의미하다.
    // 조용히 진행하지 않고 여기서 멈춘다.
    throw new Error(
      `토큰 발급 실패 (${res.status}). 테스트 계정이 있는지 확인한다: ${TEST_EMAIL}\n${res.body}`,
    );
  }
  const token = JSON.parse(res.body).access_token;

  // 때릴 경로가 실제로 존재하는지 setup에서 한 번 확인한다.
  // 없는 경로를 부하 대상으로 삼으면 400을 1분 내내 재는 테스트가 된다
  // — 실제로 /api/subscriptions/me로 그렇게 했다가 100% 실패로 끝났다.
  const probe = http.get(`${GATEWAY}${AUTHED_PATH}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (probe.status !== 200) {
    throw new Error(
      `인증 경로 확인 실패 (${probe.status}) ${AUTHED_PATH}\n${probe.body}`,
    );
  }
  return { token };
}

export default function (data) {
  const authHeaders = {
    headers: { Authorization: `Bearer ${data.token}` },
    tags: { path: 'authed' },
  };

  group('공개 경로', () => {
    const res = http.get(`${GATEWAY}/api/courses/ping`, { tags: { path: 'public' } });
    publicLatency.add(res.timings.duration);
    check(res, { 'ping 200': (r) => r.status === 200 });
  });

  group('인증 경로', () => {
    // 게이트웨이가 JWKS 검증 + introspection(D-35)을 하고
    // 서비스 토큰을 발급해 붙이는(D-33) 경로다.
    const res = http.get(`${GATEWAY}${AUTHED_PATH}`, authHeaders);
    authedLatency.add(res.timings.duration);

    const ok = res.status === 200;
    authFailures.add(!ok);
    check(res, {
      // 401/403이면 인증이 깨진 것이고, 400이면 경로가 틀린 것이다.
      '인증 통과 (200)': () => ok,
    });
  });
}

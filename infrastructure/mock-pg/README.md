# 목 PG (D-39)

실제 PG는 사업자등록이 있어야 키를 받습니다(P-01). 그때까지 **PG를 프로세스 안의
`if (amount > 0)`으로 두면 정작 실연동에서 터지는 것들이 하나도 드러나지 않습니다** —
타임아웃, 거절 코드, 승인번호 보관, 환불 호출 같은 것들입니다.

그래서 WireMock으로 **네트워크 건너편에 있는 PG**를 세워 둡니다. 실연동 시
`PgHttpClient`의 주소와 응답 매핑만 실제 PG 규격으로 바꾸면 됩니다.

## API

| 메서드 | 경로 | 용도 |
|---|---|---|
| POST | `/v1/payments` | 승인 요청 |
| POST | `/v1/payments/cancel` | 승인 취소(환불) |

승인 요청 본문에 `idempotencyKey`를 싣습니다. 실제 PG도 같은 키의 재요청을
같은 승인으로 처리하므로, 타임아웃 후 재시도해도 이중 청구가 되지 않습니다.

## 시나리오를 금액으로 고릅니다

실제 PG의 테스트 카드번호와 같은 방식입니다 — 특정 값이 특정 실패를 냅니다.

| 금액 | 응답 | 의미 |
|---|---|---|
| `1004` | 402 `LIMIT_EXCEEDED` (`retryable: true`) | 한도 초과 — 며칠 뒤 풀릴 수 있어 재시도 가치가 있음 |
| `1005` | 402 `STOLEN_CARD` (`retryable: false`) | 분실·도난 — 재시도해도 절대 안 됨 |
| `1006` | 200 (10초 지연) | 타임아웃 — 클라이언트 타임아웃보다 길게 |
| 그 외 | 200 `APPROVED` | 정상 승인 |

`retryable`이 dunning(D-37)과 연결됩니다. 재시도해도 소용없는 거절은
3회를 채우지 않고 즉시 포기합니다.

## 확인

```bash
curl -s -X POST http://localhost:8090/v1/payments \
  -H 'Content-Type: application/json' \
  -d '{"orderId":"sub-1-cycle-2","amount":29000,"idempotencyKey":"k1"}'
```

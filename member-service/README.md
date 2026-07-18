# member-service

회원 도메인과 **인증**을 함께 담당합니다. auth-service를 흡수했습니다 ([D-04](../docs/DECISIONS.md)).

- Port: `8082`
- Application: `com.lcs.member.MemberServiceApplication`
- Health: `http://localhost:8082/actuator/health`
- DB: MySQL `member_db` (예정)

## 책임

- 회원 가입 · 조회 · 수정
- **JWT 발급** — 검증은 Gateway가 합니다. 서명 키를 양쪽이 공유해야 하므로 `config-repo`에서 중앙 관리합니다.

## 엔드포인트

| 경로 | 설명 |
|---|---|
| `/api/members/**` | 회원 |
| `/api/auth/**` | 인증 (구 auth-service) |

## 패키지 구조

```text
com.lcs.member
├─ presentation/        MemberController · AuthController
├─ application/         유스케이스
├─ domain/              엔티티 · 도메인 이벤트
└─ infrastructure/
   ├─ persistence/
   ├─ outbox/
   └─ grpc/
```

## 현재 상태

ping 수준의 API만 있습니다. 실제 인증 구현은 [docs/NEXT_STEPS.md](../docs/NEXT_STEPS.md) Step 4 참고.

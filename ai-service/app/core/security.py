"""
app/core/security.py — 호출자 신원을 얻는 단 하나의 자리

이 파일의 역할: 요청에서 member_id 를 꺼낸다. 지금은 헤더를 그대로 믿는다.
→ app/api/endpoints.py 가 Depends(require_member_id) 로 쓴다
확인: X-Member-Id 없이 호출하면 401, 숫자로 넣으면 그 값이 돌아온다

주의 — 지금 이 파일은 안전하지 않다.
5기 MSA(lxp-msa-infrastructure-starter)에 붙일 때 서비스 토큰 검증으로 교체한다.
그때 검증할 것은 셋이다.
  1. 서명 (Keycloak JWKS)          위조 토큰 차단
  2. issuer 일치                    다른 realm 토큰 차단
  3. aud 에 lxp-internal 포함        게이트웨이를 거쳤다는 증명
세 번째가 핵심이다. 사용자 토큰도 같은 realm 이 서명하므로 앞의 둘은 통과한다.
이것이 없으면 사용자가 자기 토큰으로 직접 호출하면서 X-Member-Id 에 남의 id 를 넣을 수 있다.

신뢰 지점을 이 함수 하나로 모아둔 이유가 그것이다. 교체할 때 여기만 고치면 되고,
호출부(endpoints.py)는 손대지 않는다. 여러 곳에 흩어지면 한 곳만 빠뜨려도 뚫린다.
"""

from fastapi import Header, HTTPException


# 1. 호출자 식별 — 5기 gateway 의 JwtAuthenticationFilter 가 넣어주는 헤더를 받는다
def require_member_id(
    x_member_id: str | None = Header(None, alias="X-Member-Id"),
) -> int:
    if x_member_id is None:
        # 헤더 누락을 422 가 아니라 401 로 돌려준다.
        # 나중에 토큰 검증으로 바꿔도 클라이언트가 보는 상태 코드가 같아야 한다
        raise HTTPException(401, "게이트웨이를 거친 요청만 받는다")
    try:
        return int(x_member_id)
    except ValueError:
        raise HTTPException(401, "X-Member-Id 가 정수가 아니다")

## 개요

> 이 PR에서 무엇을 변경했는지 한 줄로 요약해 주세요.

## 연관 이슈

> ex) close #123

## PR 유형

- [ ] 기능 추가
- [ ] 버그 수정
- [ ] 리팩토링
- [ ] 설정 변경 (config, docker, infra)
- [ ] 문서 수정
- [ ] 테스트 추가/수정

## 변경 내용

> 어떤 문제를 해결했는지, 왜 이렇게 구현했는지 설명해 주세요.

## 테스트 방법

> 변경 사항을 확인하는 방법을 적어 주세요. (예: 실행 순서, 확인 엔드포인트 등)

```
# 예시
1. docker compose -f docker-compose.infra.yml up -d
2. ConfigServerApplication → GatewayApplication 순서로 실행
3. GET http://localhost:8080/api/.../ping
```

## 리뷰 포인트

> 리뷰어가 특히 확인해줬으면 하는 부분을 적어 주세요.

## 체크리스트

> 해당 없는 항목은 삭제해 주세요.

**인프라**
- [ ] `docker-compose.infra.yml` 정상 실행 확인
- [ ] Consul UI에서 서비스 등록 상태 확인
- [ ] Config Server에서 설정 정상 조회 확인
- [ ] Prometheus 메트릭 수집 확인

**서비스**
- [ ] 변경된 서비스 `actuator/health` 정상 응답 확인
- [ ] Gateway 라우팅 정상 동작 확인
- [ ] 서비스 간 통신 정상 동작 확인 (해당하는 경우)

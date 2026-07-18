# subscription-service

구독 도메인 코드를 옮길 자리이며, 현재 Gateway를 통해 노출되는 최소 조회 API가 있습니다.

- Port: `8084`
- Application: `com.lcs.subscription.SubscriptionServiceApplication`
- Health: `http://localhost:8084/actuator/health`

결제 도메인은 [payment-service](../payment-service)로 분리됐습니다. `/api/payments/**`는 더 이상 이 서비스가 서빙하지 않습니다.

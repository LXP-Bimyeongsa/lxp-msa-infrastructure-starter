# gateway

외부 요청의 단일 진입점. Consul에서 서비스를 찾아 경로별로 라우팅합니다.

- Port: `8080`
- Application: `com.lcs.gateway.GatewayApplication`
- Health: `http://localhost:8080/actuator/health`

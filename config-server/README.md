# config-server

로컬 config-repo를 읽어 각 서비스의 설정을 제공합니다. 이후 Git backend로 교체할 수 있습니다.

- Port: `8888`
- Application: `com.lcs.configserver.ConfigServerApplication`
- Health: `http://localhost:8888/actuator/health`

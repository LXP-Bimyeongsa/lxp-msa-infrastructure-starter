# CI (Jenkins)

## 기동

```bash
docker compose -f compose.ci.yaml up -d
docker compose -f compose.ci.yaml exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
```

http://localhost:9080 접속 후 위 비밀번호로 초기 설정.

> 호스트 포트가 9080인 이유: Jenkins 기본 8080은 gateway와 충돌합니다.

## 초기 설정

1. **Install suggested plugins** 선택
2. 관리자 계정 생성
3. 추가 플러그인 설치: `Pipeline`, `Git`, `Docker Pipeline`
4. 컨테이너 안에 docker CLI 설치 (파이프라인이 `docker build`를 실행합니다)

```bash
docker compose -f compose.ci.yaml exec jenkins bash -c \
  "apt-get update && apt-get install -y docker.io"
```

## 파이프라인 등록

**New Item → Pipeline** 생성 후:

- **Pipeline script from SCM** 선택
- SCM: Git, Repository URL: `https://github.com/LXP-Bimyeongsa/lxp-msa-infrastructure-starter.git`
- Script Path: `ci/Jenkinsfile`
- Public 레포라 인증정보 없이 읽을 수 있습니다.

## 파이프라인 동작

| 단계 | 내용 |
|---|---|
| Checkout | 커밋 체크아웃, 짧은 해시 확보 |
| 변경 서비스 탐지 | 직전 커밋과 diff. 변경된 서비스 폴더만 골라냄 |
| 빌드·테스트 | 대상 서비스만 `./gradlew clean build` |
| Docker 이미지 빌드 | `main` 브랜치일 때만 실행 |

서비스 7개를 매번 전부 빌드하면 한 줄 고쳐도 10분 넘게 걸립니다. 그래서 변경분만 빌드합니다.
다만 `config-repo/`, `compose*`, `.gitattributes` 같은 **공용 파일이 바뀌면 어느 서비스가 영향받는지 알 수 없으므로 전체를 빌드**합니다.

## 트리거 — 지금은 폴링입니다

로컬 Jenkins에는 공인 IP가 없어 GitHub webhook을 받을 수 없습니다. 그래서 `pollSCM('H/5 * * * *')`으로 5분마다 변경을 확인합니다.

webhook을 쓰려면 둘 중 하나가 필요합니다.

- **ngrok 등 터널** — `ngrok http 9080`으로 받은 공개 URL을 GitHub 레포 Settings → Webhooks에 등록. 무료 플랜은 재시작할 때마다 URL이 바뀝니다.
- **공인 IP가 있는 서버에 Jenkins 배치**

webhook으로 전환하면 Jenkinsfile의 `triggers` 블록에서 `pollSCM` 줄을 지우면 됩니다.

## 알아둘 것

파이프라인이 이미지를 빌드해야 해서 호스트의 `/var/run/docker.sock`을 컨테이너에 마운트합니다(Docker outside of Docker). **컨테이너가 호스트의 Docker를 그대로 조종할 수 있다는 뜻**이라, 사실상 호스트 root 권한과 같습니다. 로컬 학습 환경이라 이렇게 두지만, 외부에 노출되는 곳에서는 쓰면 안 됩니다.

## 미검증

Jenkins 컨테이너 기동과 파이프라인 실행은 아직 확인하지 않았습니다. Jenkinsfile 문법도 정적 검토만 거쳤습니다. 첫 실행 시 조정이 필요할 수 있습니다.

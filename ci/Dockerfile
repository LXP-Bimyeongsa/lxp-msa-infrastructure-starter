# Jenkins + docker CLI (D-38)
#
# 파이프라인의 "Docker 이미지 빌드" 단계가 `docker build`를 부르는데,
# jenkins/jenkins 이미지에는 docker CLI가 들어 있지 않다.
# 실제로 띄워서 확인했더니 `docker: not found`로 그 단계만 실패한다.
#
# 데몬은 설치하지 않는다 — 호스트의 docker.sock을 마운트해 쓰는 DooD 구성이라
# 클라이언트만 있으면 된다. 데몬까지 넣으면(DinD) 이미지 캐시가 분리되고
# 특권 컨테이너가 필요해진다.
# 베이스 버전은 여기서만 정한다 (D-46).
# 관리 화면의 "자동 업그레이드" 버튼은 쓰지 않는다 — 그것은 실행 중인 볼륨의
# jenkins.war만 바꾸므로, 다음 재빌드에서 이 줄의 버전으로 조용히 되돌아간다.
# jdk21인 이유: Java 17 지원이 2026-03-31에 끝났다.
FROM jenkins/jenkins:2.568.1-jdk21

USER root

# docker CLI만 설치한다. buildx는 compose 빌드에 필요하지 않아 뺀다.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg \
        | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && chmod a+r /etc/apt/keyrings/docker.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
        https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

# 빌드용 JDK 17 (D-48).
#
# Jenkins 자신은 21에서 돌지만, 우리 서비스의 build.gradle은 Java 17
# toolchain을 요구한다. jdk17 이미지에서 jdk21로 올렸더니 Gradle이
# "Cannot find a Java installation matching {languageVersion=17}"으로
# 6개 서비스 빌드를 전부 실패시켰다(빌드 #10).
#
# "CI가 도는 JVM"과 "우리 코드를 컴파일하는 JVM"은 다른 관심사다.
# 앞의 것은 최신·패치된 것을 쓰고, 뒤의 것은 서비스가 요구하는 버전을 맞춘다.
#
# apt로 깔지 않는 이유 — 이 이미지의 베이스는 Debian 13(trixie)이고
# 거기엔 openjdk-17 패키지가 없다(21·25만 있다).
#
# /usr/lib/jvm은 Gradle이 toolchain을 자동 탐지하는 표준 경로다.
# 다른 곳에 두면 org.gradle.java.installations.paths를 따로 잡아줘야 한다.
RUN mkdir -p /usr/lib/jvm/temurin-17 \
    && curl -fsSL "https://api.adoptium.net/v3/binary/latest/17/ga/linux/x64/jdk/hotspot/normal/eclipse" \
        | tar -xz --strip-components=1 -C /usr/lib/jvm/temurin-17 \
    && /usr/lib/jvm/temurin-17/bin/java -version

# 플러그인을 이미지에 미리 넣는다 (D-40).
# 설정 마법사로 깔면 컨테이너 볼륨을 지울 때마다 다시 클릭해야 한다.
COPY plugins.txt /usr/share/jenkins/ref/plugins.txt
RUN jenkins-plugin-cli --plugin-file /usr/share/jenkins/ref/plugins.txt

# 설정은 ci/jenkins.yaml이 소유한다. 마법사는 끈다.
ENV JAVA_OPTS="-Djenkins.install.runSetupWizard=false"
ENV CASC_JENKINS_CONFIG=/var/jenkins_home/casc/jenkins.yaml

# 호스트 docker.sock이 root 소유라 root로 돈다.
# 로컬 학습 환경 전제다 — 컨테이너가 호스트 Docker를 그대로 조종할 수 있다.
USER root

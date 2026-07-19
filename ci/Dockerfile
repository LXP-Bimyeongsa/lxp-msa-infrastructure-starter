# Jenkins + docker CLI (D-38)
#
# 파이프라인의 "Docker 이미지 빌드" 단계가 `docker build`를 부르는데,
# jenkins/jenkins 이미지에는 docker CLI가 들어 있지 않다.
# 실제로 띄워서 확인했더니 `docker: not found`로 그 단계만 실패한다.
#
# 데몬은 설치하지 않는다 — 호스트의 docker.sock을 마운트해 쓰는 DooD 구성이라
# 클라이언트만 있으면 된다. 데몬까지 넣으면(DinD) 이미지 캐시가 분리되고
# 특권 컨테이너가 필요해진다.
FROM jenkins/jenkins:2.492-jdk17

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

# 호스트 docker.sock이 root 소유라 root로 돈다.
# 로컬 학습 환경 전제다 — 컨테이너가 호스트 Docker를 그대로 조종할 수 있다.
USER root

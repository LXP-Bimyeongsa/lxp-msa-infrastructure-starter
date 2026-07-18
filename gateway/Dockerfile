FROM gradle:9.3.0-jdk17 AS builder
WORKDIR /build
COPY . .
RUN cd gateway && gradle clean bootJar --no-daemon

FROM eclipse-temurin:17-jre
WORKDIR /app
COPY --from=builder /build/gateway/build/libs/*.jar app.jar
ENTRYPOINT ["java", "-jar", "app.jar"]

# ---------- build stage ----------
FROM eclipse-temurin:25-jdk AS build
WORKDIR /app

# t3.medium에서 빌드가 메모리를 먹지 않게 제한
ENV GRADLE_OPTS="-Dorg.gradle.jvmargs=-Xmx768m -Dorg.gradle.daemon=false -Dorg.gradle.workers.max=2"

# 의존성 레이어 캐싱: 소스보다 먼저 복사해야 재빌드가 빨라집니다
COPY gradlew .
COPY gradle gradle
COPY build.gradle settings.gradle ./
RUN chmod +x gradlew && ./gradlew dependencies --no-daemon || true

COPY src src
RUN ./gradlew bootJar --no-daemon -x test

FROM eclipse-temurin:25-jre
WORKDIR /app

# docker-compose 헬스체크(curl -> /actuator/health)용
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /app/build/libs/app.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java","-XX:MaxRAMPercentage=70","-XX:+UseSerialGC","-jar","/app/app.jar"]
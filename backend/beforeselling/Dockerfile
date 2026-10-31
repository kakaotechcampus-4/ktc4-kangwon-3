# 소스 컴파일
FROM eclipse-temurin:25-jdk AS build
WORKDIR /app
ENV GRADLE_OPTS="-Dorg.gradle.jvmargs=-Xmx768m -Dorg.gradle.daemon=false -Dorg.gradle.workers.max=2"
COPY gradlew .
COPY gradle gradle
COPY build.gradle settings.gradle ./
RUN chmod +x gradlew && ./gradlew dependencies --no-daemon || true
COPY src src
RUN ./gradlew bootJar --no-daemon -x test

# 공통 베이스
FROM eclipse-temurin:25-jre AS runtime-base
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
EXPOSE 8080
ENTRYPOINT ["java","-XX:MaxRAMPercentage=70","-XX:+UseSerialGC","-jar","/app/app.jar"]

# 로컬(build 스테이지에서 만든 결과물 사용)
FROM runtime-base AS local
COPY --from=build /app/build/libs/app.jar app.jar

# 배포. 의존성과 앱 코드를 레이어로 분할
FROM runtime-base AS extract
COPY build/libs/app.jar app.jar
RUN java -Djarmode=tools -jar app.jar extract --layers --destination extracted

FROM runtime-base AS deploy
COPY --from=extract /app/extracted/dependencies/ ./
COPY --from=extract /app/extracted/spring-boot-loader/ ./
COPY --from=extract /app/extracted/snapshot-dependencies/ ./
COPY --from=extract /app/extracted/application/ ./
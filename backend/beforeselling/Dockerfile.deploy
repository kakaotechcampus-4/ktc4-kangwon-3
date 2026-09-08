# 배포(CI/CD) 전용 이미지.
# CI 단계(./gradlew build)에서 이미 만들어진 jar를 그대로 담기만 하므로 컴파일이 일어나지 않는다.
# 로컬 개발에서 소스부터 직접 빌드할 때는 멀티스테이지 방식의 Dockerfile 을 사용한다.
FROM eclipse-temurin:25-jre
WORKDIR /app

# docker compose 헬스체크(curl -> /actuator/health)용
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY build/libs/app.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java","-XX:MaxRAMPercentage=70","-XX:+UseSerialGC","-jar","/app/app.jar"]

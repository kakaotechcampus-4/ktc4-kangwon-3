package kakaotech.kangwon3.beforeselling.support;

import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.postgresql.PostgreSQLContainer;

/**
 * 실제 PostgreSQL 컨테이너가 필요한 테스트의 공통 설정. H2로는 확인할 수 없는 마이그레이션 SQL을 검증할 때 상속한다.
 * 운영과 같은 PostgreSQL 16 이미지를 쓰고, Docker가 없는 환경에서는 테스트를 건너뛴다.
 */
@Testcontainers(disabledWithoutDocker = true)
public abstract class PostgresContainerSupport {

    @Container
    @ServiceConnection
    static final PostgreSQLContainer POSTGRES = new PostgreSQLContainer("postgres:16-alpine");
}

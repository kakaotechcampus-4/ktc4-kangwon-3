package kakaotech.kangwon3.beforeselling.global;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Arrays;
import kakaotech.kangwon3.beforeselling.support.PostgresContainerSupport;
import org.flywaydb.core.Flyway;
import org.flywaydb.core.api.MigrationInfo;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;

@Tag("integration")
@SpringBootTest(properties = {
        "spring.datasource.driver-class-name=org.postgresql.Driver",
        "spring.flyway.enabled=true",
        "spring.jpa.hibernate.ddl-auto=validate"
})
@ActiveProfiles("test")
class FlywayMigrationTest extends PostgresContainerSupport {

    @Autowired
    private Flyway flyway;

    @Test
    @DisplayName("빈 PostgreSQL에 마이그레이션을 모두 적용하면 엔티티 매핑 검증을 통과해 애플리케이션이 뜬다")
    void migrationsMatchEntityMappings() {
        // given: 빈 DB에 Flyway 마이그레이션만으로 스키마를 만들고
        // when: ddl-auto=validate로 컨텍스트를 띄우면
        // then: 테이블·컬럼 누락이나 타입 불일치 없이 기동된다
        assertThat(flyway.info().current()).isNotNull();
    }

    @Test
    @DisplayName("적용된 마이그레이션은 모두 성공 상태로 이력에 기록된다")
    void allAppliedMigrationsSucceeded() {
        // given: 컨텍스트 기동 시 마이그레이션이 적용된 상태에서
        // when: 적용 이력을 조회하면
        MigrationInfo[] applied = flyway.info().applied();

        // then: 하나 이상 있고 모두 성공이다
        assertThat(applied).isNotEmpty();
        assertThat(Arrays.stream(applied).map(info -> info.getState().isFailed())).containsOnly(false);
    }
}

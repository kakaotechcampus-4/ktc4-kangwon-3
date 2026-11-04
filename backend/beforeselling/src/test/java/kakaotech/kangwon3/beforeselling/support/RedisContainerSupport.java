package kakaotech.kangwon3.beforeselling.support;

import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

/**
 * 실제 Redis 컨테이너가 필요한 테스트의 공통 설정. 직렬화·TTL처럼 mock으로는 확인할 수 없는 동작을 검증할 때 상속한다.
 * 운영과 같은 Redis 7 이미지를 쓰고, Docker가 없는 환경에서는 테스트를 건너뛴다.
 */
@Testcontainers(disabledWithoutDocker = true)
public abstract class RedisContainerSupport {

    @Container
    @ServiceConnection
    static final GenericContainer<?> REDIS = new GenericContainer<>("redis:7").withExposedPorts(6379);
}

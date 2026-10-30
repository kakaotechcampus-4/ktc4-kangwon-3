package kakaotech.kangwon3.beforeselling.global.config;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.scheduling.concurrent.ThreadPoolTaskScheduler;
import org.springframework.test.context.ActiveProfiles;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest
@ActiveProfiles("test")
class SchedulingConfigTest {

    @Autowired
    private ThreadPoolTaskScheduler taskScheduler;

    @Test
    @DisplayName("AI를 호출하는 스케줄러가 막혀도 정리 스케줄러가 돌 수 있도록 스케줄러 스레드를 3개 둔다.")
    void taskScheduler_thenPoolSizeIsThree() {
        assertThat(taskScheduler.getScheduledThreadPoolExecutor().getCorePoolSize()).isEqualTo(3);
    }
}

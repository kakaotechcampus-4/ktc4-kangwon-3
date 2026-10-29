package kakaotech.kangwon3.beforeselling.global.infra.ai.dto;

import java.util.List;

// AI 진단 접수 거절 응답(409)의 data. 이미 진행 중이라 거절 사유가 된 상품들
public record AiDiagnosesConflict(
        List<String> conflictProductIds
) {
}

package kakaotech.kangwon3.beforeselling.global.infra.ai.dto;

import java.util.List;

// AI 진단 접수 응답(202)의 data. runId는 그 실행의 콜백에 같은 값으로 실린다.
public record AiDiagnosesAccepted(
        String diagnosisId,
        List<AcceptedProduct> products
) {

    public record AcceptedProduct(
            String productId,
            String runId,
            String status
    ) {
    }
}

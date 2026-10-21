package kakaotech.kangwon3.beforeselling.global.infra.ai.dto;

import java.util.List;

// AI 진단 접수 요청 DTO (POST /api/ai/v1/diagnose/content)
public record AiDiagnosesRequest(
        String diagnosisId,
        List<Product> products
) {

    // 상품 하나. 텍스트·이미지 중 하나 이상이 있어야 AI가 받는다.
    public record Product(
            String productId,
            List<String> textBlocks,
            // 이름과 달리 base64 data URI뿐 아니라 이미지 URL도 받는다.
            List<String> imagesBase64
    ) {
    }
}

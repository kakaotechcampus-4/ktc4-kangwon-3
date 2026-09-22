package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.usecase;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.request.DiagnosesCreateRequest;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesCreateResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesDetailResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesListResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.mapper.DiagnosesMapper;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.ProductService;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;


@Service
@RequiredArgsConstructor
public class DiagnosesUseCase {

    private final ProductService productService;
    private final DiagnosesMapper diagnosesMapper;

    public DiagnosesCreateResponse createDiagnoses(Long userId, DiagnosesCreateRequest request) {
        Product product = productService.createProduct(diagnosesMapper.toCommand(userId, request));

        // TODO: AI 서버에 진단 요청(POST /api/diagnoses)을 보내고 processingStatus를 IN_PROGRESS로 전이?
        return diagnosesMapper.toCreateResponse(product);
    }

    public DiagnosesDetailResponse getDiagnoses(Long userId, Long diagnosesId) {
        Product product = productService.getProduct(userId, diagnosesId);

        return diagnosesMapper.toDetailResponse(product);
    }

    public DiagnosesListResponse getDiagnosesList(Long userId, ResultStatus resultStatus, Pageable pageable) {
        return diagnosesMapper.toListResponse(productService.getProductList(userId, resultStatus, pageable));
    }

    public void removeDiagnoses(Long userId, Long diagnosesId) {
        productService.removeProduct(userId, diagnosesId);
    }
}

package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.mapper;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.request.DiagnosesCreateRequest;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.request.ProductCreateRequest;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesCreateResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesDetailResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.ProductCreateCommand;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.util.List;

@Component
@RequiredArgsConstructor
public class DiagnosesMapper {

    private final ProductMapper productMapper;

    public List<ProductCreateCommand> toCommands(DiagnosesCreateRequest request) {
        return request.products().stream()
                .map(this::toCommand)
                .toList();
    }

    private ProductCreateCommand toCommand(ProductCreateRequest request) {
        return new ProductCreateCommand(
                request.productName(),
                request.productImageKey(),
                request.sourceType(),
                request.sourceUrl(),
                request.sourceText(),
                request.imageKeys() == null ? List.of() : request.imageKeys()
        );
    }

    public DiagnosesCreateResponse toCreateResponse(Diagnoses diagnoses) {
        return new DiagnosesCreateResponse(diagnoses.getId());
    }

    public DiagnosesDetailResponse toDetailResponse(Diagnoses diagnoses) {
        List<ProductResponse> products = diagnoses.getProducts().stream()
                .map(productMapper::toResponse)
                .toList();

        return new DiagnosesDetailResponse(
                diagnoses.getId(),
                diagnoses.getProcessingStatus(),
                products,
                diagnoses.getCreatedAt(),
                diagnoses.getUpdatedAt()
        );
    }

}

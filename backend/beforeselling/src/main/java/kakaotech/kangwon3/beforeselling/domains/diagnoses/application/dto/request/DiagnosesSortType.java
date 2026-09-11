package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.request;

import lombok.Getter;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Sort;

@Getter
@RequiredArgsConstructor
public enum DiagnosesSortType {

    LATEST(Sort.by(Sort.Direction.DESC, "createdAT")),
    OLDEST(Sort.by(Sort.Direction.ASC, "createdAt")),
    ;

    private final Sort sort;
}

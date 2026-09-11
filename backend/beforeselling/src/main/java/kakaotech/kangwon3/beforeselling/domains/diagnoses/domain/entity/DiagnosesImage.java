package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity;

import jakarta.persistence.*;
import kakaotech.kangwon3.beforeselling.global.common.BaseEntity;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@Table(
        name = "diagnoses_image",
        indexes = @Index(name = "idx_diagnoses_image_diagnoses_id", columnList = "diagnoses_id")
)
public class DiagnosesImage extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "diagnoses_image_id")
    private Long id;

    @Column(name = "diagnoses_id", nullable = false)
    private Long diagnosesId;

    @Column(name = "image_url", nullable = false)
    private String imageUrl;

    // BE -> AI OCR 깨짐 방지를 위하여
    @Column(name = "sort_order", nullable = false)
    private int sortOrder;

    private DiagnosesImage(Long diagnosesId, String imageUrl, int sortOrder) {
        this.diagnosesId = diagnosesId;
        this.imageUrl = imageUrl;
        this.sortOrder = sortOrder;
    }

    public static DiagnosesImage of(Long diagnosesId, String imageUrl, int sortOrder) {
        return new DiagnosesImage(diagnosesId, imageUrl, sortOrder);
    }
}

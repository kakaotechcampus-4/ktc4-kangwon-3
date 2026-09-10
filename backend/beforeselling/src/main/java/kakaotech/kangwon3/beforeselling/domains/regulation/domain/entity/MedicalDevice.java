package kakaotech.kangwon3.beforeselling.domains.regulation.domain.entity;

import java.time.OffsetDateTime;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.Builder;
import lombok.NoArgsConstructor;

@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@Table(name = "medical_devices")
public class MedicalDevice {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "medical_device_id")
    private Long id;

    @Column(name = "device_sn", length = 30, nullable = false, unique = true)
    private String deviceSn;

    @Column(name = "product_name", length = 300, nullable = false)
    private String productName;

    @Column(name = "classification_no", length = 30)
    private String classificationNo;

    @Column(name = "grade", length = 5)
    private String grade;

    @Column(name = "permission_type", length = 20)
    private String permissionType;

    @Column(name = "industry", length = 30)
    private String industry;

    @Column(name = "purpose", columnDefinition = "TEXT")
    private String purpose;

    @Column(name = "fetched_at", nullable = false)
    private OffsetDateTime fetchedAt;

    @Builder(access = AccessLevel.PRIVATE)
    private MedicalDevice(String deviceSn,
                          String productName,
                          String classificationNo,
                          String grade,
                          String permissionType,
                          String industry,
                          String purpose,
                          OffsetDateTime fetchedAt) {
        this.deviceSn = deviceSn;
        this.productName = productName;
        this.classificationNo = classificationNo;
        this.grade = grade;
        this.permissionType = permissionType;
        this.industry = industry;
        this.purpose = purpose;
        this.fetchedAt = fetchedAt;
    }

    public static MedicalDevice fromApi(String deviceSn,
                                        String productName,
                                        String classificationNo,
                                        String grade,
                                        String permissionType,
                                        String industry,
                                        String purpose) {
        return MedicalDevice.builder()
                .deviceSn(deviceSn)
                .productName(productName)
                .classificationNo(classificationNo)
                .grade(grade)
                .permissionType(permissionType)
                .industry(industry)
                .purpose(purpose)
                .fetchedAt(OffsetDateTime.now())
                .build();
    }
}

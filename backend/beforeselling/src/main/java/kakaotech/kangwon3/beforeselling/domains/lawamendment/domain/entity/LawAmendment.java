package kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ToolName;
import kakaotech.kangwon3.beforeselling.global.common.BaseEntity;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.UuidGenerator;

import java.time.LocalDate;
import java.util.UUID;

// AI가 전송한 진단 근거 법령의 변경
@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@Table(
        name = "law_amendment",
        uniqueConstraints = @UniqueConstraint(
                name = "uk_law_amendment_document_id_serial_number",
                columnNames = {"document_id", "serial_number"}
        )
)
public class LawAmendment extends BaseEntity {

    @Id
    @UuidGenerator(style = UuidGenerator.Style.VERSION_7)
    @Column(name = "law_amendment_id")
    private UUID id;

    @Column(name = "law_name", nullable = false)
    private String lawName;

    // 법령ID 또는 행정규칙ID. 판이 바뀌어도 같음.
    @Column(name = "document_id", nullable = false, length = 50)
    private String documentId;

    // 행정규칙(고시·훈령·예규)이면 true
    @Column(name = "admrul", nullable = false)
    private boolean admrul;

    @Enumerated(EnumType.STRING)
    @Column(name = "tool_name", nullable = false)
    private ToolName toolName;

    // 법령일련번호(MST) 또는 행정규칙일련번호
    @Column(name = "serial_number", nullable = false, length = 50)
    private String serialNumber;

    @Column(name = "previous_serial_number", length = 50)
    private String previousSerialNumber;

    // 제개정구분 (일부개정, 전부개정 등)
    @Column(name = "revision_type", length = 50)
    private String revisionType;

    @Column(name = "enforce_date")
    private LocalDate enforceDate;

    @Column(name = "issued_date")
    private LocalDate issuedDate;

    @Builder
    private LawAmendment(String lawName, String documentId, boolean admrul, ToolName toolName,
                         String serialNumber, String previousSerialNumber, String revisionType,
                         LocalDate enforceDate, LocalDate issuedDate) {
        this.lawName = lawName;
        this.documentId = documentId;
        this.admrul = admrul;
        this.toolName = toolName;
        this.serialNumber = serialNumber;
        this.previousSerialNumber = previousSerialNumber;
        this.revisionType = revisionType;
        this.enforceDate = enforceDate;
        this.issuedDate = issuedDate;
    }
}

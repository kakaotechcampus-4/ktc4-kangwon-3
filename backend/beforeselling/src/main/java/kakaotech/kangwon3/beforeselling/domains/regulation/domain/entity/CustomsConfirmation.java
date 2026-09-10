package kakaotech.kangwon3.beforeselling.domains.regulation.domain.entity;

import java.time.LocalDate;
import java.time.OffsetDateTime;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@Table(name = "customs_confirmations")
public class CustomsConfirmation {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "customs_confirmation_id")
    private Long id;

    @Column(name = "hs_code", length = 10, nullable = false)
    private String hsCode;

    @Column(name = "import_export", length = 1, nullable = false)
    private String importExport;

    @Column(name = "law_name", length = 200)
    private String lawName;

    @Column(name = "agency_name", length = 100)
    private String agencyName;

    @Column(name = "document_name", length = 300)
    private String documentName;

    @Column(name = "apply_start_date")
    private LocalDate applyStartDate;

    @Column(name = "fetched_at", nullable = false)
    private OffsetDateTime fetchedAt;
}

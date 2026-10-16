package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import kakaotech.kangwon3.beforeselling.global.common.BaseEntity;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.UuidGenerator;

import java.util.UUID;

// 진행 콜백(ProductProgressEvent)의 단계·툴별 최신 상태. 이벤트를 쌓지 않고 (stage, toolName)마다 한 행을 덮어쓴다.
@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@Table(name = "product_progress")
public class ProductProgress extends BaseEntity {

    @Id
    @UuidGenerator(style = UuidGenerator.Style.VERSION_7)
    @Column(name = "product_progress_id")
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "product_id", nullable = false)
    private Product product;

    @Column(name = "run_id", nullable = false)
    private String runId;

    // 실행마다 1부터 증가한다. 같은 실행 안에서 늦게 온 이벤트를 가려내는 데 쓴다.
    @Column(name = "sequence", nullable = false)
    private int sequence;

    @Enumerated(EnumType.STRING)
    @Column(name = "stage", nullable = false)
    private PipelineStage stage;

    @Enumerated(EnumType.STRING)
    @Column(name = "stage_status", nullable = false)
    private StageStatus stageStatus;

    // TOOL_EXECUTION 단계에서만 값이 있다.
    @Enumerated(EnumType.STRING)
    @Column(name = "tool_name")
    private ToolName toolName;

    ProductProgress(Product product, String runId, int sequence,
                    PipelineStage stage, StageStatus stageStatus, ToolName toolName) {
        this.product = product;
        this.runId = runId;
        this.sequence = sequence;
        this.stage = stage;
        this.stageStatus = stageStatus;
        this.toolName = toolName;
    }

    boolean isFor(PipelineStage stage, ToolName toolName) {
        return this.stage == stage && this.toolName == toolName;
    }

    // 같은 실행에서 이미 반영한 이벤트보다 앞선(또는 같은) 이벤트인지. 실행이 바뀌면 sequence가 1부터 다시 시작한다.
    boolean isNewerOrSame(String runId, int sequence) {
        return this.runId.equals(runId) && this.sequence >= sequence;
    }

    void update(String runId, int sequence, StageStatus stageStatus) {
        this.runId = runId;
        this.sequence = sequence;
        this.stageStatus = stageStatus;
    }
}

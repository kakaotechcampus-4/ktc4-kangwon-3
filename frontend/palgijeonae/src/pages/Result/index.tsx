import { useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { isMissingRouteParam } from "@/lib/routeParams";

function ResultPage() {
    const { productId, diagnosesId } = useParams<{ productId?: string; diagnosesId?: string }>();
    const navigate = useNavigate();

    const isMissingProductId = isMissingRouteParam(productId);
    const isMissingDiagnosesId = isMissingRouteParam(diagnosesId);
    // 파라미터 값이 둘 다 있거나, 둘 다 없는 경우 비정상 접근
    const isInvalidAccess = isMissingProductId === isMissingDiagnosesId;

    useEffect(() => {
        if (isInvalidAccess) {
            alert("잘못된 접근입니다.");
            navigate("/", { replace: true });
        }
    }, [isInvalidAccess, navigate]);

    if (!isMissingProductId) {
        // TODO: GET /api/v1/products/{productId} 조회 (마이페이지 → 상품 단건)
    } else if (!isMissingDiagnosesId) {
        // TODO: GET /api/v1/diagnoses/{diagnosesId} 조회 (질문 페이지 → 진단서 단위, 여러 상품)
    }

    return (
        <div>
            <h1>결과 페이지 입니다.</h1>
        </div>
     );
}

export default ResultPage;
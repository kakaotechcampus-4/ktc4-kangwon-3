import { type DiagnosesDetail } from "@/api/product";

import apiClient from "./client";

export async function getDiagnosesPolling(diagnosesId: string) {
    const response = await apiClient.get(`/api/v1/diagnoses/${diagnosesId}`);
    return response.data.data as DiagnosesDetail;
}

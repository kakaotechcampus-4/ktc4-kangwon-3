/**
 * 에이전트 블럭의 진행 상황을 나타내는 타입
 * - call: 해당 에이전트를 부를지 결정 중
 * - act: 해당 에이전트가 가동 중
 * - end: 해당 에이전트의 판정이 끝남
 * - skip: 해당 에이전트 호출이 필요 없다고 판단되어 스킵함
 * - fail: 에이전트 호출 실패
 */
export type ProcessType = "call" | "act" | "end" | "skip" | "fail";

/** 하나의 에이전트 진행 상황을 나타내는 블럭 */
export interface Agent {
    id: string
    title: string
    job: string
    detail: string
    status: ProcessType
}

/**
 * 상품 하나의 판정 상태.
 * - name: 상품명
 * - agents: 이 상품을 진단하는 에이전트들과 각각의 진행 상황
 * - visibleCount: agents 중 몇 번째까지 화면에 공개할지(진행 중/진행 완료된 에이전트가 몇 번까지인지)
 */
export interface ProductState {
    name: string
    agents: Agent[]
    visibleCount: number
}

/** 판정 페이지 전체 상태. 진단 중인 상품 목록과, 그중 지금 보고 있는/실제로 진행 중인 상품이 무엇인지를 담는다. */
export interface JudgementState {
    products: ProductState[]
    selectedProduct: number
    // 자동 전환의 기준이 되는, 실제 진행 중인 제품
    furthestProduct: number
}
/** 조항 안의 문장 하나. label이 있으면 앞부분을 굵게 보여준다. */
export interface PolicyItem {
    label?: string
    text: string
}

/** 개인정보 처리 위탁처럼 두 열로 보여주는 표 */
export interface PolicyTable {
    headers: [string, string]
    rows: [string, string][]
}

export interface PolicySection {
    // 목차에서 이 조항으로 스크롤할 때 쓰는 앵커 id
    id: string
    heading: string
    items: PolicyItem[]
    table?: PolicyTable
}

export interface PolicyHighlight {
    label: string
    value: string
}

/**
 * 문서 맨 위 요약.
 * - notice: 이용약관의 면책 요약 (제목과 문장들)
 * - highlights: 개인정보처리방침의 한눈에 보기 (제목과 항목 카드들)
 */
export type PolicySummary =
    | { kind: "notice", title: string, paragraphs: string[] }
    | { kind: "highlights", title: string, highlights: PolicyHighlight[] }

export interface PolicyDocument {
    title: string
    // 화면에는 "시행일 {effectiveDate}"로 보여준다.
    effectiveDate: string
    summary: PolicySummary
    sections: PolicySection[]
    footnote: string
}

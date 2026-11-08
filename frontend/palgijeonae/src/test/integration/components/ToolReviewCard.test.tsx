import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Determination, ToolReviewStatus } from '@/api/types/product'
import ToolReviewCard from '@/pages/Result/components/DiagnosisResult/components/ToolReviewCard'
import { buildFinding, buildToolReview } from '@/test/mocks/fixtures'

// 판정 항목이 없는 분야. 검토를 끝내지 못했다는 안내만 있다.
const INCOMPLETE_MESSAGE = '관련 법령을 찾지 못해 검토를 끝내지 못했어요.'
const incompleteReview = buildToolReview({ status: ToolReviewStatus.Incomplete, message: INCOMPLETE_MESSAGE, findings: [] })

describe('분야별 검토 카드 - 판정 항목이 없는 분야', () => {
  it('전체 보기에서는 판정 항목이 없어도 분야명, 상태, 메시지를 보여준다', () => {
    render(<ToolReviewCard toolReview={incompleteReview} findingFilter={null} />)

    expect(screen.getByText('전기 안전')).toBeInTheDocument()
    expect(screen.getByText(/검토 미완료/)).toBeInTheDocument()
    expect(screen.getByText(INCOMPLETE_MESSAGE)).toBeInTheDocument()
  })

  it('판정 항목이 없는 검토 완료 분야도 전체 보기에서는 분야명과 상태를 보여준다', () => {
    render(<ToolReviewCard toolReview={buildToolReview({ findings: [] })} findingFilter={null} />)

    expect(screen.getByText('전기 안전')).toBeInTheDocument()
    expect(screen.getByText(/검토 완료/)).toBeInTheDocument()
  })

  it('필터를 적용했을 때는 판정 항목이 없는 분야를 숨긴다', () => {
    const { container } = render(<ToolReviewCard toolReview={incompleteReview} findingFilter={Determination.Required} />)

    expect(container).toBeEmptyDOMElement()
  })
})

describe('분야별 검토 카드 - 필터', () => {
  const review = buildToolReview({
    findings: [
      buildFinding({ productFindingId: 'finding-required', determination: Determination.Required, summary: '조치가 필요한 항목' }),
      buildFinding({ productFindingId: 'finding-not-required', determination: Determination.NotRequired, summary: '통과한 항목' }),
    ],
  })

  it('전체 보기에서는 모든 판정 항목을 보여준다', () => {
    render(<ToolReviewCard toolReview={review} findingFilter={null} />)

    expect(screen.getByText('조치가 필요한 항목')).toBeInTheDocument()
    expect(screen.getByText('통과한 항목')).toBeInTheDocument()
  })

  it('필터를 적용하면 그 판정의 항목만 남기고, 분야명은 계속 보여준다', () => {
    render(<ToolReviewCard toolReview={review} findingFilter={Determination.NotRequired} />)

    expect(screen.getByText('전기 안전')).toBeInTheDocument()
    expect(screen.getByText('통과한 항목')).toBeInTheDocument()
    expect(screen.queryByText('조치가 필요한 항목')).not.toBeInTheDocument()
  })

  it('필터에 맞는 판정 항목이 하나도 없으면 분야 전체를 숨긴다', () => {
    const { container } = render(<ToolReviewCard toolReview={review} findingFilter={Determination.PossiblyRequired} />)

    expect(container).toBeEmptyDOMElement()
  })
})

import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import MyProductList from '@/pages/Products/components/MyProductList'
import { buildMyProduct } from '@/test/mocks/fixtures'
import { renderWithProviders } from '@/test/utils/renderWithProviders'
import { setMobileViewport } from '@/test/utils/viewport'

const renderList = () =>
  renderWithProviders(
    <MyProductList
      products={[buildMyProduct()]}
      isLoading={false}
      isError={false}
      onRetry={() => {}}
      page={0}
      totalPages={12}
      hasNext
      onPageChange={() => {}}
      selectedIds={new Set()}
      onToggleSelect={() => {}}
      isSelectionDisabled={false}
    />,
  )

// 페이지 번호 버튼은 이름이 숫자뿐이다. (처음·이전·다음·마지막 버튼과 선택 체크박스는 이름이 다르다)
const getPageNumberButtons = () => screen.getAllByRole('button', { name: /^\d+$/ })

describe('마이페이지 상품 목록 - 페이지 번호 개수', () => {
  it('데스크톱에서는 페이지 번호를 10개씩 보여준다', () => {
    renderList()

    expect(getPageNumberButtons()).toHaveLength(10)
  })

  it('모바일에서는 페이지 번호를 5개씩 보여준다', () => {
    setMobileViewport()
    renderList()

    expect(getPageNumberButtons()).toHaveLength(5)
  })
})

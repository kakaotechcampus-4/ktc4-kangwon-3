import { Route } from 'react-router-dom'

import MyPage from '@/pages/Mypage'
import ResultPage from '@/pages/Result'
import { myPage } from '@/test/drivers/myPage'
import { resultPage } from '@/test/drivers/resultPage'
import { buildMyProduct } from '@/test/mocks/fixtures'
import { getCurrentLocation, renderRoutes } from '@/test/utils/renderWithProviders'

// 테스트가 응답에 넣는 데이터. 화면 문구가 아니라 이 테스트의 입력값이다.
const PRODUCT_NAME = buildMyProduct().productName

// 이전 화면의 링크가 넘긴 state를 도착 화면의 이전으로 버튼이 쓰는지, 실제 화면 둘을 함께 렌더해서 사용자 흐름으로 확인한다.
// 진단 진행 화면을 스텁으로 둔 이유: state가 아니라 진단 진행 화면으로 가는 경로(폴백)를 탔다면 마이페이지가 아니라 이 화면이 보여 테스트가 실패한다.
const renderApp = (route: string) =>
  renderRoutes(
    <>
      <Route path="/mypage" element={<MyPage />} />
      <Route path="/result/product/:productId" element={<ResultPage />} />
      <Route path="/judgement/:diagnosesId" element={<p>진단 진행 화면</p>} />
    </>,
    { route },
  )

describe('이전으로 버튼 - 화면 이동 흐름', () => {
  it('마이페이지에서 상품을 눌러 결과 화면으로 간 뒤 이전으로를 누르면 마이페이지로 돌아온다', async () => {
    renderApp('/mypage')
    const mypage = myPage()
    const result = resultPage()
    await mypage.waitForProduct(PRODUCT_NAME)

    await mypage.openProduct(PRODUCT_NAME)
    await result.waitUntilLoaded()
    expect(getCurrentLocation()).toBe('/result/product/product-1')

    await result.clickBack()

    await mypage.waitForProduct(PRODUCT_NAME)
    expect(getCurrentLocation()).toBe('/mypage')
  })
})

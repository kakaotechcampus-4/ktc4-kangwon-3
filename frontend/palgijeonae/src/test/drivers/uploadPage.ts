import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'

import { UPLOAD_MESSAGES } from '@/test/constants/messages'

// 업로드 화면 드라이버. 테스트 본문은 이 파일의 함수만 거쳐서 화면을 조작·조회한다.
// 화면 구성(문구, 구조)이 바뀌면 테스트 본문은 두고 이 파일만 고친다.
//
//   const page = uploadPage()
//   await page.addUrlProduct({ title: '이어폰' })
//   expect(page.productNames()).toEqual(['이어폰'])

type User = ReturnType<typeof userEvent.setup>

const DEFAULT_LINK = 'https://example.com/item'

export function uploadPage(user: User = userEvent.setup()) {
  // ── 요소 찾기 ──────────────────────────────────────────────
  const titleInput = () => screen.getByLabelText(/^제품명$/)
  const linkInput = () => screen.getByLabelText(/상세페이지 링크/)
  const contentInput = () => screen.getByLabelText(/상세페이지 내용/)

  // NOTE(source): 대표 사진 file input은 숨겨져 있고 접근 가능한 이름(label)이 없어서 id로 찾는다.
  // 소스에서 input에 label을 연결하면(예: aria-label="제품 대표 사진") getByLabelText로 바꿀 수 있다.
  const mainImageInput = () => document.getElementById('product-image') as HTMLInputElement

  // "확인할 제품" 패널의 목록(list)과 항목(listitem)이 카드의 한 행이다. 상품이 없으면 패널 자체가 없다.
  const productRows = (): HTMLElement[] => {
    const list = screen.queryByRole('list', { name: '확인할 제품 목록' })
    return list ? within(list).getAllByRole('listitem') : []
  }
  const titleOf = (row: HTMLElement): string => within(row).getByRole('heading').textContent?.trim() ?? ''

  // 화면에 보이는 제품명으로 카드 행을 찾는다. 같은 이름이 둘이면 먼저 나온 것을 쓴다.
  const productRow = (name: string): HTMLElement => {
    const row = productRows().find((candidate) => titleOf(candidate) === name)
    if (!row) {
      throw new Error(`"${name}" 상품을 찾을 수 없습니다. 현재 목록: ${JSON.stringify(productRows().map(titleOf))}`)
    }
    return row
  }

  // 긴 문자열은 한 글자씩 입력하면 느려서 붙여넣기로 채운다.
  const fill = async (input: HTMLElement, text: string) => {
    await user.click(input)
    await user.paste(text)
  }

  const clickButton = (name: RegExp) => user.click(screen.getByRole('button', { name }))

  // 자세히 보기 모달과 이미지 확대 창은 한 번에 한 겹만 뜨므로, 열려 있는 대화상자는 하나뿐이다. 둘이 겹치면 getByRole이 실패한다.
  const openDialog = () => screen.getByRole('dialog')
  const lightbox = () => screen.getByRole('dialog', { name: '이미지 미리보기' })
  const detailImageButtons = () => within(openDialog()).queryAllByRole('button', { name: /크게 보기$/ })

  return {
    // ── 조작 ────────────────────────────────────────────────
    fillTitle: (text: string) => fill(titleInput(), text),
    fillLink: (text: string) => fill(linkInput(), text),
    fillContent: (text: string) => fill(contentInput(), text),
    clickAddProduct: () => clickButton(/상품 추가하기/),

    /** URL 탭에서 제품명과 링크를 입력하고 상품을 추가한다. */
    async addUrlProduct({ title, link = DEFAULT_LINK }: { title: string; link?: string }) {
      await fill(titleInput(), title)
      await fill(linkInput(), link)
      await clickButton(/상품 추가하기/)
    },

    /** 텍스트/이미지 탭에서 제품명과 내용을 입력하고 상품을 추가한다. 먼저 switchToTextImage()로 탭을 바꿔 둔다. */
    async addTextImageProduct({ title, content }: { title: string; content: string }) {
      await fill(titleInput(), title)
      await fill(contentInput(), content)
      await clickButton(/상품 추가하기/)
    },

    switchToUrl: () => clickButton(/^URL$/),
    switchToTextImage: () => clickButton(/텍스트\s*\/\s*이미지/),

    attachMainImage: (file: File) => user.upload(mainImageInput(), file),

    /** 이름이 같은 카드의 삭제 버튼을 누른다. */
    async removeProduct(name: string) {
      await user.click(within(productRow(name)).getByRole('button', { name: /^삭제$/ }))
    },

    /** 이름이 같은 카드(항목)를 눌러 상세를 연다. */
    async openDetail(name: string) {
      await user.click(within(productRow(name)).getByRole('button', { name: /자세히 보기$/ }))
    },

    // ── 자세히 보기 모달과 이미지 확대 창 ───────────────────────────
    /** 이 제목의 자세히 보기 모달이 열려 있는지 */
    isDetailOpen: (title: string) => screen.queryByRole('dialog', { name: title }) !== null,
    /** 열려 있는 대화상자(모달, 확대 창)의 수 */
    dialogCount: () => screen.queryAllByRole('dialog').length,
    /** 모달 아래의 "닫기" 버튼을 누른다. (위의 "창 닫기"와 구분된다) */
    closeDetail: () => user.click(within(openDialog()).getByRole('button', { name: '닫기' })),
    removeFromDetail: () => user.click(within(openDialog()).getByRole('button', { name: '목록에서 삭제' })),
    pressEscape: () => user.keyboard('{Escape}'),
    /** 모달 안 상세페이지 이미지 썸네일의 파일 이름들 */
    detailImageNames: () => detailImageButtons().map((button) => (button.getAttribute('aria-label') ?? '').replace(/ 크게 보기$/, '')),
    clickDetailImage: (fileName: string) => user.click(within(openDialog()).getByRole('button', { name: `${fileName} 크게 보기` })),
    isDetailImageFocused: (fileName: string) => within(openDialog()).getByRole('button', { name: `${fileName} 크게 보기` }) === document.activeElement,
    isLightboxOpen: () => screen.queryByRole('dialog', { name: '이미지 미리보기' }) !== null,
    showNextLightboxImage: () => user.click(within(lightbox()).getByRole('button', { name: '다음 이미지' })),
    closeLightbox: () => user.click(within(lightbox()).getByRole('button', { name: '닫기' })),
    /** 이름이 같은 카드(항목) 버튼에 포커스가 있는지. 모달을 닫으면 여기로 돌아온다. */
    isItemFocused: (name: string) => within(productRow(name)).getByRole('button', { name: /자세히 보기$/ }) === document.activeElement,

    startDiagnosis: () => clickButton(/진단 시작하기/),
    clickShowList: () => clickButton(/^목록 보기$/),

    // ── 조회 ────────────────────────────────────────────────
    /** 목록에 보이는 제품명을 추가한 순서대로 돌려준다. (긴 이름은 글자를 자르지 않고 CSS가 한 줄에서 줄여 보인다) */
    productNames: () => productRows().map(titleOf),

    /** 항목 위에 마우스를 올리면 보이는 전체 제목(title 속성) */
    productTooltip: (name: string) => within(productRow(name)).getByRole('button', { name: /자세히 보기$/ }).getAttribute('title'),

    thumbnailSrc: (name: string) => within(productRow(name)).getByAltText('상품 썸네일').getAttribute('src'),

    /** 열린 상세 모달에서 그 주소의 링크를 찾아 이동에 쓰이는 속성을 돌려준다. */
    detailLink(url: string) {
      const link = screen.getByRole('link', { name: url })
      return { href: link.getAttribute('href'), target: link.getAttribute('target'), rel: link.getAttribute('rel') }
    },
    hasDetailContent: (text: string) => screen.queryByText(text) !== null,

    /** 하단 바의 "확인할 제품 n / 10"에서 숫자 부분 (예: "3 / 10") */
    productCountLabel: () => screen.getByText(/^\d+ \/ \d+$/).textContent,
    hasStartButton: () => screen.queryByRole('button', { name: /진단 시작하기/ }) !== null,
    hasShowListButton: () => screen.queryByRole('button', { name: /^목록 보기$/ }) !== null,
    /** 스크롤한 요소 중에 "확인할 제품" 패널(목록을 담은 요소)이 있는지. scrollIntoView는 vitest.setup의 스텁이 호출을 기록한다. */
    wasProductListScrolledTo() {
      const list = screen.queryByRole('list', { name: '확인할 제품 목록' })
      const targets = vi.mocked(Element.prototype.scrollIntoView).mock.contexts as Element[]
      return list !== null && targets.some((target) => target.contains(list))
    },

    isFormVisible: () => screen.queryByLabelText(/^제품명$/) !== null,
    hasMaxProductsNotice: () => screen.queryByText(UPLOAD_MESSAGES.MAX_PRODUCTS_REACHED) !== null,

    // NOTE(source): 첨부한 이미지의 미리보기 목록에는 이름 붙은 그룹이 없어서, 각 썸네일 버튼의 이름("파일명 크게 보기")으로 확인한다.
    // 자세히 보기 모달 안의 상세페이지 이미지도 같은 이름이라, 모달을 열지 않은 상태에서 쓴다.
    hasAttachedImage: (fileName?: string) =>
      screen.queryAllByRole('button', { name: fileName ? `${fileName} 크게 보기` : /크게 보기$/ }).length > 0,

    /** 진단 요청을 보내는 중인지(로딩 표시가 있는지) */
    isSubmitting: () => screen.queryByRole('status') !== null,
    waitUntilSubmitting: () => screen.findByRole('status'),

    // ── 입력값 ──────────────────────────────────────────────
    titleValue: () => (titleInput() as HTMLInputElement).value,
    linkValue: () => (linkInput() as HTMLInputElement).value,
    contentValue: () => (contentInput() as HTMLTextAreaElement).value,
  }
}

export type UploadPage = ReturnType<typeof uploadPage>

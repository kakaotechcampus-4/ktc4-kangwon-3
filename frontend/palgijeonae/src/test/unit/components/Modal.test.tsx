import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import Modal from '@/components/common/Modal'

// 뒤 화면을 막는 inert는 앱의 #root에 걸리므로, 테스트에서도 같은 요소를 만들어 둔다.
let appRoot: HTMLDivElement

beforeEach(() => {
  appRoot = document.createElement('div')
  appRoot.id = 'root'
  document.body.appendChild(appRoot)
})

afterEach(() => {
  appRoot.remove()
})

const renderModal = (props: Partial<React.ComponentProps<typeof Modal>> = {}) => {
  const onClose = vi.fn()
  const view = render(
    <Modal title="상품 자세히 보기" onClose={onClose} {...props}>
      <p>본문 내용</p>
    </Modal>,
  )
  return { ...view, onClose }
}

const getDialog = () => screen.getByRole('dialog', { name: '상품 자세히 보기' })

// 부모가 렌더 여부로 여닫는 실제 사용 방식. 열기 버튼에 포커스가 있던 상태에서 연다.
function Harness({ onClose }: { onClose?: () => void }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>열기</button>
      {open && (
        <Modal
          title="상품 자세히 보기"
          footer={<button type="button">확인</button>}
          onClose={() => {
            onClose?.()
            setOpen(false)
          }}
        >
          <p>본문 내용</p>
        </Modal>
      )}
    </>
  )
}

describe('Modal - 표시', () => {
  it('제목으로 이름 붙은 대화상자에 본문을 보여주고, 열리면 대화상자로 포커스를 옮긴다', () => {
    renderModal()

    expect(getDialog()).toHaveAttribute('aria-modal', 'true')
    expect(screen.getByRole('heading', { name: '상품 자세히 보기' })).toBeInTheDocument()
    expect(within(getDialog()).getByText('본문 내용')).toBeInTheDocument()
    expect(getDialog()).toHaveFocus()
  })

  it('하단 버튼 영역을 넘기면 함께 보여준다', () => {
    renderModal({ footer: <button type="button">확인</button> })

    expect(within(getDialog()).getByRole('button', { name: '확인' })).toBeInTheDocument()
  })

  it('하단 버튼 영역을 넘기지 않으면 닫기 버튼 외에 버튼이 없다', () => {
    renderModal()

    expect(within(getDialog()).getAllByRole('button')).toHaveLength(1)
  })

  it('상단 닫기 버튼의 이름은 "창 닫기"라서, 하단 버튼 영역의 "닫기" 버튼과 구분된다', () => {
    renderModal({ footer: <button type="button">닫기</button> })

    expect(within(getDialog()).getAllByRole('button', { name: '창 닫기' })).toHaveLength(1)
    expect(within(getDialog()).getAllByRole('button', { name: '닫기' })).toHaveLength(1)
  })
})

describe('Modal - 닫기', () => {
  it('Esc를 누르면 닫는다', async () => {
    const user = userEvent.setup()
    const { onClose } = renderModal()

    await user.keyboard('{Escape}')

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('닫기 버튼을 누르면 한 번만 닫는다', async () => {
    const user = userEvent.setup()
    const { onClose } = renderModal()

    await user.click(within(getDialog()).getByRole('button', { name: '창 닫기' }))

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('바깥 배경을 누르면 닫지만, 대화상자 안을 눌러서는 닫지 않는다', async () => {
    const user = userEvent.setup()
    const { onClose } = renderModal()

    await user.click(within(getDialog()).getByText('본문 내용'))
    expect(onClose).not.toHaveBeenCalled()

    await user.click(getDialog().parentElement as HTMLElement)
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})

describe('Modal - 포커스와 접근성', () => {
  it('Tab 이동이 대화상자 안에서만 돌고, 끝에서 다시 처음으로 돌아온다', async () => {
    const user = userEvent.setup()
    render(
      <Modal title="상품 자세히 보기" footer={<button type="button">확인</button>} onClose={vi.fn()}>
        <p>본문 내용</p>
      </Modal>,
    )

    await user.tab()
    expect(screen.getByRole('button', { name: '창 닫기' })).toHaveFocus()

    await user.tab()
    expect(screen.getByRole('button', { name: '확인' })).toHaveFocus()

    await user.tab()
    expect(screen.getByRole('button', { name: '창 닫기' })).toHaveFocus()

    await user.tab({ shift: true })
    expect(screen.getByRole('button', { name: '확인' })).toHaveFocus()
  })

  it('열려 있는 동안 배경 스크롤과 뒤 화면 접근을 막고, 닫으면 풀고 열기 전 포커스로 돌려준다', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    const opener = screen.getByRole('button', { name: '열기' })
    await user.click(opener)

    expect(document.body.style.overflow).toBe('hidden')
    expect(appRoot.inert).toBe(true)
    expect(getDialog()).toHaveFocus()

    await user.keyboard('{Escape}')

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(document.body.style.overflow).toBe('')
    expect(appRoot.inert).toBe(false)
    expect(opener).toHaveFocus()
  })

  it('다시 열어도 같은 동작을 한다', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    render(<Harness onClose={onClose} />)
    const opener = screen.getByRole('button', { name: '열기' })

    await user.click(opener)
    await user.click(getDialog().parentElement as HTMLElement)
    expect(onClose).toHaveBeenCalledTimes(1)
    expect(opener).toHaveFocus()

    await user.click(opener)
    expect(getDialog()).toHaveFocus()
    expect(appRoot.inert).toBe(true)
  })
})

describe('Modal - 포커스 규칙', () => {
  it('안쪽 요소가 이미 포커스를 가져갔으면 대화상자로 옮기지 않는다', () => {
    render(
      <Modal title="상품 자세히 보기" onClose={vi.fn()}>
        <button type="button" autoFocus>썸네일</button>
      </Modal>,
    )

    expect(screen.getByRole('button', { name: '썸네일' })).toHaveFocus()
    expect(getDialog()).not.toHaveFocus()
  })

  it('안쪽 요소가 포커스를 가져갔어도, 닫으면 열기 전에 포커스가 있던 요소로 돌려준다', async () => {
    const user = userEvent.setup()
    function WithAutoFocus() {
      const [open, setOpen] = useState(false)
      return (
        <>
          <button type="button" onClick={() => setOpen(true)}>열기</button>
          {open && (
            <Modal title="상품 자세히 보기" onClose={() => setOpen(false)}>
              <button type="button" autoFocus>썸네일</button>
            </Modal>
          )}
        </>
      )
    }
    render(<WithAutoFocus />, { container: appRoot })
    const opener = screen.getByRole('button', { name: '열기' })

    await user.click(opener)
    expect(screen.getByRole('button', { name: '썸네일' })).toHaveFocus()

    await user.keyboard('{Escape}')
    expect(opener).toHaveFocus()
  })

  // inert 안의 요소는 실제 브라우저에서 포커스를 받지 못한다. (jsdom은 막지 않아서, 포커스를 돌려주는 시점에 이미 풀렸는지를 본다)
  it('열기 전 포커스로 돌려주는 시점에는 뒤 화면의 inert가 이미 풀려 있다', async () => {
    const user = userEvent.setup()
    render(<Harness />, { container: appRoot })
    const opener = screen.getByRole('button', { name: '열기' })
    await user.click(opener)
    expect(appRoot.inert).toBe(true)

    let inertWhenFocusReturned: boolean | undefined
    vi.spyOn(opener, 'focus').mockImplementation(() => {
      inertWhenFocusReturned = appRoot.inert
    })
    await user.keyboard('{Escape}')

    expect(inertWhenFocusReturned).toBe(false)
  })
})

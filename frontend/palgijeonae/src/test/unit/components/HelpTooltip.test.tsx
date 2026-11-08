import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import HelpTooltip from '@/components/common/HelpTooltip'

const renderTooltip = () =>
  render(
    <div>
      <HelpTooltip label="도움말">설명 문구</HelpTooltip>
      <p>바깥 영역</p>
    </div>,
  )

describe('HelpTooltip - 터치', () => {
  it('터치로 ? 버튼을 탭하면 안내가 열리고, 바깥을 탭하면 닫힌다', async () => {
    const user = userEvent.setup()
    renderTooltip()

    await user.pointer({ keys: '[TouchA]', target: screen.getByRole('button', { name: '도움말' }) })
    expect(await screen.findByRole('tooltip')).toHaveTextContent('설명 문구')

    await user.pointer({ keys: '[TouchA]', target: screen.getByText('바깥 영역') })
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
  })

  it('이미 열려 있을 때 ? 버튼을 다시 탭해도 닫히지 않는다 (바깥을 탭해야 닫힘)', async () => {
    const user = userEvent.setup()
    renderTooltip()
    const button = screen.getByRole('button', { name: '도움말' })

    await user.pointer({ keys: '[TouchA]', target: button })
    await user.pointer({ keys: '[TouchA]', target: button })

    expect(screen.getByRole('tooltip')).toBeInTheDocument()
  })
})

describe('HelpTooltip - 마우스', () => {
  it('마우스를 올리면 열리고 클릭해도 닫히지 않으며, 벗어나면 닫힌다', async () => {
    const user = userEvent.setup()
    renderTooltip()
    const button = screen.getByRole('button', { name: '도움말' })

    await user.hover(button)
    expect(await screen.findByRole('tooltip')).toBeInTheDocument()

    await user.click(button)
    expect(screen.getByRole('tooltip')).toBeInTheDocument()

    await user.unhover(button)
    await user.click(screen.getByText('바깥 영역'))
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
  })
})

import { createGate } from '@/test/utils/createGate'
import { expectNotified, expectNotNotified, waitForNotificationCount, waitForNotified } from '@/test/utils/notifications'

// 테스트 유틸(createGate, 알림 헬퍼)이 의도대로 동작하는지 확인한다. 이 헬퍼들을 믿고 통합 테스트를 쓰므로 실패하는 쪽도 확인한다.
describe('createGate', () => {
  it('release하기 전에는 기다리고, release하면 풀린다', async () => {
    const gate = createGate()
    let released = false
    void gate.promise.then(() => {
      released = true
    })

    await Promise.resolve()
    expect(released).toBe(false)

    gate.release()
    await gate.promise

    expect(released).toBe(true)
  })

  it('여러 번 release해도 문제없다', async () => {
    const gate = createGate()

    gate.release()
    gate.release()

    await expect(gate.promise).resolves.toBeUndefined()
  })

  it('gate마다 따로 동작한다', async () => {
    const first = createGate()
    const second = createGate()
    let secondReleased = false
    void second.promise.then(() => {
      secondReleased = true
    })

    first.release()
    await first.promise
    await Promise.resolve()

    expect(secondReleased).toBe(false)
  })
})

describe('알림 헬퍼', () => {
  it('알림을 띄우지 않았으면 expectNotNotified가 통과하고 expectNotified는 실패한다', () => {
    expectNotNotified()
    expect(() => expectNotified('안내')).toThrow()
  })

  it('문자열은 전체가 같을 때만 일치한다', () => {
    alert('질문에 모두 답변해 주세요.')

    expectNotified('질문에 모두 답변해 주세요.')
    expect(() => expectNotified('질문에 모두')).toThrow()
  })

  it('RegExp는 일부만 맞아도 일치한다', () => {
    alert('다음 상품의 진단 요청에 실패했습니다: 이어폰(S3 오류)')

    expectNotified(/진단 요청에 실패/)
    expect(() => expectNotified(/탈퇴/)).toThrow()
  })

  it('{ includes }는 그 문자열을 포함하면 일치한다', () => {
    alert('다음 상품의 진단 요청에 실패했습니다: 이어폰(S3 오류)')

    expectNotified({ includes: '이어폰(' })
    expect(() => expectNotified({ includes: '마우스(' })).toThrow()
  })

  it('알림이 여러 번 떴으면 그중 하나라도 일치하면 통과한다', () => {
    alert('첫 번째')
    alert('두 번째')

    expectNotified('첫 번째')
    expectNotified('두 번째')
  })

  it('알림을 띄운 뒤에는 expectNotNotified가 실패한다', () => {
    alert('안내')

    expect(() => expectNotNotified()).toThrow()
  })

  it('실패 메시지에 기대한 내용과 실제로 받은 알림이 함께 나온다', () => {
    alert('실제 알림')

    expect(() => expectNotified('기대한 알림')).toThrowError(/기대한 알림.*실제 알림/)
  })

  it('waitForNotified는 나중에 알림이 뜰 때까지 기다린다', async () => {
    setTimeout(() => alert('늦게 뜬 알림'), 30)

    await waitForNotified('늦게 뜬 알림')
  })

  it('waitForNotificationCount는 알림이 정해진 횟수가 될 때까지 기다린다', async () => {
    alert('하나')
    setTimeout(() => alert('둘'), 30)

    await waitForNotificationCount(2)
  })

  it('알림 기록은 테스트마다 초기화된다', () => {
    expectNotNotified()
  })
})

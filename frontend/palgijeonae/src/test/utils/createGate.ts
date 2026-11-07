// 응답을 풀어 줄 때까지 붙잡아 두는 문. "요청하는 동안 버튼이 비활성화된다"처럼 진행 중 상태를 확인할 때 쓴다.
export interface Gate {
  promise: Promise<void>
  release: () => void
}

export function createGate(): Gate {
  let release!: () => void
  const promise = new Promise<void>((resolve) => {
    release = resolve
  })
  return { promise, release }
}

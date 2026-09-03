import { useState } from 'react'
import reactLogo from './assets/react.svg'
import viteLogo from './assets/vite.svg'

function App() {
  const [count, setCount] = useState(0)

  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-6 bg-white text-center dark:bg-neutral-900">
      <div className="flex items-center gap-4">
        <img src={viteLogo} className="h-16 w-16" alt="Vite logo" />
        <img src={reactLogo} className="h-16 w-16" alt="React logo" />
      </div>

      <h1 className="text-4xl font-semibold text-neutral-900 dark:text-white">
        Tailwind CSS 적용 완료
      </h1>
      <p className="text-neutral-500 dark:text-neutral-400">
        Edit <code className="rounded bg-neutral-100 px-2 py-1 font-mono text-sm dark:bg-neutral-800">src/App.tsx</code> and save to test HMR
      </p>

      <button
        type="button"
        className="rounded-full border-2 border-transparent bg-purple-100 px-4 py-2 font-medium text-purple-600 transition-colors hover:border-purple-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-purple-600 dark:bg-purple-950 dark:text-purple-300"
        onClick={() => setCount((count) => count + 1)}
      >
        Count is {count}
      </button>
    </div>
  )
}

export default App

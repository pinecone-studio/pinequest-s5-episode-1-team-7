import { useEffect, useState } from 'react'

import { API_URL } from './api'

type BackendStatus = 'checking' | 'online' | 'offline'

function useBackendStatus(intervalMs = 5000): BackendStatus {
  const [status, setStatus] = useState<BackendStatus>('checking')

  useEffect(() => {
    let cancelled = false
    const check = async (): Promise<void> => {
      try {
        const response = await fetch(`${API_URL}/health`)
        if (!cancelled) setStatus(response.ok ? 'online' : 'offline')
      } catch {
        if (!cancelled) setStatus('offline')
      }
    }
    check()
    const timer = setInterval(check, intervalMs)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [intervalMs])

  return status
}

const STATUS_STYLE: Record<BackendStatus, string> = {
  checking: 'bg-slate-400',
  online: 'bg-emerald-500',
  offline: 'bg-red-500'
}

function App(): React.JSX.Element {
  const status = useBackendStatus()

  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-4">
        <h1 className="text-lg font-semibold">Pathology Triage</h1>
        <span className="flex items-center gap-2 text-sm text-slate-600">
          <span className={`h-2.5 w-2.5 rounded-full ${STATUS_STYLE[status]}`} />
          Backend {status}
        </span>
      </header>

      <main className="flex flex-1 items-center justify-center p-6 text-slate-500">
        Worklist and slide viewer go here (TDD 6.1, 6.2).
      </main>

      {/* TDD 8.1: required warning against over-reliance on the AI triage. */}
      <footer className="border-t border-amber-200 bg-amber-50 px-6 py-3 text-sm text-amber-900">
        AI Triage System is a prioritization assistant, not a diagnostic engine. All slides must be
        manually reviewed.
      </footer>
    </div>
  )
}

export default App

import { Component, type ErrorInfo, type ReactNode } from 'react'

import i18n from '../i18n/index.ts'

interface State {
  error: Error | null
}

/** Keeps a rendering bug on one page from blanking the whole dashboard. */
export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Dashboard render error', error, info.componentStack)
  }

  render() {
    const { error } = this.state
    if (!error) return this.props.children
    return (
      <main role="alert" className="mx-auto max-w-lg p-8 text-center">
        <h1 className="text-lg font-semibold">{i18n.t('crash.title')}</h1>
        <p className="mt-2 text-sm text-slate-500">{i18n.t('crash.body')}</p>
        <pre className="mt-3 overflow-x-auto rounded bg-slate-100 p-2 text-left text-xs dark:bg-slate-800">{error.message}</pre>
        <button
          type="button"
          onClick={() => window.location.assign('/')}
          className="mt-4 rounded-md bg-cyan-700 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-800"
        >
          {i18n.t('crash.reload')}
        </button>
      </main>
    )
  }
}

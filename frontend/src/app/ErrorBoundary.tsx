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
        <h1 className="font-display text-lg font-bold">{i18n.t('crash.title')}</h1>
        <p className="mt-2 text-sm text-ink-dim">{i18n.t('crash.body')}</p>
        <pre className="tnum mt-3 overflow-x-auto rounded-[10px] border border-line-soft bg-surface p-2 text-left text-xs">{error.message}</pre>
        <button
          type="button"
          onClick={() => window.location.assign('/')}
          className="mt-4 rounded-[10px] bg-mist px-4 py-2 font-display text-sm font-bold text-mist-ink hover:bg-mist-strong"
        >
          {i18n.t('crash.reload')}
        </button>
      </main>
    )
  }
}

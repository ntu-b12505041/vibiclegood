import { useCallback, useEffect, useState } from 'react'
import { api, ApiError, type Success } from '../api'
import { useAuth } from '../auth'

type Result<T> = { status: 'loading' }
  | { status: 'error'; error: Error }
  | { status: 'ready'; result: Success<T> }

export function useRequest<T>(url: string, privateData = false) {
  const { currentEpoch, refresh } = useAuth()
  const [retry, setRetry] = useState(0)
  const reload = useCallback(() => setRetry(value => value + 1), [])
  const [stored, setStored] = useState<{ url: string; retry: number; result: Result<T> }>()
  useEffect(() => {
    const controller = new AbortController()
    const generation = currentEpoch()
    const canApply = () => !controller.signal.aborted && (!privateData || currentEpoch() === generation)
    api<T>(url, { signal: AbortSignal.any([controller.signal, AbortSignal.timeout(15_000)]) })
      .then(result => {
        if (!canApply()) return
        if (privateData && result.meta.session.requires_revalidation) {
          void refresh()
          return
        }
        setStored({ url, retry, result: { status: 'ready', result } })
      })
      .catch((reason: unknown) => {
        if (!canApply()) return
        if (privateData && reason instanceof ApiError && reason.status === 401) {
          void refresh()
          return
        }
        const error = reason instanceof Error ? reason : new Error('無法連線，請稍後重試。')
        setStored({ url, retry, result: { status: 'error', error } })
      })
    return () => controller.abort()
    // currentEpoch reads a ref. Private components remount on Epoch changes.
  }, [url, retry, privateData, refresh, currentEpoch])
  return {
    state: stored?.url === url && stored.retry === retry ? stored.result : { status: 'loading' } as const,
    reload,
  }
}

export function useFocusReload(reload: () => void) {
  useEffect(() => {
    const restore = (event: PageTransitionEvent) => { if (event.persisted) reload() }
    window.addEventListener('focus', reload)
    window.addEventListener('pageshow', restore)
    return () => {
      window.removeEventListener('focus', reload)
      window.removeEventListener('pageshow', restore)
    }
  }, [reload])
}

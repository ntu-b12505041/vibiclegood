import { useEffect, useRef, useState } from 'react'
import { api, ApiError, type Success } from '../api'
import { useAuth } from '../auth'

export function useMutation() {
  const auth = useAuth()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const active = useRef(true)
  const working = useRef(false)
  useEffect(() => {
    active.current = true
    return () => { active.current = false }
  }, [])

  async function submit<T>(
    path: string, method: string, body: object, saved: (response: Success<T>) => void,
  ) {
    if (working.current) return
    working.current = true
    const epoch = auth.currentEpoch()
    const sameIdentity = () => active.current && auth.currentEpoch() === epoch
    setBusy(true)
    setError(null)
    let sent = false
    try {
      const token = await auth.mutationToken()
      if (!sameIdentity()) return
      sent = true
      const response = await api<T>(path, { method, csrf: token, body })
      if (!sameIdentity()) return
      if (response.meta.session.requires_revalidation) {
        // The mutation already succeeded; a session failure is not a failed save.
        window.dispatchEvent(new Event('vibicle:save-confirmed-revalidate'))
        void auth.refresh()
        return
      }
      saved(response)
    } catch (reason) {
      if (!sameIdentity()) return
      if (reason instanceof ApiError && reason.status === 401) {
        void auth.refresh()
      } else if (!sent) {
        setError(new Error('無法確認登入或安全驗證，表單尚未送出。'))
      } else if (reason instanceof ApiError && reason.outcome === 'not_applied') {
        setError(reason)
      } else {
        setError(new Error('無法確認是否已儲存。請先重新讀取資料再決定是否重送。'))
      }
    } finally {
      working.current = false
      if (sameIdentity()) setBusy(false)
    }
  }
  return { busy, error, submit }
}

import {
  createContext, useCallback, useContext, useEffect, useMemo, useRef, useState,
  type ReactNode,
} from 'react'
import { api, ApiError, fetchIdentity, type User } from './api'

const LOCK = 'vibicle:auth:v1'
const MARKER = 'vibicle:auth:pending:v1'
type Operation = 'bootstrap' | 'login' | 'register' | 'logout'
type Pending = { id: string; operation: Operation; startedAt: number }
type State = { kind: 'checking' | 'anonymous' | 'pending' | 'uncertain' | 'error' }
  | { kind: 'authenticated'; user: User }
type Csrf = { context_type: 'preauth' | 'authenticated'; csrf_token: string }
type Auth = {
  state: State
  epoch: number
  refresh: () => Promise<void>
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, confirmation: string) => Promise<void>
  logout: () => Promise<void>
  retryLogout: (() => Promise<void>) | null
  mutationToken: () => Promise<string>
  currentEpoch: () => number
  currentAuthBoundary: () => number
}
const Context = createContext<Auth | null>(null)

function marker(): Pending | null {
  const raw = localStorage.getItem(MARKER)
  if (raw === null) return null
  const value = JSON.parse(raw)
  if (typeof value?.id !== 'string' || typeof value?.startedAt !== 'number'
    || !['bootstrap', 'login', 'register', 'logout'].includes(value?.operation)) {
    throw new Error('本機登入狀態需要人工確認。')
  }
  return value
}

function knownFailure(error: unknown): boolean {
  return error instanceof ApiError && error.outcome === 'not_applied'
}

function validCsrf(token: unknown): token is string {
  return typeof token === 'string' && /^[A-Za-z0-9_-]{42}[AEIMQUYcgkosw048]$/.test(token)
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<State>({ kind: 'checking' })
  const [epoch, setEpoch] = useState(0)
  const generation = useRef(0)
  const authBoundary = useRef(0)
  const channel = useRef<BroadcastChannel | null>(null)
  const csrf = useRef<string | null>(null)
  const logoutRetry = useRef<{ pendingId: string; token: string } | null>(null)
  const currentEpoch = useCallback(() => generation.current, [])
  const currentAuthBoundary = useCallback(() => authBoundary.current, [])
  const refreshRequest = useRef<AbortController | null>(null)
  const invalidate = useCallback((kind: 'checking' | 'pending', focusOnly = false) => {
    refreshRequest.current?.abort()
    generation.current += 1
    if (!focusOnly) authBoundary.current = generation.current
    csrf.current = null
    setEpoch(generation.current)
    setState({ kind })
  }, [])

  const confirmIdentity = useCallback(async () => {
    const expected = generation.current
    refreshRequest.current?.abort()
    const controller = new AbortController()
    refreshRequest.current = controller
    try {
      const { data } = await fetchIdentity(
        AbortSignal.any([controller.signal, AbortSignal.timeout(10_000)]),
      )
      if (expected !== generation.current || controller.signal.aborted) return
      setState(data.authenticated ? { kind: 'authenticated', user: data.user } : { kind: 'anonymous' })
    } catch {
      if (expected === generation.current && !controller.signal.aborted) setState({ kind: 'error' })
    }
  }, [])

  const refresh = useCallback(async (focusOnly = false) => {
    invalidate('checking', focusOnly)
    const recheck = async () => {
      try {
        if (marker()) {
          setState({ kind: 'uncertain' })
          return
        }
      } catch {
        setState({ kind: 'uncertain' })
        return
      }
      await confirmIdentity()
    }
    if (navigator.locks) await navigator.locks.request(LOCK, recheck)
    else await recheck()
  }, [confirmIdentity, invalidate])

  useEffect(() => {
    if ('BroadcastChannel' in window) channel.current = new BroadcastChannel(LOCK)
    const onStorage = (event: StorageEvent) => {
      if (event.key === MARKER) void refresh()
    }
    const onMessage = (event: MessageEvent) => {
      if (event.data === 'invalidate') invalidate('pending')
      if (event.data === 'settled') void refresh()
    }
    const recheck = () => { void refresh() }
    const onFocus = () => { void refresh(true) }
    channel.current?.addEventListener('message', onMessage)
    window.addEventListener('storage', onStorage)
    window.addEventListener('focus', onFocus)
    window.addEventListener('pageshow', recheck)
    void refresh()
    return () => {
      channel.current?.close()
      channel.current = null
      window.removeEventListener('storage', onStorage)
      window.removeEventListener('focus', onFocus)
      window.removeEventListener('pageshow', recheck)
      refreshRequest.current?.abort()
    }
  }, [invalidate, refresh])

  const run = useCallback(async (
    operation: Operation, work: (token: string) => Promise<void>,
  ) => {
    if (!navigator.locks || !channel.current) {
      throw new Error('此瀏覽器無法協調分頁登入。請使用支援 Web Locks 與 BroadcastChannel 的瀏覽器。')
    }
    await navigator.locks.request(LOCK, async () => {
      try {
        if (marker()) {
          setState({ kind: 'uncertain' })
          throw new Error('上一次登入操作尚未確認。')
        }
      } catch (error) {
        setState({ kind: 'uncertain' })
        throw error
      }
      const savedCsrf = csrf.current
      const pending = { id: crypto.randomUUID(), operation, startedAt: Date.now() }
      try {
        localStorage.setItem(MARKER, JSON.stringify(pending))
      } catch {
        throw new Error('本機儲存不可用，已停用登入操作。')
      }
      invalidate('pending')
      channel.current?.postMessage('invalidate')
      let registrationDispatched = false
      try {
        let token = savedCsrf
        if (!token) {
          const { data } = await api<Csrf>('/api/auth/csrf')
          if (!validCsrf(data?.csrf_token)) throw new Error('無法確認安全驗證結果。')
          token = data.csrf_token
        }
        if (operation === 'logout') logoutRetry.current = { pendingId: pending.id, token }
        registrationDispatched = operation === 'register'
        await work(token)
        localStorage.removeItem(MARKER)
        logoutRetry.current = null
        await confirmIdentity()
      } catch (error) {
        if (knownFailure(error) || registrationDispatched) {
          localStorage.removeItem(MARKER)
          logoutRetry.current = null
          await confirmIdentity()
          if (!knownFailure(error) && registrationDispatched) {
            // E02 never writes a cookie. The account may exist, so allow manual sign-in.
            throw new Error('註冊結果尚未確認。可手動嘗試登入，請勿直接重送註冊。')
          }
        } else {
          setState({ kind: 'uncertain' })
        }
        throw error
      } finally {
        channel.current?.postMessage('settled')
      }
    })
  }, [confirmIdentity, invalidate])

  const auth = useMemo<Auth>(() => ({
    state, epoch, refresh,
    currentEpoch, currentAuthBoundary,
    login: (email, password) => run('login', async token => {
      const { data } = await api<{ authenticated: true; user: User; csrf_token: string }>(
        '/api/auth/login', { method: 'POST', csrf: token, body: { email, password } },
      )
      if (!data?.authenticated || !validCsrf(data.csrf_token) || typeof data.user?.id !== 'string') {
        throw new Error('無法確認登入結果。')
      }
      csrf.current = data.csrf_token
    }),
    register: (email, password, confirmation) => run('register', async token => {
      const { data } = await api<{ status: string; next: string }>('/api/auth/register', {
        method: 'POST', csrf: token, body: { email, password, password_confirmation: confirmation },
      })
      if (data?.status !== 'registered' || data.next !== 'manual_login') {
        throw new Error('無法確認註冊結果。')
      }
      csrf.current = token
    }),
    logout: () => run('logout', async token => {
      const result = await api('/api/auth/logout', { method: 'POST', csrf: token })
      if (result !== undefined) throw new Error('無法確認登出結果。')
    }),
    retryLogout: state.kind === 'uncertain' && logoutRetry.current ? async () => {
      const proof = logoutRetry.current
      if (!proof || !navigator.locks) return
      await navigator.locks.request(LOCK, async () => {
        const pending = marker()
        if (pending?.operation !== 'logout' || pending.id !== proof.pendingId) {
          throw new Error('登入狀態已變更，無法重送原登出。')
        }
        // Only the previous in-memory token is accepted; never bootstrap a new context.
        const result = await api('/api/auth/logout', { method: 'POST', csrf: proof.token })
        if (result !== undefined) throw new Error('無法確認登出結果。')
        localStorage.removeItem(MARKER)
        logoutRetry.current = null
        channel.current?.postMessage('settled')
        await confirmIdentity()
      })
    } : null,
    mutationToken: async () => {
      if (!navigator.locks || !channel.current || state.kind !== 'authenticated') {
        throw new Error('請先確認登入身分，並使用支援分頁協調的瀏覽器。')
      }
      const expectedUser = state.user.id
      const expected = generation.current
      return navigator.locks.request(LOCK, async () => {
        if (marker() || generation.current !== expected) throw new Error('登入狀態已變更。')
        if (!csrf.current) {
          // A potentially cookie-writing E01 always has a durable pending marker.
          localStorage.setItem(MARKER, JSON.stringify({
            id: crypto.randomUUID(), operation: 'bootstrap', startedAt: Date.now(),
          }))
          let data: Csrf
          try {
            ({ data } = await api<Csrf>('/api/auth/csrf'))
            if (!validCsrf(data?.csrf_token)) throw new Error('無法確認安全驗證結果。')
            localStorage.removeItem(MARKER)
          } catch (error) {
            if (knownFailure(error)) localStorage.removeItem(MARKER)
            else setState({ kind: 'uncertain' })
            throw error
          }
          const { data: identity } = await fetchIdentity()
          if (data.context_type !== 'authenticated' || identity.user?.id !== expectedUser
            || generation.current !== expected) {
            void refresh()
            throw new Error('登入狀態已失效，請重新確認。')
          }
          csrf.current = data.csrf_token
        }
        return csrf.current
      })
    },
  }), [state, epoch, refresh, run, confirmIdentity, currentEpoch, currentAuthBoundary])
  return <Context.Provider value={auth}>{children}</Context.Provider>
}

export function useAuth(): Auth {
  const auth = useContext(Context)
  if (!auth) throw new Error('AuthProvider is required')
  return auth
}

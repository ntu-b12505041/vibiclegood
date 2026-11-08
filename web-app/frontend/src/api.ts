export type User = { id: string; email: string }
export type Identity =
  | { authenticated: false; user: null; absolute_expires_at: null }
  | { authenticated: true; user: User; absolute_expires_at: string }

export type SessionMeta = {
  activity: 'not_applicable' | 'not_touched' | 'touched' | 'not_extended' | 'unknown'
  requires_revalidation: boolean
  reason: string | null
}

export type Success<T> = {
  data: T
  meta: {
    request_id: string
    business_outcome: 'read_only' | 'committed' | 'unchanged'
    session: SessionMeta
  }
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly outcome: 'not_applied' | 'unknown',
    readonly requestId?: string,
    readonly details?: Record<string, unknown>,
  ) {
    super(message)
  }
}

export async function api<T>(
  path: string,
  init?: { method?: string; body?: object; csrf?: string; signal?: AbortSignal },
): Promise<Success<T>> {
  const headers = new Headers()
  let body: string | FormData | undefined
  if (init?.body instanceof FormData) body = init.body
  else if (init?.body) {
    body = JSON.stringify(init.body)
    headers.set('Content-Type', 'application/json')
  }
  if (init?.csrf) headers.set('X-CSRF-Token', init.csrf)
  const response = await fetch(path, {
    credentials: 'same-origin',
    cache: 'no-store',
    method: init?.method,
    headers,
    body,
    signal: init?.signal ?? AbortSignal.timeout(15_000),
    redirect: 'error',
  })
  if (response.status === 204) return undefined as unknown as Success<T>
  const value = await response.json().catch(() => null)
  if (!response.ok) {
    const error = value?.error
    const known = typeof error?.code === 'string' && typeof error?.message === 'string'
      && (error?.outcome === 'not_applied' || error?.outcome === 'unknown')
      && typeof value?.meta?.request_id === 'string'
    throw new ApiError(
      response.status, known ? error.code : 'TRANSPORT_OUTCOME_UNKNOWN',
      known ? error.message : `API 回應 HTTP ${response.status}，無法確認結果。`,
      known ? error.outcome : 'unknown', value?.meta?.request_id, error?.details,
    )
  }
  if (typeof value?.meta?.request_id !== 'string'
    || typeof value.meta.session?.requires_revalidation !== 'boolean'
    || !Object.hasOwn(value, 'data')) throw new Error('API Response 不符合 Contract。')
  return value as Success<T>
}

export async function fetchIdentity(signal?: AbortSignal): Promise<Success<Identity>> {
  const result = await api<Identity>('/api/auth/me', { signal })
  const { data, meta } = result
  const anonymous = data?.authenticated === false && data.user === null
    && data.absolute_expires_at === null && meta.session.activity === 'not_applicable'
  const authenticated = data?.authenticated === true && typeof data.user?.id === 'string'
    && typeof data.user.email === 'string' && typeof data.absolute_expires_at === 'string'
    && meta.session.activity === 'not_touched'
  if ((!anonymous && !authenticated) || meta.business_outcome !== 'read_only'
    || meta.session.requires_revalidation || meta.session.reason !== null) {
    throw new Error('API Response 不符合 E05 Contract。')
  }
  return result
}

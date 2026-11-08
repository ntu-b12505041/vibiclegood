import { afterEach, expect, it, vi } from 'vitest'
import { fetchIdentity } from './api'

afterEach(() => vi.unstubAllGlobals())

it('reads the contracted anonymous response through a relative same-origin URL', async () => {
  const body = {
    data: { authenticated: false, user: null, absolute_expires_at: null },
    meta: {
      request_id: '11111111-1111-4111-8111-111111111111', business_outcome: 'read_only',
      session: { activity: 'not_applicable', requires_revalidation: false, reason: null },
    },
  }
  const mock = vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status: 200 }))
  vi.stubGlobal('fetch', mock)
  await expect(fetchIdentity(new AbortController().signal)).resolves.toEqual(body)
  expect(mock).toHaveBeenCalledWith('/api/auth/me', expect.objectContaining({
    credentials: 'same-origin', cache: 'no-store',
  }))
})

it('does not turn a 503 into an anonymous success', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 503 })))
  await expect(fetchIdentity(new AbortController().signal)).rejects.toThrow('HTTP 503')
})

it('rejects an authenticated response missing the required identity and metadata', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
    JSON.stringify({ data: { authenticated: true, user: { id: 'forged' } } }),
    { status: 200 },
  )))
  await expect(fetchIdentity(new AbortController().signal)).rejects.toThrow('Contract')
})

it('preserves unknown commit outcome for gateway or application errors', async () => {
  const { api } = await import('./api')
  const fetcher = vi.fn()
    .mockResolvedValueOnce(new Response('upstream timeout', { status: 504 }))
    .mockResolvedValueOnce(new Response(JSON.stringify({
      error: { code: 'COMMIT_OUTCOME_UNKNOWN', message: '無法確認', outcome: 'unknown' },
      meta: { request_id: 'evidence-id' },
    }), { status: 503 }))
  vi.stubGlobal('fetch', fetcher)
  await expect(api('/api/vehicles', { method: 'POST', csrf: 'test', body: {} }))
    .rejects.toMatchObject({ code: 'TRANSPORT_OUTCOME_UNKNOWN', outcome: 'unknown' })
  await expect(api('/api/vehicles', { method: 'POST', csrf: 'test', body: {} }))
    .rejects.toMatchObject({ code: 'COMMIT_OUTCOME_UNKNOWN', outcome: 'unknown' })
  expect(fetcher).toHaveBeenCalledTimes(2)
})

it('preserves committed business success even when session touch is unknown', async () => {
  const { api } = await import('./api')
  const value = {
    data: { id: 'vehicle-1' },
    meta: {
      request_id: 'evidence-id', business_outcome: 'committed',
      session: { activity: 'unknown', requires_revalidation: true, reason: 'SESSION_STORE_UNAVAILABLE' },
    },
  }
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(value), { status: 201 })))
  await expect(api('/api/vehicles', { method: 'POST', csrf: 'test', body: {} })).resolves.toEqual(value)
})

import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiFailure } from './api'

describe('api client', () => {
  afterEach(() => vi.restoreAllMocks())

  it('returns JSON data for a successful response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({status: 'ok'}), {status: 200, headers: {'content-type': 'application/json'}})))
    await expect(api<{status: string}>('/api/health')).resolves.toEqual({status: 'ok'})
  })

  it('preserves the user-facing error and request id', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({detail: {message: '请先登录'}}), {status: 401, headers: {'content-type': 'application/json', 'x-request-id': 'req-demo'}})))
    await expect(api('/api/dashboard')).rejects.toMatchObject({message: '请先登录', status: 401, requestId: 'req-demo'})
  })
})

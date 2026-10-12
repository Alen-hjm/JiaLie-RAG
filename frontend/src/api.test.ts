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

  it('does not expose infrastructure details from a failed service', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({detail: {message: 'Embedding provider API key error: https://internal.example'}}), {status: 500, headers: {'content-type': 'application/json', 'x-request-id': 'req-failed'}})))
    await expect(api('/api/conversations')).rejects.toMatchObject({message: '服务暂时繁忙，请稍后重试；若持续失败，请联系服务负责人。', status: 500, requestId: 'req-failed'})
  })

  it('provides an actionable message when the network is unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(api('/api/dashboard')).rejects.toMatchObject({message: '暂时无法连接，请检查网络后重试。', status: 0})
  })
})

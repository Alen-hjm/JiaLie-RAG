export type Candidate = {
  id: string; name: string; location?: string; current_title?: string;
  years_experience: number; industries: string[]; skills: string[];
  management_experience: boolean;
}

export type Requirements = {
  company?: string; title: string; industries: string[]; locations: string[]; minimum_years: number;
  skills: string[]; management_required: boolean; must_have: string[];
  preferred: string[]; performance_expectations: string[];
}

export type Match = {
  id: string; total_score: number; structured_score: number; semantic_score: number;
  rerank_score: number; rerank_mode?: 'rule' | 'llm'; strengths: string[]; gaps: string[];
  evidence: Array<{chunk_id: string; section: string; page_number?: number; quote: string}>;
  candidate: Candidate;
}

export type ConversationSummary = {id: string; title: string; requirements: Requirements; updated_at: string; job_id?: string}
export type OrchestrationStep = {node: string; detail?: string; verdict?: string}
export type OrchestrationInfo = {mode: string; attempts?: number; steps: OrchestrationStep[]}
export type ConversationResponse = {assistant_text?: string; requirements?: Requirements; items?: Match[]; total?: number; follow_up_suggestions?: string[]; orchestration?: OrchestrationInfo}
export type ConversationMessage = {id: string; role: 'user'|'assistant'; content: string; response?: ConversationResponse; created_at: string}
export type Conversation = {id: string; title: string; requirements: Requirements; messages: ConversationMessage[]; updated_at: string}
export type VectorStats = {
  total_chunks: number; missing_vectors: number; dimension_counts: Record<string, number>;
  expected_dimension: number; mismatched_vectors: number; needs_reindex: boolean;
}

export type AppSettings = {
  model_mode: string; base_url: string; chat_model: string; timeout_seconds: number;
  api_key_configured: boolean; api_key_masked: string;
  // Embeddings are configured separately: the chat provider (DeepSeek) has no
  // public embeddings endpoint, so a placeholder backend is the default.
  embedding_provider: string; embedding_mode: string; embedding_base_url: string;
  embedding_model: string; embedding_dimensions: number;
  embedding_key_configured: boolean; embedding_key_masked: string;
  embedding_is_placeholder: boolean; embedding_label: string;
  vectors: VectorStats;
  // Final-stage rerank: which judge produced the 20% relevance score.
  rerank_mode: 'rule' | 'llm'; rerank_top_n: number; rerank_effective: 'rule' | 'llm';
}

export class ApiFailure extends Error {
  constructor(message: string, public status: number, public requestId?: string) { super(message) }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body && !(options.body instanceof FormData)) headers.set('content-type', 'application/json')
  let response: Response
  try { response = await fetch(path, {...options, headers, credentials: 'include'}) }
  catch { throw new ApiFailure('暂时无法连接，请检查网络后重试。', 0) }
  if (!response.ok) {
    let message = '操作未完成，请稍后重试。'
    try {
      const body = await response.json()
      const detail = body.detail?.message || body.message
      if (typeof detail === 'string' && !/api|key|token|sql|traceback|embedding|向量|模型|http|exception|error|\.env|provider|timeout/i.test(detail) && response.status < 500) message = detail
    } catch { /* use fallback */ }
    if (response.status >= 500) message = '服务暂时繁忙，请稍后重试；若持续失败，请联系服务负责人。'
    if (response.status === 429) message = '操作较频繁，请稍等片刻再试。'
    if (response.status === 413) message = '文件过大，请缩小文件后重新上传。'
    if (response.status === 422) message = '请检查填写内容或上传的文件后重试。'
    throw new ApiFailure(message, response.status, response.headers.get('x-request-id') || undefined)
  }
  if (response.status === 204) return undefined as T
  return response.json()
}

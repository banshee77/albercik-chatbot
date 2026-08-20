import { request } from './client'
import type { ConversationDetail, ConversationListParams, ConversationListResponse } from './types'

export async function listConversations(
  params: ConversationListParams = {},
): Promise<ConversationListResponse> {
  const query = new URLSearchParams()
  if (params.q) query.set('q', params.q)
  if (params.outcome) query.set('outcome', params.outcome)
  if (params.start_date) query.set('start_date', params.start_date)
  if (params.end_date) query.set('end_date', params.end_date)
  if (params.limit !== undefined) query.set('limit', String(params.limit))
  if (params.offset !== undefined) query.set('offset', String(params.offset))

  const qs = query.toString()
  return request<ConversationListResponse>(
    `/api/v1/admin/conversations${qs ? `?${qs}` : ''}`,
  )
}

export async function getConversation(id: string): Promise<ConversationDetail> {
  return request<ConversationDetail>(`/api/v1/admin/conversations/${id}`)
}

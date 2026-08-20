export interface AdministratorIdentity {
  id: string
  username: string
}

export interface OrganizationIdentity {
  id: string
  name: string
  slug: string
}

export interface ApiError {
  message: string
  status?: number
}

export type DocumentStatus = 'processing' | 'ready' | 'failed'

export interface DocumentSummary {
  id: string
  filename: string
  content_type: string
  status: DocumentStatus
  uploaded_at: string
  updated_at: string
  indexed_at: string | null
  error_message: string | null
}

export interface DocumentCounts {
  total: number
  ready: number
  processing: number
  failed: number
}

export interface KnowledgeHealthSummary {
  documents: DocumentCounts
  chunks: number
  ready_for_chat: boolean
  last_indexed_at: string | null
}

export type ConversationOutcome =
  | 'grounded'
  | 'insufficient_information'
  | 'out_of_scope'
  | 'unavailable'
  | 'small_talk'

export interface ConversationSummary {
  id: string
  request_id: string
  question: string
  outcome: ConversationOutcome
  created_at: string
  latency_ms: number
}

export interface ConversationListResponse {
  items: ConversationSummary[]
  total: number
  limit: number
  offset: number
}

export interface ConversationListParams {
  q?: string
  outcome?: ConversationOutcome
  start_date?: string
  end_date?: string
  limit?: number
  offset?: number
}

export interface ConversationSource {
  document_id: string
  label: string
}

/** Never `provider_metrics` — deliberately excluded (research.md R4, FR-037). */
export type SafeFailureCategory =
  | 'provider_error'
  | 'budget_exceeded'
  | 'kill_switch'
  | 'concurrency_limit'

export interface ConversationDetail {
  id: string
  request_id: string
  question: string
  answer: string
  outcome: ConversationOutcome
  created_at: string
  latency_ms: number
  sources: ConversationSource[] | null
  provider_name: string | null
  provider_model: string | null
  input_tokens: number | null
  output_tokens: number | null
  safe_failure_category: SafeFailureCategory | null
}

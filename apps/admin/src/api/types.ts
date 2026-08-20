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

import { request } from './client'
import type { DocumentSummary, KnowledgeHealthSummary } from './types'

export async function listDocuments(): Promise<DocumentSummary[]> {
  return request<DocumentSummary[]>('/api/v1/documents')
}

export async function getKnowledgeHealth(): Promise<KnowledgeHealthSummary> {
  return request<KnowledgeHealthSummary>('/api/v1/documents/health')
}

export async function getDocument(id: string): Promise<DocumentSummary> {
  return request<DocumentSummary>(`/api/v1/documents/${id}`)
}

export async function uploadDocument(file: File): Promise<DocumentSummary> {
  const body = new FormData()
  body.append('file', file)
  return request<DocumentSummary>('/api/v1/documents', { method: 'POST', body })
}

export async function replaceDocument(id: string, file: File): Promise<DocumentSummary> {
  const body = new FormData()
  body.append('file', file)
  return request<DocumentSummary>(`/api/v1/documents/${id}/replace`, { method: 'POST', body })
}

export async function reindexDocument(id: string): Promise<DocumentSummary> {
  return request<DocumentSummary>(`/api/v1/documents/${id}/reindex`, { method: 'POST' })
}

export async function deleteDocument(id: string): Promise<void> {
  return request<void>(`/api/v1/documents/${id}`, { method: 'DELETE' })
}

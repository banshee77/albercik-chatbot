import { useEffect, useState } from 'react'
import {
  deleteDocument,
  getKnowledgeHealth,
  listDocuments,
  reindexDocument,
  replaceDocument,
  uploadDocument,
} from '../api/knowledge'
import type { ApiError, DocumentSummary, KnowledgeHealthSummary } from '../api/types'
import { DocumentDetailPanel } from '../components/knowledge/DocumentDetailPanel'
import { DocumentTable } from '../components/knowledge/DocumentTable'
import { HealthSummary } from '../components/knowledge/HealthSummary'
import { statusLabel } from '../components/knowledge/statusLabel'
import { UploadControl } from '../components/knowledge/UploadControl'
import { ErrorMessage } from '../components/ErrorMessage'
import { LoadingState } from '../components/LoadingState'
import { usePageTitle } from '../hooks/usePageTitle'

type PageStatus = 'loading' | 'loaded' | 'error'

interface PendingAction {
  kind: 'upload' | 'replace' | 'reindex' | 'delete'
  documentId?: string
}

interface MutationFeedback {
  kind: 'success' | 'error'
  text: string
}

const LOAD_FAILURE_MESSAGE = "Couldn't load your knowledge base. Please try again."
const GENERIC_MUTATION_ERROR = 'Something went wrong. Please try again.'

function isApiError(value: unknown): value is ApiError {
  return typeof value === 'object' && value !== null && 'message' in value
}

function errorMessageFrom(err: unknown): string {
  return isApiError(err) ? err.message : GENERIC_MUTATION_ERROR
}

export function KnowledgePage() {
  usePageTitle('Knowledge')

  const [status, setStatus] = useState<PageStatus>('loading')
  const [documents, setDocuments] = useState<DocumentSummary[]>([])
  const [health, setHealth] = useState<KnowledgeHealthSummary | null>(null)
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null)
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null)
  const [feedback, setFeedback] = useState<MutationFeedback | null>(null)

  async function reloadKnowledge(): Promise<void> {
    try {
      const [nextDocuments, nextHealth] = await Promise.all([listDocuments(), getKnowledgeHealth()])
      setDocuments(nextDocuments)
      setHealth(nextHealth)
      setStatus('loaded')
    } catch {
      setStatus('error')
    }
  }

  useEffect(() => {
    // reloadKnowledge's setState calls happen asynchronously after the
    // fetch resolves, not synchronously within this effect body — the
    // standard fetch-on-mount pattern.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    reloadKnowledge()
  }, [])

  async function handleUpload(file: File): Promise<void> {
    setPendingAction({ kind: 'upload' })
    setFeedback(null)
    try {
      const uploaded = await uploadDocument(file)
      await reloadKnowledge()
      setFeedback({
        kind: 'success',
        text: `"${uploaded.filename}" uploaded — status: ${statusLabel(uploaded.status)}.`,
      })
    } catch (err) {
      setFeedback({ kind: 'error', text: errorMessageFrom(err) })
    } finally {
      setPendingAction(null)
    }
  }

  async function handleReindex(documentId: string): Promise<void> {
    setPendingAction({ kind: 'reindex', documentId })
    setFeedback(null)
    try {
      await reindexDocument(documentId)
      await reloadKnowledge()
      setFeedback({ kind: 'success', text: 'Search index rebuilt.' })
    } catch (err) {
      setFeedback({ kind: 'error', text: errorMessageFrom(err) })
    } finally {
      setPendingAction(null)
    }
  }

  async function handleReplace(documentId: string, file: File): Promise<void> {
    setPendingAction({ kind: 'replace', documentId })
    setFeedback(null)
    try {
      await replaceDocument(documentId, file)
      await reloadKnowledge()
      setSelectedDocumentId(null)
      setFeedback({ kind: 'success', text: 'Document replaced.' })
    } catch (err) {
      setFeedback({ kind: 'error', text: errorMessageFrom(err) })
    } finally {
      setPendingAction(null)
    }
  }

  async function handleDelete(documentId: string): Promise<void> {
    setPendingAction({ kind: 'delete', documentId })
    setFeedback(null)
    try {
      await deleteDocument(documentId)
      await reloadKnowledge()
      setSelectedDocumentId((current) => (current === documentId ? null : current))
      setFeedback({ kind: 'success', text: 'Document deleted.' })
    } catch (err) {
      setFeedback({ kind: 'error', text: errorMessageFrom(err) })
    } finally {
      setPendingAction(null)
    }
  }

  if (status === 'loading') {
    return <LoadingState label="Loading your knowledge base…" />
  }

  if (status === 'error') {
    return (
      <div>
        <ErrorMessage message={LOAD_FAILURE_MESSAGE} />
        <button type="button" onClick={reloadKnowledge}>
          Retry
        </button>
      </div>
    )
  }

  const selectedDocument = documents.find((document) => document.id === selectedDocumentId) ?? null
  const isUploading = pendingAction?.kind === 'upload'

  return (
    <div>
      <h1>Knowledge</h1>
      {health && <HealthSummary health={health} />}
      <UploadControl onUpload={handleUpload} isUploading={isUploading} />
      {feedback && (
        <p role={feedback.kind === 'error' ? 'alert' : 'status'}>{feedback.text}</p>
      )}
      {documents.length === 0 ? (
        <p>No knowledge has been added yet.</p>
      ) : (
        <DocumentTable
          documents={documents}
          selectedDocumentId={selectedDocumentId}
          onSelect={setSelectedDocumentId}
        />
      )}
      {selectedDocument && (
        <DocumentDetailPanel
          document={selectedDocument}
          onReindex={handleReindex}
          onReplace={handleReplace}
          onDelete={handleDelete}
          isReindexing={
            pendingAction?.kind === 'reindex' && pendingAction.documentId === selectedDocument.id
          }
          isReplacing={
            pendingAction?.kind === 'replace' && pendingAction.documentId === selectedDocument.id
          }
          isDeleting={
            pendingAction?.kind === 'delete' && pendingAction.documentId === selectedDocument.id
          }
        />
      )}
    </div>
  )
}

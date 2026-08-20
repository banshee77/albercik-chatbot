import { useEffect, useRef, useState } from 'react'
import type { DocumentSummary } from '../../api/types'
import { StatusBadge } from './StatusBadge'
import { ReplaceDialog } from './ReplaceDialog'
import { DeleteDialog } from './DeleteDialog'

interface DocumentDetailPanelProps {
  document: DocumentSummary
  onReindex: (id: string) => void
  onReplace: (id: string, file: File) => void
  onDelete: (id: string) => void
  isReindexing: boolean
  isReplacing: boolean
  isDeleting: boolean
}

/** Closes a dialog once its own in-flight submission settles (success or
 * failure) — the dialog stays open (with its controls disabled by
 * `isSubmitting`) for the duration of the request, rather than closing
 * instantly on click, so "disable while in flight" is actually visible. */
function useCloseWhenSettled(isOpen: boolean, isSubmitting: boolean, close: () => void): void {
  const wasSubmittingRef = useRef(false)
  useEffect(() => {
    if (isOpen && wasSubmittingRef.current && !isSubmitting) {
      close()
    }
    wasSubmittingRef.current = isSubmitting
  }, [isOpen, isSubmitting, close])
}

export function DocumentDetailPanel({
  document,
  onReindex,
  onReplace,
  onDelete,
  isReindexing,
  isReplacing,
  isDeleting,
}: DocumentDetailPanelProps) {
  const [isReplaceDialogOpen, setReplaceDialogOpen] = useState(false)
  const [isDeleteDialogOpen, setDeleteDialogOpen] = useState(false)

  useCloseWhenSettled(isReplaceDialogOpen, isReplacing, () => setReplaceDialogOpen(false))
  useCloseWhenSettled(isDeleteDialogOpen, isDeleting, () => setDeleteDialogOpen(false))

  return (
    <section aria-label={`Document detail: ${document.filename}`}>
      <h2>{document.filename}</h2>
      <dl>
        <dt>Status</dt>
        <dd>
          <StatusBadge status={document.status} />
        </dd>
        <dt>Content type</dt>
        <dd>{document.content_type}</dd>
        <dt>Uploaded</dt>
        <dd>{new Date(document.uploaded_at).toLocaleString()}</dd>
        <dt>Updated</dt>
        <dd>{new Date(document.updated_at).toLocaleString()}</dd>
        {document.indexed_at && (
          <>
            <dt>Indexed</dt>
            <dd>{new Date(document.indexed_at).toLocaleString()}</dd>
          </>
        )}
      </dl>
      {document.status === 'failed' && document.error_message && (
        <p role="alert">{document.error_message}</p>
      )}
      <div>
        {document.status !== 'processing' && (
          <button type="button" onClick={() => onReindex(document.id)} disabled={isReindexing}>
            Rebuild search index
          </button>
        )}
        <button type="button" onClick={() => setReplaceDialogOpen(true)} disabled={isReplacing}>
          Replace
        </button>
        <button type="button" onClick={() => setDeleteDialogOpen(true)} disabled={isDeleting}>
          Delete
        </button>
      </div>
      <ReplaceDialog
        isOpen={isReplaceDialogOpen}
        documentFilename={document.filename}
        isSubmitting={isReplacing}
        onConfirm={(file) => onReplace(document.id, file)}
        onCancel={() => setReplaceDialogOpen(false)}
      />
      <DeleteDialog
        isOpen={isDeleteDialogOpen}
        documentFilename={document.filename}
        isSubmitting={isDeleting}
        onConfirm={() => onDelete(document.id)}
        onCancel={() => setDeleteDialogOpen(false)}
      />
    </section>
  )
}

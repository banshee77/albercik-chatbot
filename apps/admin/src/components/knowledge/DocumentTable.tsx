import type { DocumentSummary } from '../../api/types'
import { StatusBadge } from './StatusBadge'

interface DocumentTableProps {
  documents: DocumentSummary[]
  selectedDocumentId: string | null
  onSelect: (id: string) => void
}

export function DocumentTable({ documents, selectedDocumentId, onSelect }: DocumentTableProps) {
  return (
    <table>
      <caption>Documents</caption>
      <thead>
        <tr>
          <th scope="col">Name</th>
          <th scope="col">Status</th>
          <th scope="col">Updated</th>
        </tr>
      </thead>
      <tbody>
        {documents.map((document) => (
          <tr key={document.id} aria-current={document.id === selectedDocumentId}>
            <th scope="row">
              <button type="button" onClick={() => onSelect(document.id)}>
                {document.filename}
              </button>
            </th>
            <td>
              <StatusBadge status={document.status} />
            </td>
            <td>{new Date(document.updated_at).toLocaleString()}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

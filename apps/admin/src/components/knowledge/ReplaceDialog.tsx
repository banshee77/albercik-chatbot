import { type ChangeEvent, useState } from 'react'
import { useDialogElement } from '../../hooks/useDialogElement'

interface ReplaceDialogProps {
  isOpen: boolean
  documentFilename: string
  isSubmitting: boolean
  onConfirm: (file: File) => void
  onCancel: () => void
}

export function ReplaceDialog({
  isOpen,
  documentFilename,
  isSubmitting,
  onConfirm,
  onCancel,
}: ReplaceDialogProps) {
  const dialogRef = useDialogElement(isOpen)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)

  function handleFileChange(event: ChangeEvent<HTMLInputElement>): void {
    setSelectedFile(event.target.files?.[0] ?? null)
  }

  function handleConfirm(): void {
    if (selectedFile) {
      onConfirm(selectedFile)
      setSelectedFile(null)
    }
  }

  return (
    <dialog ref={dialogRef} aria-label={`Replace ${documentFilename}`}>
      <h2>Replace "{documentFilename}"</h2>
      <p>
        Your current document keeps answering questions while the replacement is processed. It is
        retired only once the new document succeeds.
      </p>
      <label htmlFor="knowledge-replace-file">New file</label>
      <input id="knowledge-replace-file" type="file" accept=".txt,text/plain" onChange={handleFileChange} />
      <button type="button" onClick={onCancel} disabled={isSubmitting}>
        Cancel
      </button>
      <button type="button" onClick={handleConfirm} disabled={isSubmitting || !selectedFile}>
        Replace
      </button>
    </dialog>
  )
}

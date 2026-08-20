import { type ChangeEvent, type FormEvent, useState } from 'react'
import { LoadingState } from '../LoadingState'

interface UploadControlProps {
  onUpload: (file: File) => void
  isUploading: boolean
}

// A stable, non-configurable backend constant (_ALLOWED_EXTENSION in
// _ingest_content.py) — safe to mirror as early client-side feedback,
// unlike the operator-configurable max size (research.md R7).
const EXTENSION_ERROR = 'Only .txt files are accepted.'

export function UploadControl({ onUpload, isUploading }: UploadControlProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [extensionError, setExtensionError] = useState<string | null>(null)

  function handleFileChange(event: ChangeEvent<HTMLInputElement>): void {
    const file = event.target.files?.[0] ?? null
    setSelectedFile(file)
    setExtensionError(file && !file.name.toLowerCase().endsWith('.txt') ? EXTENSION_ERROR : null)
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault()
    if (!selectedFile || extensionError) {
      return
    }
    onUpload(selectedFile)
    setSelectedFile(null)
  }

  return (
    <form onSubmit={handleSubmit}>
      <label htmlFor="knowledge-upload-file">Upload document</label>
      <input
        id="knowledge-upload-file"
        type="file"
        accept=".txt,text/plain"
        onChange={handleFileChange}
        disabled={isUploading}
      />
      {selectedFile && <span>{selectedFile.name}</span>}
      {extensionError && (
        <span role="alert">{extensionError}</span>
      )}
      <button type="submit" disabled={isUploading || !selectedFile || Boolean(extensionError)}>
        Upload document
      </button>
      {isUploading && <LoadingState label="Uploading and indexing…" />}
    </form>
  )
}

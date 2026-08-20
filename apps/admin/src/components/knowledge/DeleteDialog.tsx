import { useDialogElement } from '../../hooks/useDialogElement'

interface DeleteDialogProps {
  isOpen: boolean
  documentFilename: string
  isSubmitting: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function DeleteDialog({
  isOpen,
  documentFilename,
  isSubmitting,
  onConfirm,
  onCancel,
}: DeleteDialogProps) {
  const dialogRef = useDialogElement(isOpen)

  return (
    <dialog ref={dialogRef} aria-label={`Delete ${documentFilename}`}>
      <h2>Delete "{documentFilename}"?</h2>
      <p>The assistant will no longer be able to use this document once it's deleted.</p>
      <button type="button" onClick={onCancel} disabled={isSubmitting}>
        Cancel
      </button>
      <button type="button" onClick={onConfirm} disabled={isSubmitting}>
        Delete
      </button>
    </dialog>
  )
}

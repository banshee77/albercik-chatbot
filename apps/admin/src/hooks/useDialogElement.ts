import { useEffect, useRef } from 'react'

const FOCUSABLE_SELECTOR =
  'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'

/** Opens/closes a native <dialog> via showModal()/close(), explicitly
 * moving focus to its first focusable control on open and restoring focus
 * to whatever triggered it on close — done explicitly rather than relying
 * on browser-default showModal() focus behavior, so it's intentional and
 * verifiable (FR-038). */
export function useDialogElement(isOpen: boolean) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const previouslyFocusedRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) {
      return
    }

    if (isOpen) {
      previouslyFocusedRef.current = document.activeElement as HTMLElement | null
      if (!dialog.open) {
        dialog.showModal()
      }
      dialog.querySelector<HTMLElement>(FOCUSABLE_SELECTOR)?.focus()
    } else if (dialog.open) {
      dialog.close()
      previouslyFocusedRef.current?.focus()
    }
  }, [isOpen])

  return dialogRef
}

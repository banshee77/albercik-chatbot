import { useEffect, useRef } from 'react'

/** Focus-in/focus-out for a plain (non-`<dialog>`) inline panel — the
 * detail panel must stay a non-modal section so the list behind it remains
 * usable (research.md R5), so `useDialogElement`'s `showModal()`/`close()`
 * calls don't apply here; this hook keeps only the explicit focus-save/
 * restore behavior (FR-047). Attach the returned ref to the panel's
 * heading with `tabIndex={-1}`. */
export function usePanelFocus<T extends HTMLElement = HTMLElement>(isOpen: boolean) {
  const headingRef = useRef<T>(null)
  const previouslyFocusedRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    if (!isOpen) {
      return
    }
    previouslyFocusedRef.current = document.activeElement as HTMLElement | null
    headingRef.current?.focus()
    // Runs on isOpen -> false, and (for a panel that mounts/unmounts rather
    // than toggling `isOpen` in place) on unmount — either way this is the
    // "closed" moment focus must be restored (FR-047).
    return () => {
      previouslyFocusedRef.current?.focus()
      previouslyFocusedRef.current = null
    }
  }, [isOpen])

  return headingRef
}

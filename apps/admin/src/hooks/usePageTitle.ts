import { useEffect } from 'react'

/** Keeps every route's page title meaningful and distinct (FR-027). */
export function usePageTitle(title: string): void {
  useEffect(() => {
    document.title = `${title} · Shiruno Admin`
  }, [title])
}

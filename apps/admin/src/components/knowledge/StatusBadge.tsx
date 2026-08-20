import { statusLabel } from './statusLabel'

/** Status is always conveyed as text, never by color alone (FR-005, FR-008). */
export function StatusBadge({ status }: { status: string }) {
  return <span className={`status-badge status-badge--${status}`}>{statusLabel(status)}</span>
}

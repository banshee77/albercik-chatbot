import { outcomeLabel } from './outcomeLabel'

/** Outcome is always conveyed as text, never by color alone (FR-008). */
export function OutcomeBadge({ outcome }: { outcome: string }) {
  return <span className={`outcome-badge outcome-badge--${outcome}`}>{outcomeLabel(outcome)}</span>
}

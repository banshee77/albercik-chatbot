const OUTCOME_LABELS: Record<string, string> = {
  grounded: 'Answered',
  insufficient_information: 'Knowledge gap',
  out_of_scope: 'Out of scope',
  unavailable: 'Assistant unavailable',
  small_talk: 'Small talk',
}

const FALLBACK_LABEL = 'Unknown'

export function outcomeLabel(outcome: string): string {
  return OUTCOME_LABELS[outcome] ?? FALLBACK_LABEL
}

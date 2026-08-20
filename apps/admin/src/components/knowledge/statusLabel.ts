const STATUS_LABELS: Record<string, string> = {
  processing: 'Processing',
  ready: 'Ready',
  failed: 'Failed',
}

const FALLBACK_LABEL = 'Unknown'

export function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? FALLBACK_LABEL
}

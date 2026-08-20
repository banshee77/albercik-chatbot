export function LoadingState({ label }: { label: string }) {
  return (
    <div role="status" aria-live="polite" className="loading-state">
      {label}
    </div>
  )
}

interface ConversationPaginationProps {
  hasPrevious: boolean
  hasNext: boolean
  onPrevious: () => void
  onNext: () => void
}

export function ConversationPagination({
  hasPrevious,
  hasNext,
  onPrevious,
  onNext,
}: ConversationPaginationProps) {
  return (
    <nav aria-label="Conversations pagination">
      <button type="button" onClick={onPrevious} disabled={!hasPrevious}>
        Previous
      </button>
      <button type="button" onClick={onNext} disabled={!hasNext}>
        Next
      </button>
    </nav>
  )
}

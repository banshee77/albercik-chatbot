import { useEffect, useState } from 'react'
import { getConversation, listConversations } from '../api/conversations'
import type {
  ApiError,
  ConversationDetail,
  ConversationOutcome,
  ConversationSummary,
} from '../api/types'
import { ConversationDetailPanel } from '../components/conversations/ConversationDetailPanel'
import { ConversationFilters } from '../components/conversations/ConversationFilters'
import { ConversationList } from '../components/conversations/ConversationList'
import { ConversationPagination } from '../components/conversations/ConversationPagination'
import { ErrorMessage } from '../components/ErrorMessage'
import { LoadingState } from '../components/LoadingState'
import { usePageTitle } from '../hooks/usePageTitle'

type PageStatus = 'loading' | 'loaded' | 'error'
type DetailStatus = 'idle' | 'loading' | 'loaded' | 'error'

const PAGE_LIMIT = 20
const LOAD_FAILURE_MESSAGE = "Couldn't load conversations. Please try again."
const DETAIL_FAILURE_MESSAGE = "Couldn't load this conversation. Please try again."

interface QueryState {
  search: string
  outcome: ConversationOutcome | 'all'
  dateFrom: string
  dateTo: string
  offset: number
}

const INITIAL_QUERY: QueryState = { search: '', outcome: 'all', dateFrom: '', dateTo: '', offset: 0 }

function isApiError(value: unknown): value is ApiError {
  return typeof value === 'object' && value !== null && 'message' in value
}

/** The native date input gives a bare `YYYY-MM-DD`; the backend's
 * `end_date` bound is an inclusive `<=` comparison against a full
 * datetime, so a bare date would silently exclude the rest of that day
 * (research.md R10). */
function toEndOfDayIso(date: string): string {
  return `${date}T23:59:59.999`
}

export function ConversationsPage() {
  usePageTitle('Conversations')

  const [status, setStatus] = useState<PageStatus>('loading')
  const [items, setItems] = useState<ConversationSummary[]>([])
  const [total, setTotal] = useState(0)
  const [query, setQuery] = useState<QueryState>(INITIAL_QUERY)
  const [filtersActive, setFiltersActive] = useState(false)
  const [filterResetKey, setFilterResetKey] = useState(0)

  const [selectedConversationId, setSelectedConversationId] = useState<string | null>(null)
  const [detailStatus, setDetailStatus] = useState<DetailStatus>('idle')
  const [detail, setDetail] = useState<ConversationDetail | null>(null)
  const [detailError, setDetailError] = useState<string | null>(null)

  async function fetchConversations(nextQuery: QueryState): Promise<void> {
    setStatus('loading')
    setQuery(nextQuery)
    try {
      const response = await listConversations({
        q: nextQuery.search || undefined,
        outcome: nextQuery.outcome === 'all' ? undefined : nextQuery.outcome,
        start_date: nextQuery.dateFrom || undefined,
        end_date: nextQuery.dateTo ? toEndOfDayIso(nextQuery.dateTo) : undefined,
        limit: PAGE_LIMIT,
        offset: nextQuery.offset,
      })
      setItems(response.items)
      setTotal(response.total)
      setStatus('loaded')
    } catch {
      setStatus('error')
    }
  }

  useEffect(() => {
    // fetchConversations' setState calls happen asynchronously after the
    // fetch resolves, not synchronously within this effect body — the
    // standard fetch-on-mount pattern (mirrors KnowledgePage).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchConversations(INITIAL_QUERY)
  }, [])

  function handleSearchSubmit(term: string): void {
    setFiltersActive(term !== '' || query.outcome !== 'all' || query.dateFrom !== '' || query.dateTo !== '')
    fetchConversations({ ...query, search: term, offset: 0 })
  }

  function handleOutcomeChange(outcome: ConversationOutcome | 'all'): void {
    setFiltersActive(query.search !== '' || outcome !== 'all' || query.dateFrom !== '' || query.dateTo !== '')
    fetchConversations({ ...query, outcome, offset: 0 })
  }

  function handleDateChange(dateFrom: string, dateTo: string): void {
    setFiltersActive(query.search !== '' || query.outcome !== 'all' || dateFrom !== '' || dateTo !== '')
    fetchConversations({ ...query, dateFrom, dateTo, offset: 0 })
  }

  function handlePrevious(): void {
    fetchConversations({ ...query, offset: Math.max(0, query.offset - PAGE_LIMIT) })
  }

  function handleNext(): void {
    fetchConversations({ ...query, offset: query.offset + PAGE_LIMIT })
  }

  function handleClearFilters(): void {
    setFiltersActive(false)
    setFilterResetKey((key) => key + 1)
    fetchConversations(INITIAL_QUERY)
  }

  async function handleSelect(id: string): Promise<void> {
    setSelectedConversationId(id)
    setDetailStatus('loading')
    setDetailError(null)
    try {
      const result = await getConversation(id)
      setDetail(result)
      setDetailStatus('loaded')
    } catch (err) {
      setDetailError(isApiError(err) ? err.message : DETAIL_FAILURE_MESSAGE)
      setDetailStatus('error')
    }
  }

  function handleCloseDetail(): void {
    setSelectedConversationId(null)
    setDetail(null)
    setDetailStatus('idle')
    setDetailError(null)
  }

  return (
    <div>
      <h1>Conversations</h1>
      {/* The filter bar stays mounted across every reload (initial, search,
          filter, date, pagination, retry) — unmounting it here would wipe
          its own in-progress input state (research.md R9, discovered via
          T024–T026 test failures during implementation). */}
      <ConversationFilters
        key={filterResetKey}
        onSearchSubmit={handleSearchSubmit}
        onOutcomeChange={handleOutcomeChange}
        onDateChange={handleDateChange}
      />

      {status === 'loading' && <LoadingState label="Loading conversations…" />}

      {status === 'error' && (
        <div>
          <ErrorMessage message={LOAD_FAILURE_MESSAGE} />
          <button type="button" onClick={() => fetchConversations(query)}>
            Retry
          </button>
        </div>
      )}

      {status === 'loaded' && items.length === 0 && filtersActive && (
        <div>
          <p>No conversations match the selected filters.</p>
          <button type="button" onClick={handleClearFilters}>
            Clear filters
          </button>
        </div>
      )}
      {status === 'loaded' && items.length === 0 && !filtersActive && <p>No conversations yet.</p>}
      {status === 'loaded' && items.length > 0 && (
        <>
          <ConversationList
            items={items}
            selectedConversationId={selectedConversationId}
            onSelect={handleSelect}
          />
          <ConversationPagination
            hasPrevious={query.offset > 0}
            hasNext={query.offset + PAGE_LIMIT < total}
            onPrevious={handlePrevious}
            onNext={handleNext}
          />
        </>
      )}
      {selectedConversationId && detailStatus === 'loading' && (
        <LoadingState label="Loading conversation…" />
      )}
      {selectedConversationId && detailStatus === 'error' && (
        <div>
          <ErrorMessage message={detailError ?? DETAIL_FAILURE_MESSAGE} />
          <button type="button" onClick={handleCloseDetail}>
            Close
          </button>
        </div>
      )}
      {selectedConversationId && detailStatus === 'loaded' && detail && (
        <ConversationDetailPanel conversation={detail} onClose={handleCloseDetail} />
      )}
    </div>
  )
}

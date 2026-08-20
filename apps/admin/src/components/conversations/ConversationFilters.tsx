import { type FormEvent, useState } from 'react'
import type { ConversationOutcome } from '../../api/types'

const OUTCOME_OPTIONS: Array<{ value: ConversationOutcome | 'all'; label: string }> = [
  { value: 'all', label: 'All' },
  { value: 'grounded', label: 'Answered' },
  { value: 'insufficient_information', label: 'Knowledge gap' },
  { value: 'out_of_scope', label: 'Out of scope' },
  { value: 'unavailable', label: 'Unavailable' },
  { value: 'small_talk', label: 'Small talk' },
]

interface ConversationFiltersProps {
  onSearchSubmit: (term: string) => void
  onOutcomeChange: (outcome: ConversationOutcome | 'all') => void
  onDateChange: (from: string, to: string) => void
}

/** Uncontrolled — the parent resets this component by changing its `key`
 * (see ConversationsPage's "Clear filters" action) rather than by passing
 * controlled props, since a native date input's displayed value can't
 * safely round-trip through a converted (end-of-day) parent value. */
export function ConversationFilters({
  onSearchSubmit,
  onOutcomeChange,
  onDateChange,
}: ConversationFiltersProps) {
  const [searchInput, setSearchInput] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [dateError, setDateError] = useState<string | null>(null)

  function handleSearchSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault()
    onSearchSubmit(searchInput)
  }

  function handleDateChange(nextFrom: string, nextTo: string): void {
    setDateFrom(nextFrom)
    setDateTo(nextTo)
    if (nextFrom && nextTo && nextFrom > nextTo) {
      setDateError('The "From" date must be on or before the "To" date.')
      return
    }
    setDateError(null)
    onDateChange(nextFrom, nextTo)
  }

  return (
    <div>
      <form onSubmit={handleSearchSubmit} role="search">
        <label htmlFor="conversations-search">Search questions</label>
        <input
          id="conversations-search"
          type="search"
          value={searchInput}
          onChange={(event) => setSearchInput(event.target.value)}
        />
        <button type="submit">Search</button>
      </form>

      <label htmlFor="conversations-outcome">Outcome</label>
      <select
        id="conversations-outcome"
        defaultValue="all"
        onChange={(event) => onOutcomeChange(event.target.value as ConversationOutcome | 'all')}
      >
        {OUTCOME_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>

      <label htmlFor="conversations-date-from">From</label>
      <input
        id="conversations-date-from"
        type="date"
        value={dateFrom}
        onChange={(event) => handleDateChange(event.target.value, dateTo)}
      />
      <label htmlFor="conversations-date-to">To</label>
      <input
        id="conversations-date-to"
        type="date"
        value={dateTo}
        onChange={(event) => handleDateChange(dateFrom, event.target.value)}
      />
      {dateError && <p role="alert">{dateError}</p>}
    </div>
  )
}

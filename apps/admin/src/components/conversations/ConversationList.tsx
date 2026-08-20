import type { ConversationSummary } from '../../api/types'
import { OutcomeBadge } from './OutcomeBadge'

interface ConversationListProps {
  items: ConversationSummary[]
  selectedConversationId: string | null
  onSelect: (id: string) => void
}

export function ConversationList({ items, selectedConversationId, onSelect }: ConversationListProps) {
  return (
    <table>
      <caption>Conversations</caption>
      <thead>
        <tr>
          <th scope="col">Question</th>
          <th scope="col">Outcome</th>
          <th scope="col">Time</th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item.id} aria-current={item.id === selectedConversationId}>
            <th scope="row">
              <button type="button" onClick={() => onSelect(item.id)}>
                {item.question}
              </button>
            </th>
            <td>
              <OutcomeBadge outcome={item.outcome} />
            </td>
            <td>{new Date(item.created_at).toLocaleString()}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

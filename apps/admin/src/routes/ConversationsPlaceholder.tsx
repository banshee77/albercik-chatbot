import { usePageTitle } from '../hooks/usePageTitle'

export function ConversationsPlaceholder() {
  usePageTitle('Conversations')
  return (
    <div>
      <h1>Conversations</h1>
      <p>Conversation history is coming soon.</p>
    </div>
  )
}

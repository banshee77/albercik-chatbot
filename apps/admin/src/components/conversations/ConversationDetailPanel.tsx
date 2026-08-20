import { usePanelFocus } from '../../hooks/usePanelFocus'
import type { ConversationDetail } from '../../api/types'
import { OutcomeBadge } from './OutcomeBadge'

const SAFE_FAILURE_LABELS: Record<string, string> = {
  provider_error: 'The assistant provider was unavailable.',
  budget_exceeded: 'The usage budget for this period was reached.',
  kill_switch: 'The assistant was temporarily disabled by an operator.',
  concurrency_limit: 'Too many requests were in flight at once.',
}

interface ConversationDetailPanelProps {
  conversation: ConversationDetail
  onClose: () => void
}

export function ConversationDetailPanel({ conversation, onClose }: ConversationDetailPanelProps) {
  const headingRef = usePanelFocus<HTMLHeadingElement>(true)

  const hasSources = conversation.sources !== null && conversation.sources.length > 0
  const hasMetadata =
    conversation.provider_name !== null ||
    conversation.provider_model !== null ||
    conversation.input_tokens !== null ||
    conversation.output_tokens !== null

  return (
    <section aria-label="Conversation detail">
      <h2 ref={headingRef} tabIndex={-1}>
        Conversation detail
      </h2>
      <p>
        <strong>Question:</strong> {conversation.question}
      </p>
      <p>
        <strong>Answer:</strong> {conversation.answer}
      </p>
      <p>
        Outcome: <OutcomeBadge outcome={conversation.outcome} />
      </p>
      <p>{new Date(conversation.created_at).toLocaleString()}</p>

      {conversation.outcome === 'unavailable' && conversation.safe_failure_category && (
        <p role="status">{SAFE_FAILURE_LABELS[conversation.safe_failure_category]}</p>
      )}

      {hasSources && (
        <section aria-label="Sources">
          <h3>Sources</h3>
          <ul>
            {conversation.sources?.map((source) => <li key={source.document_id}>{source.label}</li>)}
          </ul>
        </section>
      )}

      {hasMetadata && (
        <dl aria-label="Operational metadata">
          <dt>Latency</dt>
          <dd>{conversation.latency_ms} ms</dd>
          {conversation.provider_name !== null && (
            <>
              <dt>Provider</dt>
              <dd>{conversation.provider_name}</dd>
            </>
          )}
          {conversation.provider_model !== null && (
            <>
              <dt>Model</dt>
              <dd>{conversation.provider_model}</dd>
            </>
          )}
          {conversation.input_tokens !== null && (
            <>
              <dt>Input tokens</dt>
              <dd>{conversation.input_tokens}</dd>
            </>
          )}
          {conversation.output_tokens !== null && (
            <>
              <dt>Output tokens</dt>
              <dd>{conversation.output_tokens}</dd>
            </>
          )}
        </dl>
      )}

      <details>
        <summary>Technical details</summary>
        <p>
          Request ID: <code>{conversation.request_id}</code>{' '}
          <button
            type="button"
            onClick={() => navigator.clipboard.writeText(conversation.request_id)}
          >
            Copy
          </button>
        </p>
      </details>

      <button type="button" onClick={onClose}>
        Close
      </button>
    </section>
  )
}

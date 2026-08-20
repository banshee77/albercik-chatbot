import type { KnowledgeHealthSummary } from '../../api/types'

export function HealthSummary({ health }: { health: KnowledgeHealthSummary }) {
  return (
    <section aria-label="Knowledge base status">
      <h2>Knowledge base status</h2>
      <ul>
        <li>{health.documents.total} documents</li>
        <li>{health.documents.ready} ready</li>
        <li>{health.documents.processing} processing</li>
        <li>{health.documents.failed} failed</li>
        <li>{health.chunks} chunks</li>
        <li>Ready for chat: {health.ready_for_chat ? 'Yes' : 'No'}</li>
      </ul>
    </section>
  )
}

import { usePageTitle } from '../hooks/usePageTitle'

export function AnalyticsPlaceholder() {
  usePageTitle('Analytics')
  return (
    <div>
      <h1>Analytics</h1>
      <p>Analytics is coming soon.</p>
    </div>
  )
}

import { Navigate, type RouteObject } from 'react-router'
import { AnalyticsPlaceholder } from './routes/AnalyticsPlaceholder'
import { AppHome } from './routes/AppHome'
import { ConversationsPlaceholder } from './routes/ConversationsPlaceholder'
import { KnowledgePlaceholder } from './routes/KnowledgePlaceholder'
import { LoginPage } from './routes/LoginPage'
import { ProtectedLayout } from './routes/ProtectedLayout'

export const routeConfig: RouteObject[] = [
  { path: '/', element: <Navigate to="/login" replace /> },
  { path: '/login', element: <LoginPage /> },
  {
    path: '/app',
    element: <ProtectedLayout />,
    children: [
      { index: true, element: <AppHome /> },
      { path: 'knowledge', element: <KnowledgePlaceholder /> },
      { path: 'conversations', element: <ConversationsPlaceholder /> },
      { path: 'analytics', element: <AnalyticsPlaceholder /> },
    ],
  },
]

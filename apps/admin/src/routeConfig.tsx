import { Navigate, type RouteObject } from 'react-router'
import { AnalyticsPlaceholder } from './routes/AnalyticsPlaceholder'
import { AppHome } from './routes/AppHome'
import { ConversationsPage } from './routes/ConversationsPage'
import { KnowledgePage } from './routes/KnowledgePage'
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
      { path: 'knowledge', element: <KnowledgePage /> },
      { path: 'conversations', element: <ConversationsPage /> },
      { path: 'analytics', element: <AnalyticsPlaceholder /> },
    ],
  },
]

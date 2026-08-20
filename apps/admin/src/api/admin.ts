import { request } from './client'
import type { AdministratorIdentity, OrganizationIdentity } from './types'

interface AdminMeResponse {
  administrator: AdministratorIdentity
  tenant: OrganizationIdentity
}

export async function getMe(): Promise<AdminMeResponse> {
  return request<AdminMeResponse>('/api/v1/admin/me')
}

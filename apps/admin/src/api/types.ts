export interface AdministratorIdentity {
  id: string
  username: string
}

export interface OrganizationIdentity {
  id: string
  name: string
  slug: string
}

export interface ApiError {
  message: string
  status?: number
}

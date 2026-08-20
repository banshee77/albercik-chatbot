import { request } from './client'

interface LoginResponse {
  access_token: string
  token_type: 'bearer'
  expires_in: number
}

export async function login(username: string, password: string): Promise<LoginResponse> {
  return request<LoginResponse>('/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
}

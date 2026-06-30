import type { Client, CreateClientPayload, TaxSummary } from '../types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })

  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail ?? `Request failed with status ${response.status}`)
  }

  return response.json() as Promise<T>
}

export const api = {
  listClients: () => request<Client[]>('/clients'),
  onboardClient: (payload: CreateClientPayload) =>
    request<Client>('/clients', { method: 'POST', body: JSON.stringify(payload) }),
  getClient: (clientId: string) => request<Client>(`/clients/${clientId}`),
  generateTaxSummary: (clientId: string, notes: string) =>
    request<TaxSummary>(`/clients/${clientId}/tax-summary`, {
      method: 'POST',
      body: JSON.stringify({ notes }),
    }),
}

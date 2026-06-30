export interface Client {
  client_id: string
  full_name: string
  email: string
  tax_id_masked: string
  status: string
  submitted_documents: string[]
  created_at: string
}

export interface CreateClientPayload {
  full_name: string
  email: string
  tax_id: string
}

export interface TaxSummary {
  client_id: string
  summary: string
}

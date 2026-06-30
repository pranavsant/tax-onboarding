import type { Client } from '../types'

interface Props {
  clients: Client[]
  onSelect: (clientId: string) => void
}

export default function ClientList({ clients, onSelect }: Props) {
  if (clients.length === 0) {
    return <p>No clients onboarded yet.</p>
  }

  return (
    <ul className="client-list">
      {clients.map((client) => (
        <li key={client.client_id} onClick={() => onSelect(client.client_id)}>
          <strong>{client.full_name}</strong> — {client.status} ({client.tax_id_masked})
        </li>
      ))}
    </ul>
  )
}

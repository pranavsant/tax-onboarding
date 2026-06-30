import { useEffect, useState } from 'react'
import { api } from './api/client'
import ClientList from './components/ClientList'
import OnboardingForm from './components/OnboardingForm'
import type { Client, CreateClientPayload } from './types'

export default function App() {
  const [clients, setClients] = useState<Client[]>([])
  const [summary, setSummary] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  const loadClients = async () => {
    try {
      const data = await api.listClients()
      setClients(data)
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : 'Failed to load clients')
    }
  }

  useEffect(() => {
    loadClients()
  }, [])

  const handleOnboard = async (payload: CreateClientPayload) => {
    await api.onboardClient(payload)
    await loadClients()
  }

  const handleSelectClient = async (clientId: string) => {
    setSummary(null)
    try {
      const result = await api.generateTaxSummary(clientId, '')
      setSummary(result.summary)
    } catch (err) {
      setSummary(err instanceof Error ? err.message : 'Failed to generate summary')
    }
  }

  return (
    <main className="app">
      <h1>Tax Onboarding</h1>
      <p>Onboard clients and generate AI-assisted tax summaries powered by Claude.</p>

      <section>
        <OnboardingForm onSubmit={handleOnboard} />
      </section>

      <section>
        <h2>Clients</h2>
        {loadError && <p className="error">{loadError}</p>}
        <ClientList clients={clients} onSelect={handleSelectClient} />
      </section>

      {summary && (
        <section>
          <h2>AI Tax Summary</h2>
          <p>{summary}</p>
        </section>
      )}
    </main>
  )
}

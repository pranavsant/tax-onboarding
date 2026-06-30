import { useState, type FormEvent } from 'react'
import type { CreateClientPayload } from '../types'

interface Props {
  onSubmit: (payload: CreateClientPayload) => Promise<void>
}

export default function OnboardingForm({ onSubmit }: Props) {
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [taxId, setTaxId] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await onSubmit({ full_name: fullName, email, tax_id: taxId })
      setFullName('')
      setEmail('')
      setTaxId('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form className="onboarding-form" onSubmit={handleSubmit}>
      <h2>Onboard a New Client</h2>
      <label>
        Full name
        <input value={fullName} onChange={(e) => setFullName(e.target.value)} required />
      </label>
      <label>
        Email
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
      </label>
      <label>
        Tax ID (SSN or EIN)
        <input
          value={taxId}
          onChange={(e) => setTaxId(e.target.value)}
          placeholder="123-45-6789"
          required
        />
      </label>
      {error && <p className="error">{error}</p>}
      <button type="submit" disabled={submitting}>
        {submitting ? 'Submitting...' : 'Onboard Client'}
      </button>
    </form>
  )
}

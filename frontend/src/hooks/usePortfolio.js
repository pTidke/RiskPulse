import { useState, useEffect, useCallback } from 'react'

const API = '/api'

export function usePortfolio() {
  const [portfolio, setPortfolio]   = useState([])
  const [alerts,    setAlerts]      = useState([])
  const [loading,   setLoading]     = useState(true)
  const [error,     setError]       = useState(null)
  const [lastUpdate, setLastUpdate] = useState(null)

  const fetch_data = useCallback(async () => {
    try {
      const res = await fetch(`${API}/portfolio`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setPortfolio(data.portfolio || [])
      setAlerts(data.alerts || [])
      setLastUpdate(new Date())
      setError(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetch_data()
    const id = setInterval(fetch_data, 30_000)
    return () => clearInterval(id)
  }, [fetch_data])

  return { portfolio, alerts, loading, error, lastUpdate, refresh: fetch_data }
}

export async function sendQuery(question) {
  const res = await fetch(`${API}/query`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ question }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const data = await res.json()
  return data.answer
}

export async function triggerIngest() {
  const res = await fetch(`${API}/ingest`, { method: 'POST' })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

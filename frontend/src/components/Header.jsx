import { useState, useEffect } from 'react'
import styles from './Header.module.css'

const STATUS = [
  { label: 'KAFKA',   color: 'green' },
  { label: 'FAUST',   color: 'amber' },
  { label: 'dbt',     color: 'blue'  },
  { label: 'RAG',     color: 'green' },
]

export default function Header({ lastUpdate, onIngest }) {
  const [clock, setClock] = useState('')
  const [date, setDate]   = useState('')
  const [ingesting, setIngesting] = useState(false)

  useEffect(() => {
    const tick = () => {
      const d = new Date()
      setClock(d.toUTCString().slice(17, 25))
      setDate(d.toUTCString().slice(5, 16).toUpperCase())
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [])

  const handleIngest = async () => {
    setIngesting(true)
    try { await onIngest() } finally { setIngesting(false) }
  }

  return (
    <header className={styles.header}>
      <div className={styles.left}>
        <div className={styles.logoIcon}>
          <span />
        </div>
        <div className={styles.logoMeta}>
          <div className={styles.logoText}>RISKPULSE</div>
          <div className={styles.logoSub}>v1.0 · PORTFOLIO INTELLIGENCE</div>
        </div>
        <div className={styles.statuses}>
          {STATUS.map(s => (
            <div key={s.label} className={styles.pill}>
              <span className={`${styles.dot} ${styles[s.color]}`} />
              {s.label}
            </div>
          ))}
        </div>
      </div>

      <div className={styles.right}>
        {lastUpdate && (
          <span className={styles.updated}>
            <span className={styles.recDot} />
            UPDATED {lastUpdate.toLocaleTimeString().slice(0,8)}
          </span>
        )}
        <button
          className={`${styles.ingestBtn} ${ingesting ? styles.spinning : ''}`}
          onClick={handleIngest}
          disabled={ingesting}
        >
          <span className={styles.ingestIcon}>↻</span>
          {ingesting ? 'SYNCING' : 'SYNC RAG'}
        </button>
        <div className={styles.clockBlock}>
          <div className={styles.clockDate}>{date}</div>
          <div className={styles.clock}>{clock} <span className={styles.tz}>UTC</span></div>
        </div>
      </div>
    </header>
  )
}

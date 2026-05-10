import { useState, useEffect, useRef } from 'react'
import styles from './ActivityFeed.module.css'

const SYM_COLORS = {
  NVDA: '#f5a623', AAPL: '#29b6f6', TSLA: '#ff3d5a',
  MSFT: '#00d97e', META: '#b388ff', GOOGL:'#ffcc02',
  SPY:  '#4dd0e1', QQQ:  '#a5d6a7',
}

const ACTIVITY_TYPES = [
  { type: 'WINDOW',  label: 'window computed' },
  { type: 'INGEST',  label: 'tick ingested'   },
  { type: 'FLUSH',   label: 'parquet flushed' },
  { type: 'ALERT',   label: 'risk evaluated'  },
]

function fakeActivity(portfolio) {
  if (!portfolio.length) return null
  const sym = portfolio[Math.floor(Math.random() * portfolio.length)].symbol
  const t   = ACTIVITY_TYPES[Math.floor(Math.random() * ACTIVITY_TYPES.length)]
  const vwap = portfolio.find(p => p.symbol === sym)?.avg_vwap || 0
  return {
    id:    Date.now() + Math.random(),
    sym,
    type:  t.type,
    label: t.label,
    vwap:  Number(vwap).toFixed(2),
    ts:    new Date(),
  }
}

export default function ActivityFeed({ portfolio }) {
  const [items, setItems] = useState([])
  const intervalRef = useRef(null)

  useEffect(() => {
    if (!portfolio.length) return

    // Seed with initial 5 items
    const seed = Array.from({ length: 5 }, () => fakeActivity(portfolio)).filter(Boolean)
    setItems(seed)

    // Push new every 1.2-2.5s
    const tick = () => {
      const next = fakeActivity(portfolio)
      if (next) setItems(prev => [next, ...prev].slice(0, 12))
      intervalRef.current = setTimeout(tick, 1200 + Math.random() * 1300)
    }
    intervalRef.current = setTimeout(tick, 1500)

    return () => clearTimeout(intervalRef.current)
  }, [portfolio])

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <span className={styles.title}>● ACTIVITY STREAM</span>
        <span className={styles.badge}>
          <span className={styles.badgeDot} />
          LIVE
        </span>
      </div>
      <div className={styles.list}>
        {items.length === 0 ? (
          <div className={styles.empty}>Waiting for activity...</div>
        ) : items.map(item => (
          <div key={item.id} className={styles.item}>
            <span className={styles.time}>
              {item.ts.toTimeString().slice(0, 8)}
            </span>
            <span
              className={styles.sym}
              style={{ color: SYM_COLORS[item.sym] }}
            >
              {item.sym}
            </span>
            <span className={`${styles.type} ${styles[item.type]}`}>
              {item.type}
            </span>
            <span className={styles.label}>{item.label}</span>
            <span className={styles.vwap}>${item.vwap}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

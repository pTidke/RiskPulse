import { useCountUp } from '../hooks/useCountUp'
import styles from './MetricsBar.module.css'

function Card({ label, value, sub, accent, formatter }) {
  const animated = useCountUp(typeof value === 'number' ? value : 0)
  const display  = typeof value === 'number'
    ? (formatter ? formatter(animated) : Math.round(animated).toLocaleString())
    : value

  return (
    <div className={`${styles.card} ${styles[accent]}`}>
      <div className={styles.labelRow}>
        <span className={styles.label}>{label}</span>
        <span className={`${styles.dot} ${styles[accent]}`} />
      </div>
      <div className={`${styles.value} ${styles[accent + 'Text']}`}>{display}</div>
      <div className={styles.sub}>{sub}</div>
    </div>
  )
}

export default function MetricsBar({ portfolio, alerts }) {
  const totalTrades = portfolio.reduce((s, p) => s + (p.total_trades || 0), 0)
  const totalVolume = portfolio.reduce((s, p) => s + (p.total_volume || 0), 0)
  const highVol     = portfolio.filter(p => p.volatility_regime === 'HIGH').length
  const medVol      = portfolio.filter(p => p.volatility_regime === 'MEDIUM').length

  return (
    <div className={styles.bar}>
      <Card
        label="TOTAL TRADES"
        value={totalTrades}
        sub="Across all symbols"
        accent="amber"
      />
      <Card
        label="ACTIVE ALERTS"
        value={alerts.length}
        sub={`${highVol} HIGH · ${medVol} MEDIUM`}
        accent="red"
      />
      <Card
        label="SYMBOLS LIVE"
        value={portfolio.length}
        sub="Streaming via Kafka"
        accent="green"
      />
      <Card
        label="TOTAL VOLUME"
        value={totalVolume / 1e6}
        sub="Notional traded ($M)"
        accent="blue"
        formatter={(v) => `$${v.toFixed(2)}M`}
      />
    </div>
  )
}

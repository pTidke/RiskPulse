import styles from './Ticker.module.css'

export default function Ticker({ portfolio }) {
  if (!portfolio.length) return null

  const renderItem = (p, i) => {
    const change = ((p.session_high - p.session_low) / p.session_low * 100).toFixed(2)
    const isUp   = p.avg_vwap > (p.session_low + p.session_high) / 2
    return (
      <div key={`${p.symbol}-${i}`} className={styles.item}>
        <span className={styles.sym}>{p.symbol}</span>
        <span className={styles.price}>${Number(p.avg_vwap).toFixed(2)}</span>
        <span className={isUp ? styles.up : styles.down}>
          {isUp ? '▲' : '▼'} {change}%
        </span>
        <span className={styles.regime}>{p.volatility_regime}</span>
        <span className={styles.divider} />
      </div>
    )
  }

  // Triple for seamless loop
  const tripled = [...portfolio, ...portfolio, ...portfolio]

  return (
    <div className={styles.wrap}>
      <div className={styles.label}>LIVE FEED</div>
      <div className={styles.track}>
        <div className={styles.scroll}>
          {tripled.map(renderItem)}
        </div>
      </div>
    </div>
  )
}

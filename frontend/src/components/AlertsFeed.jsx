import styles from './AlertsFeed.module.css'

const TYPE_STYLES = {
  DRAWDOWN:    { color: 'red',   icon: '▼' },
  HIGHEST_VOL: { color: 'red',   icon: '!' },
  WATCH:       { color: 'amber', icon: '◆' },
}

export default function AlertsFeed({ alerts }) {
  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <span className={styles.title}>● RISK ALERTS</span>
        <span className={`${styles.badge} ${alerts.length > 0 ? styles.badgeActive : ''}`}>
          {alerts.length} ACTIVE
        </span>
      </div>
      <div className={styles.list}>
        {alerts.length === 0 ? (
          <div className={styles.empty}>
            <span className={styles.checkmark}>✓</span>
            All positions within risk thresholds
          </div>
        ) : alerts.map((a, i) => {
          const t = TYPE_STYLES[a.alert_type] || { color: 'amber', icon: '◆' }
          return (
            <div
              key={`${a.symbol}-${i}`}
              className={`${styles.item} ${styles[t.color]}`}
              style={{ animationDelay: `${i * 0.08}s` }}
            >
              <div className={styles.itemLeft}>
                <div className={`${styles.iconBox} ${styles[t.color]}`}>{t.icon}</div>
                <div className={styles.itemText}>
                  <div className={styles.sym}>{a.symbol}</div>
                  <div className={`${styles.type} ${styles[t.color + 'Text']}`}>
                    {a.alert_type.replace('_', ' ')}
                  </div>
                </div>
              </div>
              <div className={styles.itemRight}>
                <div className={styles.vwap}>${Number(a.current_vwap).toFixed(2)}</div>
                <div className={styles.metrics}>
                  <span>Vol {Number(a.volatility).toFixed(4)}</span>
                  <span className={styles.rank}>#{a.volatility_rank}</span>
                </div>
                <div className={styles.detail}>
                  DD {Number(a.drawdown_pct).toFixed(2)}%
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

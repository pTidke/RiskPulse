import Sparkline from './Sparkline.jsx'
import styles from './PortfolioTable.module.css'

const REGIME_CLASS = { HIGH: styles.high, MEDIUM: styles.medium, LOW: styles.low }
const SYM_COLORS = {
  NVDA: '#f5a623', AAPL: '#29b6f6', TSLA: '#ff3d5a',
  MSFT: '#00d97e', META: '#b388ff', GOOGL:'#ffcc02',
  SPY:  '#4dd0e1', QQQ:  '#a5d6a7',
}

export default function PortfolioTable({ portfolio }) {
  if (!portfolio.length) return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <span className={styles.title}>● PORTFOLIO SUMMARY</span>
      </div>
      <div className={styles.empty}>Waiting for dbt mart data...</div>
    </div>
  )

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <span className={styles.title}>● PORTFOLIO SUMMARY</span>
        <span className={styles.badge}>dbt · mart_portfolio_summary</span>
      </div>
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th className={styles.thLeft}>SYMBOL</th>
              <th>VWAP</th>
              <th>RANGE</th>
              <th>SPARK</th>
              <th>VOL</th>
              <th>REGIME</th>
              <th>DRAWDOWN</th>
              <th className={styles.thRight}>TRADES</th>
            </tr>
          </thead>
          <tbody>
            {portfolio.map((p, i) => {
              const color = SYM_COLORS[p.symbol] || '#f5a623'
              return (
                <tr key={p.symbol} style={{ animationDelay: `${i * 0.04}s` }}>
                  <td className={styles.symCell}>
                    <span className={styles.symDot} style={{ background: color, boxShadow: `0 0 6px ${color}` }} />
                    <span className={styles.symText}>{p.symbol}</span>
                  </td>
                  <td className={styles.numCell}>${Number(p.avg_vwap).toFixed(2)}</td>
                  <td className={styles.dim}>
                    <span className={styles.rangeLow}>${Number(p.session_low).toFixed(2)}</span>
                    <span className={styles.rangeArrow}>→</span>
                    <span className={styles.rangeHigh}>${Number(p.session_high).toFixed(2)}</span>
                  </td>
                  <td>
                    <Sparkline
                      low={Number(p.session_low)}
                      avg={Number(p.avg_vwap)}
                      high={Number(p.session_high)}
                      color={color}
                      width={70}
                      height={20}
                    />
                  </td>
                  <td className={styles.numCell}>{Number(p.avg_volatility).toFixed(4)}</td>
                  <td>
                    <span className={`${styles.regime} ${REGIME_CLASS[p.volatility_regime]}`}>
                      {p.volatility_regime}
                    </span>
                  </td>
                  <td className={p.max_drawdown_pct > 3 ? styles.redText : styles.dim}>
                    {Number(p.max_drawdown_pct).toFixed(2)}%
                  </td>
                  <td className={`${styles.numCell} ${styles.dim}`}>
                    {Number(p.total_trades).toLocaleString()}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

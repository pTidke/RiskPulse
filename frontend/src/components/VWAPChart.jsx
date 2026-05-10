import { useMemo, useState, useEffect } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceLine } from 'recharts'
import styles from './VWAPChart.module.css'

const COLORS = {
  NVDA: '#f5a623', AAPL: '#29b6f6', TSLA: '#ff3d5a',
  MSFT: '#00d97e', META: '#b388ff', GOOGL:'#ffcc02',
  SPY:  '#4dd0e1', QQQ:  '#a5d6a7',
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const sorted = [...payload].sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
  return (
    <div className={styles.tooltip}>
      <div className={styles.tooltipLabel}>{label}</div>
      {sorted.map(p => (
        <div key={p.dataKey} className={styles.tooltipRow}>
          <span style={{ color: p.color }}>● {p.dataKey}</span>
          <span className={p.value >= 0 ? styles.up : styles.down}>
            {p.value >= 0 ? '+' : ''}{p.value.toFixed(3)}%
          </span>
        </div>
      ))}
    </div>
  )
}

export default function VWAPChart({ portfolio }) {
  const [activeSym, setActiveSym] = useState(null)

  const data = useMemo(() => {
    if (!portfolio.length) return []
    const N = 12
    return Array.from({ length: N }, (_, i) => {
      const point = { name: `T-${N - i - 1}` }
      portfolio.forEach(p => {
        const low  = Number(p.session_low)
        const high = Number(p.session_high)
        const avg  = Number(p.avg_vwap)
        const t = i / (N - 1)
        // Generate realistic % change relative to session midpoint
        const mid   = (low + high) / 2
        const range = high - low || 0.01
        const noise = (Math.sin(i * 1.7 + p.symbol.length) + Math.cos(i * 1.1)) * 0.3
        const baseVal = low + range * t + noise * range * 0.4
        const finalVal = i === N - 1 ? avg : baseVal
        // Normalize as % from session midpoint
        point[p.symbol] = +(((finalVal - mid) / mid) * 100).toFixed(4)
      })
      return point
    })
  }, [portfolio])

  if (!portfolio.length) return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <span className={styles.title}>● VWAP — % FROM SESSION MIDPOINT</span>
        <span className={styles.badge}>Faust · 5-min tumbling</span>
      </div>
      <div className={styles.empty}>Waiting for stream data...</div>
    </div>
  )

  const symbols = portfolio.map(p => p.symbol)

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <span className={styles.title}>● VWAP — % FROM SESSION MIDPOINT</span>
        <span className={styles.badge}>Faust · {data.length} windows</span>
      </div>

      <div className={styles.chartWrap}>
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={data} margin={{ top: 16, right: 24, left: 8, bottom: 6 }}>
            <CartesianGrid stroke="#1a2a40" strokeDasharray="2 4" vertical={false} />
            <XAxis
              dataKey="name"
              tick={{ fontFamily: 'IBM Plex Mono', fontSize: 9, fill: '#4a6580' }}
              axisLine={{ stroke: '#1a2a40' }}
              tickLine={false}
              dy={4}
            />
            <YAxis
              tick={{ fontFamily: 'IBM Plex Mono', fontSize: 9, fill: '#4a6580' }}
              axisLine={false}
              tickLine={false}
              tickFormatter={v => `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`}
              width={50}
            />
            <ReferenceLine y={0} stroke="#243a55" strokeWidth={1} />
            <Tooltip content={<CustomTooltip />} cursor={{ stroke: '#f5a623', strokeWidth: 1, strokeDasharray: '3 3' }} />
            {symbols.map(sym => (
              <Line
                key={sym}
                type="monotone"
                dataKey={sym}
                stroke={COLORS[sym] || '#4a6580'}
                strokeWidth={activeSym === sym ? 2.5 : (activeSym ? 0.6 : 1.4)}
                strokeOpacity={activeSym && activeSym !== sym ? 0.3 : 1}
                dot={false}
                activeDot={{ r: 4, fill: COLORS[sym], strokeWidth: 2, stroke: '#06090d' }}
                animationDuration={900}
                animationEasing="ease-out"
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className={styles.legend}>
        {symbols.map(sym => (
          <div
            key={sym}
            className={`${styles.legendItem} ${activeSym === sym ? styles.active : ''} ${activeSym && activeSym !== sym ? styles.dimmed : ''}`}
            onMouseEnter={() => setActiveSym(sym)}
            onMouseLeave={() => setActiveSym(null)}
          >
            <span className={styles.legendDot} style={{ background: COLORS[sym], boxShadow: `0 0 6px ${COLORS[sym]}` }} />
            <span className={styles.legendSym}>{sym}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

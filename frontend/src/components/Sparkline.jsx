import styles from './Sparkline.module.css'

export default function Sparkline({ low, avg, high, color = '#f5a623', width = 60, height = 18 }) {
  // Generate a smooth realistic-looking line between low → avg → high → avg
  const points = []
  const N = 14
  for (let i = 0; i < N; i++) {
    const t = i / (N - 1)
    const noise = (Math.sin(i * 1.3) + Math.cos(i * 0.8)) * 0.15
    let v
    if (t < 0.5) {
      v = low + (avg - low) * (t * 2) + noise * (avg - low) * 0.3
    } else {
      v = avg + (high - avg) * ((t - 0.5) * 2) + noise * (high - avg) * 0.3
    }
    points.push(v)
  }

  const min = Math.min(...points)
  const max = Math.max(...points)
  const range = max - min || 1

  const path = points.map((v, i) => {
    const x = (i / (N - 1)) * width
    const y = height - ((v - min) / range) * (height - 2) - 1
    return `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`
  }).join(' ')

  // Last point coordinates for the dot
  const lx = width
  const ly = height - ((points[N-1] - min) / range) * (height - 2) - 1

  return (
    <svg className={styles.spark} width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      <defs>
        <linearGradient id={`g-${color.replace('#','')}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stopColor={color} stopOpacity="0.3" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={`${path} L ${width} ${height} L 0 ${height} Z`} fill={`url(#g-${color.replace('#','')})`} />
      <path d={path} fill="none" stroke={color} strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={lx} cy={ly} r="1.8" fill={color} />
    </svg>
  )
}

import styles from './AnswerRenderer.module.css'

function parseInline(text) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g)
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} className={styles.bold}>{part.slice(2, -2)}</strong>
    }
    return <span key={i}>{part}</span>
  })
}

function stripBold(text) {
  return text.replace(/\*\*/g, '')
}

function parseBullet(text) {
  const cleaned = text.replace(/^[\s-•]+/, '').trim()
  const colonIdx = cleaned.indexOf(':')
  if (colonIdx > 0 && colonIdx < 50) {
    return {
      key:   stripBold(cleaned.slice(0, colonIdx)).trim(),
      value: stripBold(cleaned.slice(colonIdx + 1)).trim(),
    }
  }
  return { value: stripBold(cleaned) }
}

function highlightValue(value) {
  const tokens = value.split(/(\$[\d,.]+|\d+\.\d+%?|#\d+|\bHIGH\b|\bMEDIUM\b|\bLOW\b|\bHIGHEST_VOL\b|\bWATCH\b|\bDRAWDOWN\b)/g)
  return tokens.map((t, i) => {
    if (/^\$[\d,.]+$/.test(t))   return <span key={i} className={styles.money}>{t}</span>
    if (/^\d+\.\d+%?$/.test(t))  return <span key={i} className={styles.number}>{t}</span>
    if (/^#\d+$/.test(t))         return <span key={i} className={styles.rank}>{t}</span>
    if (t === 'HIGH' || t === 'HIGHEST_VOL' || t === 'DRAWDOWN')
      return <span key={i} className={styles.tagRed}>{t}</span>
    if (t === 'WATCH' || t === 'MEDIUM')
      return <span key={i} className={styles.tagAmber}>{t}</span>
    if (t === 'LOW')
      return <span key={i} className={styles.tagGreen}>{t}</span>
    return <span key={i}>{t}</span>
  })
}

export default function AnswerRenderer({ text }) {
  const lines = text.split('\n').map(l => l.replace(/\r/g, ''))

  const blocks = []
  let currentItem = null

  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed) {
      if (currentItem) { blocks.push(currentItem); currentItem = null }
      continue
    }

    const numMatch = trimmed.match(/^(\d+)\.\s+(.*)$/)
    if (numMatch) {
      if (currentItem) blocks.push(currentItem)
      currentItem = {
        type: 'card',
        number: numMatch[1],
        title: numMatch[2],
        bullets: [],
      }
      continue
    }

    if (/^[\s]*[-•]\s+/.test(line)) {
      if (currentItem) {
        currentItem.bullets.push(parseBullet(line))
      } else {
        blocks.push({ type: 'bullet', ...parseBullet(line) })
      }
      continue
    }

    if (trimmed.startsWith('**') && trimmed.includes(':**')) {
      if (currentItem) { blocks.push(currentItem); currentItem = null }
      blocks.push({ type: 'callout', text: trimmed })
      continue
    }

    if (currentItem) { blocks.push(currentItem); currentItem = null }
    blocks.push({ type: 'paragraph', text: trimmed })
  }
  if (currentItem) blocks.push(currentItem)

  return (
    <div className={styles.answer}>
      {blocks.map((b, i) => {
        if (b.type === 'paragraph') {
          return <p key={i} className={styles.paragraph}>{parseInline(b.text)}</p>
        }
        if (b.type === 'bullet') {
          return (
            <div key={i} className={styles.metric}>
              {b.key && <span className={styles.metricKey}>{b.key}</span>}
              <span className={styles.metricValue}>{highlightValue(b.value)}</span>
            </div>
          )
        }
        if (b.type === 'callout') {
          return (
            <div key={i} className={styles.callout}>
              <span className={styles.calloutIcon}>!</span>
              <div>{parseInline(b.text)}</div>
            </div>
          )
        }
        if (b.type === 'card') {
          return (
            <div key={i} className={styles.card}>
              <div className={styles.cardHeader}>
                <span className={styles.cardNum}>{b.number.padStart(2, '0')}</span>
                <span className={styles.cardTitle}>{parseInline(b.title)}</span>
              </div>
              <div className={styles.cardBody}>
                {b.bullets.map((bullet, j) => (
                  <div key={j} className={styles.metric}>
                    {bullet.key && <span className={styles.metricKey}>{bullet.key}</span>}
                    <span className={styles.metricValue}>{highlightValue(bullet.value)}</span>
                  </div>
                ))}
              </div>
            </div>
          )
        }
        return null
      })}
    </div>
  )
}

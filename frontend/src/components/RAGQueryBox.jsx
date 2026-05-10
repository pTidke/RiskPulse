import { useState, useRef, useEffect } from 'react'
import { sendQuery } from '../hooks/usePortfolio'
import styles from './RAGQueryBox.module.css'
import AnswerRenderer from './AnswerRenderer.jsx'

const SUGGESTIONS = [
  'Which stocks are riskiest right now?',
  'Is NVDA near a drawdown threshold?',
  'Compare AAPL and TSLA volatility',
  'Should I be worried about any alerts?',
]

// ── Typewriter component ─────────────────────────────────────────────────────
function Typewriter({ text, speed = 8, onDone }) {
  const [displayed, setDisplayed] = useState('')
  const indexRef = useRef(0)

  useEffect(() => {
    setDisplayed('')
    indexRef.current = 0

    const tick = () => {
      if (indexRef.current >= text.length) {
        onDone?.()
        return
      }
      // Print 3 chars per tick for natural speed
      const next = text.slice(0, indexRef.current + 3)
      setDisplayed(next)
      indexRef.current += 3
      timeoutRef.current = setTimeout(tick, speed)
    }

    const timeoutRef = { current: null }
    tick()

    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
    }
  }, [text, speed, onDone])

  return <span>{displayed}<span className={styles.cursor}>▍</span></span>
}

export default function RAGQueryBox() {
  const [input,    setInput]    = useState('')
  const [history,  setHistory]  = useState([])
  const [loading,  setLoading]  = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [history, loading])

  const send = async (q) => {
    const question = (q || input).trim()
    if (!question || loading) return
    setInput('')
    setLoading(true)
    const ts = new Date()
    setHistory(h => [...h, { question, answer: null, ts, animating: false }])

    try {
      const answer = await sendQuery(question)
      setHistory(h => h.map((item, i) =>
        i === h.length - 1 ? { ...item, answer, animating: true } : item
      ))
    } catch (e) {
      setHistory(h => h.map((item, i) =>
        i === h.length - 1
          ? { ...item, answer: `⚠ ${e.message} — Is FastAPI running on port 8888?`, animating: true }
          : item
      ))
    } finally {
      setLoading(false)
    }
  }

  const markComplete = (index) => {
    setHistory(h => h.map((item, i) => i === index ? { ...item, animating: false } : item))
  }

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <span className={styles.title}>● PORTFOLIO INTELLIGENCE</span>
        <span className={styles.badge}>
          <span className={styles.badgeDot} />
          GPT-4o-mini · RAG
        </span>
      </div>

      {history.length === 0 && (
        <div className={styles.suggestions}>
          <div className={styles.suggestionsLabel}>SUGGESTED QUERIES</div>
          {SUGGESTIONS.map((s, i) => (
            <button
              key={s}
              className={styles.suggestion}
              style={{ animationDelay: `${i * 0.06}s` }}
              onClick={() => send(s)}
            >
              <span className={styles.arrow}>›</span>
              {s}
            </button>
          ))}
        </div>
      )}

      <div className={styles.history}>
        {history.map((item, i) => (
          <div key={i} className={styles.exchange}>
            <div className={styles.qRow}>
              <span className={styles.prompt}>&gt;_</span>
              <span className={styles.qText}>{item.question}</span>
              <span className={styles.qTime}>
                {item.ts.toLocaleTimeString().slice(0, 8)}
              </span>
            </div>
            {item.answer ? (
              <div className={styles.answer}>
                <span className={styles.answerLabel}>RISKPULSE</span>
                <span className={styles.answerText}>
                  <AnswerRenderer text={item.answer} />
                </span>
              </div>
            ) : (
              <div className={styles.loading}>
                <span /><span /><span />
                <span className={styles.loadingText}>QUERYING RAG ENGINE</span>
              </div>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <div className={styles.inputRow}>
        <span className={styles.inputPrompt}>&gt;_</span>
        <input
          className={styles.input}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && send()}
          placeholder="Ask about your portfolio..."
          disabled={loading}
        />
        <button
          className={styles.btn}
          onClick={() => send()}
          disabled={loading || !input.trim()}
        >
          ASK ⏎
        </button>
      </div>
    </div>
  )
}

import styles from './App.module.css'
import Header         from './components/Header.jsx'
import Ticker         from './components/Ticker.jsx'
import MetricsBar     from './components/MetricsBar.jsx'
import VWAPChart      from './components/VWAPChart.jsx'
import PortfolioTable from './components/PortfolioTable.jsx'
import AlertsFeed     from './components/AlertsFeed.jsx'
import RAGQueryBox    from './components/RAGQueryBox.jsx'
import PipelineStatus from './components/PipelineStatus.jsx'
import ActivityFeed   from './components/ActivityFeed.jsx'
import { usePortfolio, triggerIngest } from './hooks/usePortfolio'

export default function App() {
  const { portfolio, alerts, loading, error, lastUpdate, refresh } = usePortfolio()

  const handleIngest = async () => {
    try {
      await triggerIngest()
      await refresh()
    } catch (e) {
      console.error('Ingest failed:', e)
    }
  }

  return (
    <div className={styles.app}>
      <Header lastUpdate={lastUpdate} onIngest={handleIngest} />

      {error && (
        <div className={styles.error}>
          <span className={styles.errorIcon}>⚠</span>
          API offline: {error} — Run{' '}
          <code>uvicorn rag.api:app --port 8888</code>
        </div>
      )}

      <Ticker portfolio={portfolio} />

      <MetricsBar portfolio={portfolio} alerts={alerts} />

      <main className={styles.main}>
        <div className={styles.left}>
          <VWAPChart portfolio={portfolio} />
          <PortfolioTable portfolio={portfolio} />
          <ActivityFeed portfolio={portfolio} />
        </div>

        <div className={styles.right}>
          <PipelineStatus />
          <AlertsFeed alerts={alerts} />
          <RAGQueryBox />
        </div>
      </main>

      <footer className={styles.footer}>
        <div className={styles.footerLeft}>
          <span className={styles.footerLogo}>RISKPULSE</span>
          <span className={styles.footerDot}>·</span>
          <span>Kafka</span>
          <span className={styles.footerDot}>·</span>
          <span>Faust</span>
          <span className={styles.footerDot}>·</span>
          <span>dbt</span>
          <span className={styles.footerDot}>·</span>
          <span>DuckDB</span>
          <span className={styles.footerDot}>·</span>
          <span>LangChain RAG</span>
        </div>
        <div className={styles.footerRight}>
          <a href="https://github.com/pTidke/riskpulse" target="_blank" rel="noreferrer">
            github.com/pTidke/riskpulse
          </a>
          <span className={styles.footerDot}>·</span>
          <a href="https://prajwaltidke.me" target="_blank" rel="noreferrer">
            prajwaltidke.me
          </a>
        </div>
      </footer>
    </div>
  )
}

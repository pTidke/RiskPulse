import styles from './PipelineStatus.module.css'

const SERVICES = [
  { name: 'Kafka',       detail: '3 topics',          status: 'on', url: 'http://localhost:8080', emoji: 'K' },
  { name: 'Faust',       detail: '5-min windows',     status: 'on', url: null,                    emoji: 'F' },
  { name: 'dbt',         detail: '4 models · 10 tests',status: 'on', url: null,                    emoji: 'D' },
  { name: 'DuckDB',      detail: 'Lakehouse',          status: 'on', url: null,                    emoji: '∂' },
  { name: 'ChromaDB',    detail: '19 vectors',         status: 'on', url: null,                    emoji: 'C' },
  { name: 'GPT-4o-mini', detail: 'Azure OpenAI',       status: 'on', url: null,                    emoji: 'G' },
  { name: 'MinIO',       detail: 'Local S3',           status: 'on', url: 'http://localhost:9001', emoji: 'M' },
  { name: 'Grafana',     detail: 'Dashboards',         status: 'on', url: 'http://localhost:3000', emoji: 'g' },
]

export default function PipelineStatus() {
  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <span className={styles.title}>● PIPELINE STATUS</span>
        <span className={styles.badge}>8 / 8 ONLINE</span>
      </div>
      <div className={styles.grid}>
        {SERVICES.map((s, i) => (
          <div
            key={s.name}
            className={`${styles.item} ${s.url ? styles.clickable : ''}`}
            onClick={() => s.url && window.open(s.url, '_blank')}
            style={{ animationDelay: `${i * 0.04}s` }}
          >
            <div className={`${styles.dot} ${styles[s.status]}`} />
            <div className={styles.text}>
              <div className={styles.name}>{s.name}</div>
              <div className={styles.detail}>{s.detail}</div>
            </div>
            {s.url && <span className={styles.link}>↗</span>}
          </div>
        ))}
      </div>
    </div>
  )
}

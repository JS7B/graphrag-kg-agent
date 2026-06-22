import type { Citation } from '../../types'
import { DataValue } from '../ui'
import styles from './CitationPanel.module.css'

interface CitationPanelProps {
  citations: Citation[]
  activeChunkId: string | null
}

export function CitationPanel({ citations, activeChunkId }: CitationPanelProps) {
  if (citations.length === 0) {
    return <div className={styles.empty}>引用证据将在回答生成后显示</div>
  }

  return (
    <div className={styles.panel}>
      <div className={styles.list}>
        {citations.map((citation) => {
          const isActive = citation.chunkId === activeChunkId

          return (
            <article
              key={`${citation.chunkId}-${citation.index}`}
              className={`${styles.entry} ${isActive ? styles.active : ''}`}
            >
              <sup className={styles.index}>[{citation.index}]</sup>
              <div className={styles.body}>
                <div className={styles.source}>
                  <strong className={styles.documentName}>{citation.documentName}</strong>
                  <DataValue label="loc">{citation.location}</DataValue>
                </div>
                <div className={styles.trace}>
                  <DataValue label="chunk">{citation.chunkId}</DataValue>
                </div>
                <p className={styles.snippet}>{citation.snippet}</p>
              </div>
            </article>
          )
        })}
      </div>
    </div>
  )
}

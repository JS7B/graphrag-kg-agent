import { useMemo } from 'react'
import { Button, Card, Chip, DataValue, Eyebrow, StatusBadge } from '../../components/ui'
import { mockDocuments } from '../../mocks'
import type { DocumentSourceType, IndexStatus, ParseStatus } from '../../types'
import styles from './LibraryView.module.css'

const sourceTypeLabels: Record<DocumentSourceType, string> = {
  pdf: 'PDF',
  markdown: 'Markdown',
  txt: 'TXT',
  repo: '仓库',
}

const parseStatusLabels: Record<ParseStatus, string> = {
  pending: '待解析',
  parsing: '解析中',
  parsed: '已解析',
  failed: '解析失败',
}

const indexStatusLabels: Record<IndexStatus, string> = {
  pending: '待索引',
  indexing: '索引中',
  indexed: '已索引',
  failed: '索引失败',
}

const parseStatusTones: Record<ParseStatus, 'success' | 'error' | 'info' | 'neutral'> = {
  pending: 'neutral',
  parsing: 'info',
  parsed: 'success',
  failed: 'error',
}

const indexStatusTones: Record<IndexStatus, 'success' | 'error' | 'info' | 'neutral'> = {
  pending: 'neutral',
  indexing: 'info',
  indexed: 'success',
  failed: 'error',
}

export function LibraryView() {
  const summary = useMemo(
    () => ({
      documentCount: mockDocuments.length,
      chunkCount: mockDocuments.reduce((total, document) => total + document.chunkCount, 0),
    }),
    [],
  )

  return (
    <section className={styles.library}>
      <header className={styles.header}>
        <div className={styles.heading}>
          <div className={styles.titleBlock}>
            <Eyebrow>Knowledge Base</Eyebrow>
            <h1 className={styles.title}>文档库</h1>
          </div>
          <div className={styles.summary} aria-label="文档库统计">
            <DataValue label="文档">{summary.documentCount}</DataValue>
            <span className={styles.summaryText}>个文档</span>
            <DataValue label="chunks">{summary.chunkCount}</DataValue>
            <span className={styles.summaryText}>个可追溯片段</span>
          </div>
        </div>
        <div className={styles.actions}>
          <Button variant="primary" onClick={() => { /* 占位：后端上传接口就绪后接入 */ }}>
            上传文档
          </Button>
          <Button variant="secondary" onClick={() => { /* 占位：后端仓库导入接口就绪后接入 */ }}>
            导入仓库
          </Button>
        </div>
      </header>

      {mockDocuments.length > 0 ? (
        <div className={styles.list} aria-label="文档列表">
          {mockDocuments.map((document) => (
            <Card key={document.id} className={styles.documentCard} interactive padding="lg">
              <div className={styles.cardHeader}>
                <div className={styles.documentNameGroup}>
                  <h2 className={styles.documentName}>{document.name}</h2>
                  <div className={styles.statusRow}>
                    <StatusBadge status={parseStatusTones[document.parseStatus]}>
                      {parseStatusLabels[document.parseStatus]}
                    </StatusBadge>
                    <StatusBadge status={indexStatusTones[document.indexStatus]}>
                      {indexStatusLabels[document.indexStatus]}
                    </StatusBadge>
                  </div>
                </div>
                <Chip className={styles.sourceChip} tone="accent">
                  {sourceTypeLabels[document.sourceType]}
                </Chip>
              </div>

              <div className={styles.metaRow}>
                <span className={styles.metaCopy}>
                  {document.chunkCount > 0 ? '已切分为引用片段' : '等待生成可引用 chunks'}
                </span>
                <DataValue label="chunks">{document.chunkCount}</DataValue>
              </div>

              <div className={styles.cardActions}>
                <Button size="sm" variant="ghost" onClick={() => { /* 占位：后端重建索引接口就绪后接入 */ }}>
                  重建索引
                </Button>
                <Button size="sm" variant="ghost" onClick={() => { /* 占位：后端删除接口就绪后接入 */ }}>
                  删除
                </Button>
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <Card className={styles.emptyState} padding="lg">
          <Eyebrow>Empty Library</Eyebrow>
          <h2 className={styles.emptyTitle}>还没有文档</h2>
          <p className={styles.emptyCopy}>上传一份文档，开始构建可追溯引用的个人知识库。</p>
          <Button variant="primary" onClick={() => { /* 占位：后端上传接口就绪后接入 */ }}>
            上传文档
          </Button>
        </Card>
      )}
    </section>
  )
}

import { useState } from 'react'
import { ChatThread } from '../../components/ChatThread/ChatThread'
import { ChatComposer } from '../../components/ChatComposer/ChatComposer'
import { CitationPanel } from '../../components/CitationPanel/CitationPanel'
import { RunEventTimeline } from '../../components/RunEventTimeline/RunEventTimeline'
import { useRunEvents } from '../../hooks/useRunEvents'
import type { ChatMessage, Citation } from '../../types'
import styles from './WorkbenchView.module.css'

export function WorkbenchView() {
  const { events } = useRunEvents()
  const [messages] = useState<ChatMessage[]>([])
  const [activeChunkId, setActiveChunkId] = useState<string | null>(null)

  // 占位：当前无真实答案，引用列表为空。后端就绪后由 answer 派生。
  const citations: Citation[] = []

  return (
    <div className={styles.workbench}>
      <section className={styles.mainCol}>
        <div className={styles.chatThread}>
          <ChatThread messages={messages} onCitationClick={setActiveChunkId} />
        </div>
        <div className={styles.citation}>
          <CitationPanel citations={citations} activeChunkId={activeChunkId} />
        </div>
        <div className={styles.composer}>
          <ChatComposer onSend={() => { /* 占位：后端就绪后发起问答 */ }} />
        </div>
      </section>
      <aside className={styles.sideCol}>
        <div className={styles.stageSlot}>像素 Agent 舞台（Task 8 填入）</div>
        <div className={styles.timelineSlot}>
          <RunEventTimeline events={events} />
        </div>
      </aside>
    </div>
  )
}

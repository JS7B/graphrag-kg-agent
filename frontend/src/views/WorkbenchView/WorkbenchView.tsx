import { useMemo, useState } from 'react'
import { ChatThread } from '../../components/ChatThread/ChatThread'
import { ChatComposer } from '../../components/ChatComposer/ChatComposer'
import { CitationPanel } from '../../components/CitationPanel/CitationPanel'
import { RunEventTimeline } from '../../components/RunEventTimeline/RunEventTimeline'
import { PixelAgent } from '../../components/PixelAgent/PixelAgent'
import { Panel } from '../../components/ui'
import { useRunEvents } from '../../hooks/useRunEvents'
import { mockMessages, mockRunEvents } from '../../mocks'
import type { Citation } from '../../types'
import styles from './WorkbenchView.module.css'

export function WorkbenchView() {
  const { currentStage } = useRunEvents()
  const [activeChunkId, setActiveChunkId] = useState<string | null>(null)

  const citations: Citation[] = useMemo(
    () => mockMessages.flatMap((message) => message.answer?.citations ?? []),
    [],
  )

  return (
    <div className={styles.workbench}>
      <section className={styles.mainCol}>
        <div className={styles.chatThread}>
          <ChatThread messages={mockMessages} onCitationClick={setActiveChunkId} />
        </div>
        <div className={styles.citation}>
          <CitationPanel citations={citations} activeChunkId={activeChunkId} />
        </div>
        <div className={styles.composer}>
          <ChatComposer onSend={() => { /* 占位：后端就绪后发起问答 */ }} />
        </div>
      </section>
      <aside className={styles.sideCol}>
        <Panel className={styles.stagePanel} eyebrow="Agent Stage" title="像素档案员">
          <div className={styles.stageBody}>
            <PixelAgent stage={currentStage} devControls={import.meta.env.DEV} />
          </div>
        </Panel>
        <Panel className={styles.timelinePanel} eyebrow="Run Events" title="运行轨迹">
          <RunEventTimeline events={mockRunEvents} />
        </Panel>
      </aside>
    </div>
  )
}

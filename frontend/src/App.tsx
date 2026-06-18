import { useState } from 'react'
import { TopBar, type ViewKey } from './components/TopBar/TopBar'
import styles from './App.module.css'

export default function App() {
  const [view, setView] = useState<ViewKey>('workbench')
  const [settingsOpen, setSettingsOpen] = useState(false)

  return (
    <div className={styles.app}>
      <TopBar
        active={view}
        onChange={setView}
        onOpenSettings={() => setSettingsOpen(true)}
      />
      <main className={styles.main}>
        {view === 'workbench' && <div>问答工作台（占位）</div>}
        {view === 'library' && <div>文档库（占位）</div>}
        {view === 'graph' && <div>图谱探索（占位）</div>}
      </main>
      {settingsOpen && (
        <div className={styles.settingsPlaceholder}>
          设置（占位）
          <button onClick={() => setSettingsOpen(false)}>关闭</button>
        </div>
      )}
    </div>
  )
}

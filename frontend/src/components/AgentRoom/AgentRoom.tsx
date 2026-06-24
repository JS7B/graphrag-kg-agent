import { useState } from 'react'
import type { RunEvent, Stage } from '../../types'
import { sceneMap, ALL_STAGES } from './sceneMap'
import { DUDE_SHADOW } from './drawDude'
import styles from './AgentRoom.module.css'
import './roomScenes.css'

interface AgentRoomProps {
  stage: Stage
  // events 预留：未来可用于门牌显示当前任务等。当前房间只消费 stage。
  events?: RunEvent[]
  // 仅供开发预览：显示手动切 stage 的按钮。
  // 红线：这只是开发工具，生产中 stage 必须来自真实 RunEvent，禁止用它驱动生产状态。
  devControls?: boolean
  // 外部 className 透传（用于父级控制 flex 比例等布局）。
  className?: string
}

/**
 * AgentRoom · 深紫调像素小房间。
 *
 * 极简悬浮色块小人（只 bob 浮动）+ 头顶气泡图标 + 周围场景道具表达状态。
 * 小人本体全状态几乎一样，变的是气泡 + 道具（降维：不做复杂逐帧角色动画）。
 *
 * 红线：stage 只来自真实 RunEvent（useRunEvents 守住），devControls 仅供开发预览。
 *
 * 道具 DOM 常驻、CSS 按 data-stage 显隐（避免切换重建跳变）。
 * 道具用全局 class 名（p-xxx），不经 module hash，故 roomScenes.css 能稳定选中。
 */
export function AgentRoom({ stage, devControls = false, className }: AgentRoomProps) {
  const [previewStage, setPreviewStage] = useState<Stage | null>(null)
  const active = devControls && previewStage ? previewStage : stage
  const cfg = sceneMap[active]
  const rootClass = [styles.room, className ?? ''].filter(Boolean).join(' ')

  return (
    <div className={rootClass}>
      {/* 画布：承载所有场景元素，data-stage/data-busy 驱动 roomScenes.css */}
      <div className={styles.canvas} data-stage={active} data-busy={cfg.busy}>
        {/* 门牌 */}
        <div className={styles.plate}>像素档案员</div>

        {/* 常驻场景元素（桌子/显示器/门），让小人有"家" */}
        <div className={`${styles.monitor} ${styles.monitorL}`} />
        <div className={`${styles.monitor} ${styles.monitorR}`} />
        <div className={styles.desk} />
        <div className={styles.door} />

        {/* 场景道具层：DOM 常驻，roomScenes.css 按 data-stage 显隐。
            全局 class 名（prop + p-xxx，不经 hash），故直接写字符串。 */}
        <div className={styles.props}>
          <div className="prop p-upload" />
          <div className="prop p-doc" />
          <div className="prop p-tag" />
          <div className="prop p-link" />
          <div className="prop p-cabinet" />
          <div className="prop p-glass" />
          <div className="prop p-type" />
          <div className="prop p-shred" />
          <div className="prop p-copy" />
          <div className="prop p-err" />
        </div>

        {/* 头顶气泡 */}
        <div className={styles.bubble}>{cfg.bubbleIcon}</div>

        {/* 小人：1 个 div + box-shadow 画全部像素（见 drawDude.ts） */}
        <div className={styles.dudeShadow} />
        <div className={styles.dude} style={{ boxShadow: DUDE_SHADOW }} />

        {/* 地面：像素条纹 */}
        <div className={styles.ground} />
      </div>

      {/* 状态栏（画布下方，正常流）*/}
      <div className={styles.status}>
        <span className={styles.statusLabel}>{cfg.label}</span>
        <span className={styles.statusDetail}>{cfg.detail}</span>
      </div>

      {devControls && (
        <div className={styles.devControls}>
          {ALL_STAGES.map((s) => (
            <button
              key={s}
              className={s === active ? styles.devBtnActive : styles.devBtn}
              onClick={() => setPreviewStage(s)}
            >
              {s}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

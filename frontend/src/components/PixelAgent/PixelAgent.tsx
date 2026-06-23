import { useState } from 'react'
import type { Stage } from '../../types'
import { stageMap, ALL_STAGES } from './stageMap'
import styles from './PixelAgent.module.css'
import './animations.css'

interface PixelAgentProps {
  stage: Stage
  // 仅供开发预览：显示手动切 stage 的按钮。
  // 红线：这只是开发工具，生产中 stage 必须来自真实 RunEvent，禁止用它驱动生产状态。
  devControls?: boolean
}

/**
 * 像素档案员：精细分层 CSS 小人。
 *
 * 小人由 22+ 个绝对定位 div 组成（头/五官/躯干/四肢/脚/影子），每个可独立动画。
 * 场景道具（桌面/道具）作为独立层，随 stage 切换显示。
 *
 * 红线：stage 只来自真实 RunEvent（useRunEvents 守住），devControls 仅供开发预览。
 *
 * 动画协作机制：
 * - module.css（本组件 styles）定义部件静态形态/位置（类名会被 hash）。
 * - animations.css（全局）定义各 stage 动作，用 [data-stage]+[data-part] 定位部件
 *   （data-* 不被 hash，故 animations.css 能稳定选中）。
 * - 子代理实现某 stage 动画时，只动 animations.css，不碰 module.css 类名。
 */
export function PixelAgent({ stage, devControls = false }: PixelAgentProps) {
  const [previewStage, setPreviewStage] = useState<Stage | null>(null)
  const active = devControls && previewStage ? previewStage : stage
  const cfg = stageMap[active]

  return (
    <div className={styles.wrap}>
      <div className={styles.scene}>
        <span className={styles.sceneIcon}>{cfg.sceneIcon}</span>
        <span className={styles.sceneLabel}>{cfg.sceneLabel}</span>
      </div>

      {/* 舞台：data-stage 驱动 animations.css；data-part 标记可动画部件 */}
      <div className={styles.stage} data-stage={active}>
        {/* 场景道具层：DOM 常驻，CSS 按需显隐，避免切换时重建跳变 */}
        <div className={styles.props} aria-hidden="true">
          <div className={`${styles.prop} ${styles.propDesk}`} data-part="propDesk" />
          <div className={`${styles.prop} ${styles.propDoc}`} data-part="propDoc" />
          <div className={`${styles.prop} ${styles.propCup}`} data-part="propCup" />
          <div className={`${styles.prop} ${styles.propSteam}`} data-part="propSteam" />
        </div>

        {/* 像素小人：部件 data-part 供 animations.css 选中做动作 */}
        <div className={styles.agent} data-part="agent">
          <div className={styles.shadow} />

          {/* 下半身 */}
          <div className={`${styles.leg} ${styles.legL}`} data-part="legL" />
          <div className={`${styles.leg} ${styles.legR}`} data-part="legR" />
          <div className={`${styles.shoe} ${styles.shoeL}`} data-part="shoeL" />
          <div className={`${styles.shoe} ${styles.shoeR}`} data-part="shoeR" />

          {/* 躯干 */}
          <div className={styles.body} data-part="body" />
          <div className={styles.bodyShade} data-part="bodyShade" />
          <div className={styles.pocket} data-part="pocket" />
          <div className={styles.collar} data-part="collar" />
          <div className={styles.neck} data-part="neck" />

          {/* 双臂 + 手（独立动画单元，很多状态要让手臂举起/摆动） */}
          <div className={`${styles.arm} ${styles.armL}`} data-part="armL" />
          <div className={`${styles.arm} ${styles.armR}`} data-part="armR" />
          <div className={`${styles.hand} ${styles.handL}`} data-part="handL" />
          <div className={`${styles.hand} ${styles.handR}`} data-part="handR" />

          {/* 头部 + 五官（头部整体可动，五官各自可动） */}
          <div className={styles.head} data-part="head">
            <div className={styles.headHi} />
            <div className={styles.headShade} />
            <div className={styles.hair}>
              <div className={styles.hairHi} />
            </div>
            <div className={`${styles.brow} ${styles.browL}`} data-part="browL" />
            <div className={`${styles.brow} ${styles.browR}`} data-part="browR" />
            <div className={styles.glasses} />
            <div className={styles.glassGlint} />
            <div className={`${styles.eye} ${styles.eyeL}`} data-part="eyeL" />
            <div className={`${styles.eye} ${styles.eyeR}`} data-part="eyeR" />
            <div className={styles.nose} />
            <div className={styles.mouth} data-part="mouth" />
          </div>

          {/* 手持道具层（放大镜/纸片等，按 stage 显隐） */}
          <div className={styles.heldProp} data-part="heldProp" />
        </div>
      </div>

      <div className={styles.label}>{cfg.label}</div>

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

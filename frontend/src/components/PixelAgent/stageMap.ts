import type { Stage } from '../../types'

/**
 * stage → 展示配置。
 * - label：状态标签（中文，显示在小人下方）。
 * - sceneIcon / sceneLabel：场景描述（场景道具的文字标识，给用户直观提示）。
 * - 动画由根节点 data-stage 触发 animations.css，不在此配置动画类名（避免与 DOM 切换耦合）。
 *
 * Stage 枚举 12 个值锁定前端契约，不得改名（后端 runs.models.Stage 同源）。
 */
export const stageMap: Record<
  Stage,
  { label: string; sceneIcon: string; sceneLabel: string }
> = {
  idle: { label: '待命', sceneIcon: '☕', sceneLabel: '安静的工作间' },
  uploading: { label: '搬运文档', sceneIcon: '📦', sceneLabel: '门口收件筐' },
  parsing: { label: '拆文件', sceneIcon: '📄', sceneLabel: '拆包台' },
  extracting: { label: '贴实体标签', sceneIcon: '🏷️', sceneLabel: '标签贴纸' },
  linking: { label: '拉关系线', sceneIcon: '🔗', sceneLabel: '连线板' },
  indexing: { label: '整理档案柜', sceneIcon: '🗄️', sceneLabel: '档案柜' },
  searching: { label: '翻找文件', sceneIcon: '🔍', sceneLabel: '文件堆' },
  checking: { label: '校对引用', sceneIcon: '🔎', sceneLabel: '放大镜' },
  writing: { label: '打字输出', sceneIcon: '⌨️', sceneLabel: '打字机' },
  deleting: { label: '碎纸', sceneIcon: '🗑️', sceneLabel: '碎纸机' },
  rebuilding: { label: '复印重排', sceneIcon: '🖨️', sceneLabel: '复印机' },
  error: { label: '查看错误', sceneIcon: '⚠️', sceneLabel: '红色纸条' },
}

// 12 个状态的固定顺序，供开发预览切换器使用。
export const ALL_STAGES: Stage[] = [
  'idle', 'uploading', 'parsing', 'extracting', 'linking', 'indexing',
  'searching', 'checking', 'writing', 'deleting', 'rebuilding', 'error',
]

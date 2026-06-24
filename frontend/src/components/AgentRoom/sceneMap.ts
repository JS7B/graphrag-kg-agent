import type { Stage } from '../../types'

/**
 * stage → 房间场景配置。
 * - label：状态标签（中文，显示在房间下方）。
 * - bubbleIcon：头顶气泡图标（emoji，状态最直观的表达）。
 * - detail：进度文案（状态副标题）。
 * - busy：是否"工作中"——影响小人摆动幅度（busy=1 摆动更明显）。
 *
 * Stage 枚举 12 个值锁定前端契约（types/runEvent.ts），不得改名（后端同源）。
 */
export const sceneMap: Record<
  Stage,
  { label: string; bubbleIcon: string; detail: string; busy: 0 | 1 }
> = {
  idle: { label: '待命', bubbleIcon: '☕', detail: '空闲中', busy: 0 },
  uploading: { label: '搬运文档', bubbleIcon: '📥', detail: '接收文件', busy: 1 },
  parsing: { label: '拆文件', bubbleIcon: '📄', detail: '解析文档', busy: 1 },
  extracting: { label: '贴标签', bubbleIcon: '🏷️', detail: '抽取实体', busy: 1 },
  linking: { label: '拉关系', bubbleIcon: '🔗', detail: '连接关系', busy: 1 },
  indexing: { label: '整理档案', bubbleIcon: '🗂️', detail: '写入图库', busy: 1 },
  searching: { label: '翻找', bubbleIcon: '🔍', detail: '向量召回', busy: 1 },
  checking: { label: '校对', bubbleIcon: '✓', detail: '校验引用', busy: 1 },
  writing: { label: '打字', bubbleIcon: '⌨️', detail: '生成回答', busy: 1 },
  deleting: { label: '碎纸', bubbleIcon: '🗑️', detail: '删除文档', busy: 1 },
  rebuilding: { label: '重排', bubbleIcon: '🔄', detail: '重建索引', busy: 1 },
  error: { label: '出错', bubbleIcon: '⚠️', detail: '发生错误', busy: 0 },
}

// 12 个状态的固定顺序，供开发预览切换器使用。
export const ALL_STAGES: Stage[] = [
  'idle', 'uploading', 'parsing', 'extracting', 'linking', 'indexing',
  'searching', 'checking', 'writing', 'deleting', 'rebuilding', 'error',
]

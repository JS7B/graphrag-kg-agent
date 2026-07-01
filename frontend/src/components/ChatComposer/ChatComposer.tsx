import { useState } from 'react'
import { Button } from '../ui'
import styles from './ChatComposer.module.css'

interface ChatComposerProps {
  onSend: (text: string) => void
  /** 运行中（SSE 未结束）时禁用，避免双订阅状态混乱。 */
  busy?: boolean
}

export function ChatComposer({ onSend, busy = false }: ChatComposerProps) {
  const [text, setText] = useState('')
  const trimmedText = text.trim()
  const disabled = !trimmedText || busy

  return (
    <form
      className={styles.composer}
      onSubmit={(event) => {
        event.preventDefault()
        if (trimmedText && !busy) {
          onSend(trimmedText)
          setText('')
        }
      }}
    >
      <label className={styles.inputWrap}>
        <span className={styles.label}>向知识库提问</span>
        <textarea
          className={styles.input}
          value={text}
          placeholder={busy ? 'Agent 正在思考，请稍候…' : '例如：多头注意力相比单头有什么好处？'}
          rows={2}
          enterKeyHint="send"
          disabled={busy}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            // Enter 发送、Shift+Enter 换行；输入法组合中（选词回车）不触发。
            if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault()
              if (trimmedText && !busy) {
                onSend(trimmedText)
                setText('')
              }
            }
          }}
        />
      </label>
      <Button className={styles.sendButton} disabled={disabled} type="submit" variant="primary">
        {busy ? '思考中…' : '发送'}
      </Button>
    </form>
  )
}

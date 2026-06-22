import { useState } from 'react'
import { Button } from '../ui'
import styles from './ChatComposer.module.css'

interface ChatComposerProps {
  onSend: (text: string) => void
}

export function ChatComposer({ onSend }: ChatComposerProps) {
  const [text, setText] = useState('')
  const trimmedText = text.trim()

  return (
    <form
      className={styles.composer}
      onSubmit={(event) => {
        event.preventDefault()
        if (trimmedText) {
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
          placeholder="例如：多头注意力相比单头有什么好处？"
          rows={2}
          onChange={(event) => setText(event.target.value)}
        />
      </label>
      <Button className={styles.sendButton} disabled={!trimmedText} type="submit" variant="primary">
        发送
      </Button>
    </form>
  )
}

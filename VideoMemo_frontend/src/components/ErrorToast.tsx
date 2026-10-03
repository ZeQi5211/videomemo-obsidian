import { useState } from 'react'
import { toast, type Toast } from 'react-hot-toast'

/**
 * 全局错误提示框（替换默认 toast.error 渲染）：
 * - 不自动消失（duration: Infinity），需要用户主动点「关闭」
 * - 提供「复制」按钮，方便把后端返回的详细错误（如引擎退出码）拷出去反馈
 */
export function ErrorToastView({ t, message }: { t: Toast; message: string }) {
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    const text = message || ''
    const markCopied = () => {
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    }
    try {
      await navigator.clipboard.writeText(text)
      markCopied()
    } catch {
      // 剪贴板 API 不可用（非 https / 权限受限）时回退到 execCommand
      try {
        const ta = document.createElement('textarea')
        ta.value = text
        ta.style.position = 'fixed'
        ta.style.opacity = '0'
        document.body.appendChild(ta)
        ta.select()
        document.execCommand('copy')
        document.body.removeChild(ta)
        markCopied()
      } catch {
        /* ignore */
      }
    }
  }

  const btn: React.CSSProperties = {
    border: '1px solid rgba(255,255,255,.28)',
    background: 'transparent',
    color: '#fff',
    borderRadius: 6,
    padding: '4px 12px',
    fontSize: 12,
    lineHeight: 1.4,
    cursor: 'pointer',
    flexShrink: 0,
  }

  return (
    <div
      style={{
        background: '#2b2b2b',
        color: '#fff',
        borderRadius: 10,
        padding: '12px 14px',
        maxWidth: 440,
        minWidth: 260,
        boxShadow: '0 10px 32px rgba(0,0,0,.28)',
        fontFamily:
          '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 8,
        }}
      >
        <span style={{ fontWeight: 700, fontSize: 13, color: '#ff7a7a' }}>错误</span>
        <button
          title="关闭"
          aria-label="关闭"
          onClick={() => toast.dismiss(t.id)}
          style={{
            border: 'none',
            background: 'transparent',
            color: 'rgba(255,255,255,.65)',
            fontSize: 15,
            lineHeight: 1,
            cursor: 'pointer',
            padding: 2,
          }}
        >
          ✕
        </button>
      </div>
      <pre
        style={{
          margin: '0 0 10px',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
          maxHeight: 200,
          overflow: 'auto',
          fontSize: 12.5,
          lineHeight: 1.55,
          fontFamily: 'inherit',
          color: 'rgba(255,255,255,.92)',
        }}
      >
        {message}
      </pre>
      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
        <button style={btn} onClick={copy}>
          {copied ? '已复制 ✓' : '复制'}
        </button>
        <button style={btn} onClick={() => toast.dismiss(t.id)}>
          关闭
        </button>
      </div>
    </div>
  )
}

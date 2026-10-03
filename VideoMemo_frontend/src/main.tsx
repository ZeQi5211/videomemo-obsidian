import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import RootLayout from './layouts/RootLayout.tsx'
import toast from 'react-hot-toast'
import { ErrorToastView } from './components/ErrorToast'

// 全局包装错误 toast：不自动消失，提供「复制 / 关闭」按钮。
// 后端返回的详细错误（如下载引擎退出码、供应商接口报错）往往很长，
// 默认 toast 几秒自动消失且无法复制；包装后所有 toast.error(...) 调用点
// 统一渲染成可复制、需手动关闭的错误卡片，方便排查与反馈。
const _origError = toast.error.bind(toast)
;(toast as any).error = (message: unknown, opts?: Record<string, unknown>) => {
  const text = typeof message === 'string' ? message : String(message ?? '')
  return toast.custom(
    t => <ErrorToastView t={t} message={text} />,
    { duration: Infinity, ...opts },
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <RootLayout>
      <App />
    </RootLayout>
  </StrictMode>
)

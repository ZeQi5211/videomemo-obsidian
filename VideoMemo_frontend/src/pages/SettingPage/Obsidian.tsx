import { useEffect, useState } from 'react'
import { BookMarked, Save, Plug, History, Check } from 'lucide-react'
import toast from 'react-hot-toast'
import {
  getObsidianConfig,
  saveObsidianConfig,
  testObsidianPath,
} from '@/services/obsidian'

const Obsidian = () => {
  const [folderPath, setFolderPath] = useState('')
  const [history, setHistory] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)

  useEffect(() => {
    ;(async () => {
      try {
        const cfg = await getObsidianConfig()
        setFolderPath(cfg.folder_path || '')
        setHistory(cfg.history || [])
      } catch {
        /* 拦截器已 toast */
      } finally {
        setLoading(false)
      }
    })()
  }, [])

  const handleSave = async () => {
    if (!folderPath.trim()) {
      toast.error('请填写 Obsidian 知识库文件夹路径')
      return
    }
    setSaving(true)
    try {
      const cfg = await saveObsidianConfig(folderPath)
      setHistory(cfg.history || [])
      toast.success('Obsidian 同步配置已保存')
    } catch {
      /* 拦截器已 toast */
    } finally {
      setSaving(false)
    }
  }

  /** 点击历史路径：立即切换为当前路径并保存（一键切换） */
  const handlePickHistory = async (path: string) => {
    if (path === folderPath) return
    setFolderPath(path)
    setSaving(true)
    try {
      const cfg = await saveObsidianConfig(path)
      setHistory(cfg.history || [])
      toast.success(`已切换到：${path}`)
    } catch {
      /* 拦截器已 toast */
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async () => {
    if (!folderPath.trim()) {
      toast.error('请先填写文件夹路径')
      return
    }
    setTesting(true)
    const toastId = toast.loading('正在校验路径…')
    try {
      const res = await testObsidianPath(folderPath)
      toast.success(res?.msg || '路径有效，可以写入', { id: toastId })
    } catch (e: any) {
      toast.error(e?.msg || e?.message || '路径不可用', { id: toastId })
    } finally {
      setTesting(false)
    }
  }

  if (loading) {
    return (
      <div className="vm-content-inner narrow vm-fade-up">
        <div className="vm-card vm-card-pad">
          <div className="vm-muted text-sm">加载 Obsidian 配置…</div>
        </div>
      </div>
    )
  }

  return (
    <div className="vm-content-inner narrow vm-fade-up">
      <div className="vm-card vm-card-pad">
        {/* 标题区 */}
        <div className="vm-row" style={{ gap: 12, marginBottom: 16 }}>
          <span
            style={{
              width: 38,
              height: 38,
              borderRadius: 10,
              background: 'var(--vm-primary-soft)',
              color: 'var(--vm-primary)',
              display: 'grid',
              placeItems: 'center',
            }}
          >
            <BookMarked size={19} />
          </span>
          <div>
            <div style={{ fontWeight: 800, fontSize: 18 }}>Obsidian 同步</div>
            <div className="vm-muted" style={{ fontSize: 13 }}>
              把生成的笔记一键写入你自己的 Obsidian 知识库文件夹（.md，兼容 YAML
              frontmatter）。
            </div>
          </div>
        </div>

        {/* 文件夹路径 */}
        <label className="vm-field-label" htmlFor="obsidian-folder">
          Obsidian 知识库文件夹路径
        </label>
        <input
          id="obsidian-folder"
          className="vm-input"
          value={folderPath}
          placeholder="例如 D:\ObsidianVault\视频解析知识库"
          onChange={e => setFolderPath(e.target.value)}
          style={{ marginTop: 6 }}
        />
        <div className="vm-field-hint" style={{ marginTop: 8, whiteSpace: 'normal' }}>
          填写这台机器上 Obsidian 库的绝对路径（每台电脑的路径不同，请填自己的）。同步时会
          写入该文件夹，重名自动追加 -1/-2 序号，不会覆盖已有文件。
        </div>

        {/* 操作按钮 */}
        <div className="vm-row" style={{ gap: 10, marginTop: 18 }}>
          <button className="vm-btn vm-btn-outline" type="button" onClick={handleTest} disabled={testing}>
            <Plug size={16} />
            {testing ? '测试中…' : '测试路径'}
          </button>
          <button className="vm-btn vm-btn-primary" type="button" onClick={handleSave} disabled={saving}>
            <Save size={16} />
            {saving ? '保存中…' : '保存配置'}
          </button>
        </div>

        {/* 历史路径：一键选择切换 */}
        {history.length > 0 && (
          <div style={{ marginTop: 20 }}>
            <div className="vm-row" style={{ gap: 8, marginBottom: 8 }}>
              <History size={14} className="vm-muted" />
              <span className="vm-field-label" style={{ margin: 0 }}>
                历史路径
              </span>
              <span className="vm-muted" style={{ fontSize: 12 }}>
                点击即可切换（每个知识库保存一次，以后直接选）
              </span>
            </div>
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 6,
              }}
            >
              {history.map(path => {
                const active = path === folderPath
                return (
                  <button
                    key={path}
                    type="button"
                    onClick={() => handlePickHistory(path)}
                    disabled={saving}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      textAlign: 'left',
                      width: '100%',
                      padding: '8px 12px',
                      borderRadius: 8,
                      border: `1px solid ${
                        active ? 'var(--vm-primary)' : 'var(--vm-border, #e5e7eb)'
                      }`,
                      background: active ? 'var(--vm-primary-soft, #eef4ff)' : 'transparent',
                      color: 'inherit',
                      fontSize: 13,
                      cursor: 'pointer',
                    }}
                  >
                    <span style={{ flex: 1, wordBreak: 'break-all' }}>{path}</span>
                    {active && (
                      <span
                        className="vm-muted"
                        style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12 }}
                      >
                        <Check size={13} style={{ color: 'var(--vm-primary)' }} />
                        当前
                      </span>
                    )}
                  </button>
                )
              })}
            </div>
          </div>
        )}

        <div className="vm-field-hint" style={{ marginTop: 16, whiteSpace: 'normal' }}>
          提示：在笔记页点「同步 Obsidian」按钮即可一键同步；未配置路径时会弹出引导框，首次填写后
          自动保存。多个知识库可分别保存一次，之后在「历史路径」里一键切换。
        </div>
      </div>
    </div>
  )
}
export default Obsidian

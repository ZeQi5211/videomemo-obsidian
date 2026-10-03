import { FC, useState } from 'react'
import { Check, Download, ExternalLink, FileVideo, Play, RefreshCw, Square } from 'lucide-react'
import { trVm } from '@/i18n/redesign'
import { WxChannelsStatus, WxDownloadItem } from '@/services/wxchannels'

function fmtSize(n: number): string {
  if (n >= 1 << 30) return (n / (1 << 30)).toFixed(1) + ' GB'
  if (n >= 1 << 20) return (n / (1 << 20)).toFixed(1) + ' MB'
  if (n >= 1 << 10) return (n / (1 << 10)).toFixed(0) + ' KB'
  return n + ' B'
}

function fmtTime(ts: number): string {
  const d = new Date(ts * 1000)
  const p = (x: number) => String(x).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

/**
 * 微信视频号下载面板：服务状态 / 启停 / 已下载文件选择。
 * 选中文件后把路径通过 onPick 交给父级（等价于填好了 video_url），
 * 点主按钮「生成笔记」即进入 VideoMemo 转写链路。
 */
const WxChannelsPanel: FC<{
  lang: 'zh' | 'en'
  status: WxChannelsStatus | null
  downloads: WxDownloadItem[]
  loading: boolean
  busy: boolean
  selected: string
  downloading: boolean
  onRefresh: () => void
  onStart: () => void
  onStop: () => void
  onPick: (path: string) => void
  onDownload: (url: string) => void
}> = ({ lang, status, downloads, loading, busy, selected, downloading, onRefresh, onStart, onStop, onPick, onDownload }) => {
  const t = (key: string) => trVm(key, lang)
  const [link, setLink] = useState('')
  const running = !!status?.running
  const apiUp = !!status?.api_listening
  const binMissing = status ? !status.binary_exists : false
  const webUrl = apiUp && status?.api_addr ? status.api_addr : ''
  const handleDownload = () => {
    const u = link.trim()
    if (!u || downloading) return
    onDownload(u)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* 服务状态 + 启停 */}
      <div
        className="vm-card vm-card-pad"
        style={{ margin: 0, padding: '10px 14px', background: 'var(--vm-surface-2)' }}
      >
        <div className="vm-row" style={{ justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
          <div className="vm-row" style={{ gap: 8, alignItems: 'center' }}>
            <span className="vm-field-label">{t('wxSvcStatus')}</span>
            {binMissing ? (
              <span className="vm-badge vm-badge-warn">{t('wxNotInstalled')}</span>
            ) : running ? (
              <span className="vm-badge vm-badge-ok">
                {t('wxRunning')}
                {status?.version ? ` · v${status.version}` : ''}
              </span>
            ) : (
              <span className="vm-badge vm-badge-neutral">{t('wxStopped')}</span>
            )}
            {apiUp && status?.proxy_listening ? (
              <span className="vm-badge vm-badge-ok" style={{ fontSize: 11 }}>
                {status.proxy_addr || 'proxy'} ✓
              </span>
            ) : null}
          </div>
          <div className="vm-row" style={{ gap: 6, flexWrap: 'wrap' }}>
            <button
              className="vm-btn vm-btn-primary vm-btn-sm"
              disabled={busy || running || binMissing}
              onClick={onStart}
            >
              <Play size={13} /> {t('wxStart')}
            </button>
            <button
              className="vm-btn vm-btn-outline vm-btn-sm"
              disabled={busy || !running}
              onClick={onStop}
            >
              <Square size={13} /> {t('wxStop')}
            </button>
            {webUrl && (
              <a
                className="vm-btn vm-btn-ghost vm-btn-sm"
                href={webUrl}
                target="_blank"
                rel="noreferrer"
                style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}
              >
                <ExternalLink size={13} /> {t('wxOpenWeb')}
              </a>
            )}
          </div>
        </div>
        {binMissing && (
          <div className="vm-field-hint" style={{ marginTop: 6, fontSize: 12, color: 'var(--vm-warn)' }}>
            {t('wxBinMissing')}
          </div>
        )}
      </div>

      {/* 链接下载：粘贴分享链接 → 一键下载为 MP4 */}
      <div
        className="vm-card vm-card-pad"
        style={{ margin: 0, padding: '10px 14px', background: 'var(--vm-surface-2)' }}
      >
        <span className="vm-field-label" style={{ fontSize: 12.5 }}>
          {t('wxLinkDownload')}
        </span>
        <div className="vm-row" style={{ gap: 6, marginTop: 7 }}>
          <input
            className="vm-input vm-input-mono"
            placeholder={t('wxLinkPlaceholder')}
            value={link}
            onChange={e => setLink(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter' && link.trim() && !downloading) handleDownload()
            }}
            disabled={downloading}
            style={{ flex: 1, minWidth: 0, fontSize: 12.5 }}
          />
          <button
            className="vm-btn vm-btn-primary vm-btn-sm"
            disabled={downloading || !link.trim()}
            onClick={handleDownload}
            style={{ whiteSpace: 'nowrap' }}
          >
            <Download size={13} /> {downloading ? t('wxDownloading') : t('wxDownload')}
          </button>
        </div>
        <div className="vm-field-hint" style={{ fontSize: 12, marginTop: 6, color: 'var(--vm-muted)', lineHeight: 1.5 }}>
          {t('wxDownloadHint')}
        </div>
      </div>

      {/* 使用步骤 */}
      <div
        className="vm-card vm-card-pad"
        style={{ margin: 0, padding: '10px 14px', background: 'var(--vm-surface-2)' }}
      >
        <span className="vm-field-label" style={{ fontSize: 12.5 }}>
          {t('wxStepsTitle')}
        </span>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3, marginTop: 6 }}>
          {[t('wxStep1'), t('wxStep2'), t('wxStep3'), t('wxStep4')].map((s, i) => (
            <div key={i} className="vm-row" style={{ gap: 7, alignItems: 'flex-start' }}>
              <span
                className="vm-badge vm-badge-neutral"
                style={{ minWidth: 18, height: 18, borderRadius: 9, padding: '0 5px', fontSize: 11, justifyContent: 'center' }}
              >
                {i + 1}
              </span>
              <span className="vm-field-hint" style={{ fontSize: 12, lineHeight: 1.5 }}>
                {s}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* 已下载文件列表 */}
      <div
        className="vm-card vm-card-pad"
        style={{ margin: 0, padding: '10px 14px', background: 'var(--vm-surface-2)' }}
      >
        <div className="vm-row" style={{ justifyContent: 'space-between', marginBottom: 8 }}>
          <span className="vm-field-label" style={{ fontSize: 12.5 }}>
            {t('wxDownloads')}
            {status?.download_dir ? (
              <span style={{ color: 'var(--vm-faint)', fontWeight: 400 }}> · {status.download_dir}</span>
            ) : null}
          </span>
          <button className="vm-btn vm-btn-ghost vm-btn-sm" disabled={loading} onClick={onRefresh}>
            <RefreshCw size={13} className={loading ? 'vm-spin' : ''} /> {t('wxRefresh')}
          </button>
        </div>

        {downloads.length === 0 ? (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 6,
              padding: '14px 0',
              color: 'var(--vm-muted)',
            }}
          >
            <FileVideo size={22} />
            <span style={{ fontSize: 12.5 }}>
              {status && !status.download_dir_exists ? t('wxDownloadDirMissing') : t('wxEmpty')}
            </span>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5, maxHeight: 260, overflowY: 'auto' }}>
            {downloads.map(f => {
              const on = selected === f.path
              return (
                <div
                  key={f.path}
                  onClick={() => onPick(f.path)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 9,
                    padding: '7px 9px',
                    borderRadius: 'var(--vm-radius-sm)',
                    cursor: 'pointer',
                    background: on ? 'var(--vm-primary-soft, rgba(16,163,127,.12))' : 'transparent',
                    border: on ? '1px solid var(--vm-primary)' : '1px solid var(--vm-border)',
                  }}
                >
                  <span
                    style={{
                      width: 16,
                      height: 16,
                      borderRadius: 8,
                      border: '1.5px solid ' + (on ? 'var(--vm-primary)' : 'var(--vm-border-strong)'),
                      display: 'grid',
                      placeItems: 'center',
                      flexShrink: 0,
                      color: '#fff',
                    }}
                  >
                    {on && <Check size={11} strokeWidth={3} style={{ background: 'var(--vm-primary)', borderRadius: 8 }} />}
                  </span>
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div
                      style={{
                        fontSize: 12.5,
                        fontWeight: on ? 700 : 500,
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        fontFamily: 'var(--vm-mono, monospace)',
                      }}
                      title={f.path}
                    >
                      {f.name}
                    </div>
                    <div className="vm-field-hint" style={{ fontSize: 11 }}>
                      {fmtSize(f.size)} · {fmtTime(f.mtime)}
                    </div>
                  </div>
                  {on && <span className="vm-badge vm-badge-ok" style={{ fontSize: 11 }}>{t('wxSelect')}</span>}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

export default WxChannelsPanel

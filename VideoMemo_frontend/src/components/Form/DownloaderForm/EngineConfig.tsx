import { useCallback, useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { Download } from 'lucide-react'
import { Button } from '@/components/ui/button.tsx'
import { Input } from '@/components/ui/input.tsx'
import {
  getDownloadModeConfig,
  updateDownloadModeConfig,
  installDownloadEngine,
  type DownloadModeConfig,
} from '@/services/downloader'

/** 下载引擎（yt-dlp + lux）配置区：目录设置 + 安装状态 + 一键安装 */
const EngineConfig = () => {
  const [config, setConfig] = useState<DownloadModeConfig | null>(null)
  const [dirInput, setDirInput] = useState('')
  const [installing, setInstalling] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const cfg = await getDownloadModeConfig()
      setConfig(cfg)
      setDirInput(cfg.engine_dir || cfg.default_dir || '')
    } catch {
      setConfig(null)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const handleSaveDir = async () => {
    try {
      const cfg = await updateDownloadModeConfig(dirInput.trim())
      setConfig(cfg)
      setDirInput(cfg.engine_dir || '')
      toast.success('引擎目录已保存')
    } catch {
      toast.error('保存失败，请检查目录路径')
    }
  }

  const handleInstall = async (engine: 'lux' | 'ytdlp') => {
    if (installing) return
    setInstalling(engine)
    try {
      await installDownloadEngine(engine)
      toast.success(engine === 'lux' ? 'lux 开始安装（多镜像自动切换）' : 'yt-dlp 开始安装（多镜像自动切换）')
      // 后台下载可能需几分钟：轮询刷新就绪状态（最长 5 分钟）
      for (let i = 0; i < 60; i++) {
        await new Promise(r => setTimeout(r, 5000))
        const cfg = await getDownloadModeConfig().catch(() => null)
        if (!cfg) continue
        setConfig(cfg)
        const ready = engine === 'lux' ? cfg.lux_installed : cfg.ytdlp_exe_installed
        if (ready) {
          toast.success(engine === 'lux' ? 'lux 已就绪' : 'yt-dlp 已就绪')
          break
        }
      }
    } catch {
      toast.error('安装任务提交失败，可改用 VideoDownloader 安装')
    } finally {
      setInstalling(null)
    }
  }

  const Status = ({ ok, okText, failText }: { ok: boolean; okText: string; failText: string }) => (
    <span className={ok ? 'text-emerald-600' : 'text-amber-600'}>
      {ok ? '✓ ' + okText : failText}
    </span>
  )

  return (
    <div className="flex flex-col gap-2">
      <div className="text-sm font-light">下载引擎</div>
      <div className="rounded-md border border-emerald-100 bg-emerald-50 p-2 text-xs leading-relaxed text-emerald-700">
        双引擎下载模式（yt-dlp + lux），选中哪个引擎，下载就走哪条通道：
        <br />· yt-dlp：开源下载器，支持上千个网站、更新频繁，负责 YouTube / TikTok / X 等海外站
        <br />· lux：Go 编写的轻量下载器，对国内主流视频站支持好、速度快，负责 B 站 / 抖音 / 小红书 / 微博等国内站
      </div>

      {/* 状态 */}
      <div className="flex flex-col gap-1 rounded border border-neutral-200 p-2 text-xs">
        <div className="flex items-center justify-between">
          <span className="text-gray-500">lux（国内站）</span>
          <Status
            ok={!!config?.lux_installed}
            okText="已就绪"
            failText="未安装，点击下方安装"
          />
        </div>
        <div className="flex items-center justify-between">
          <span className="text-gray-500">yt-dlp（海外站 / 音频）</span>
          <span className="text-emerald-600">✓ 已安装（内置 Python 包）</span>
        </div>
      </div>

      {/* 引擎目录 */}
      <div className="flex flex-col gap-1">
        <div className="text-xs text-gray-500">引擎目录（lux.exe / yt-dlp.exe 所在位置）</div>
        <div className="flex gap-1">
          <Input
            value={dirInput}
            onChange={e => setDirInput(e.target.value)}
            placeholder="留空则自动检测 VideoDownloader\\bin"
            className="h-8 flex-1 text-xs"
          />
          <Button size="sm" variant="outline" onClick={handleSaveDir}>
            保存
          </Button>
        </div>
      </div>

      {/* 一键安装：仅 lux 需要下载 */}
      <div className="flex gap-1">
        <Button
          size="sm"
          variant="ghost"
          disabled={!!installing}
          onClick={() => handleInstall('lux')}
          className="flex-1"
        >
          <Download className="h-3.5 w-3.5" />
          {installing === 'lux' ? '安装中…' : '安装 lux'}
        </Button>
      </div>
      <div className="text-[11px] leading-relaxed text-gray-400">
        yt-dlp 使用 VideoMemo 内置的 Python 包，无需安装；lux 可用本页按钮或 VideoDownloader 安装，保存到同一目录后这里会自动识别。
      </div>
    </div>
  )
}
export default EngineConfig

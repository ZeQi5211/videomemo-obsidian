/** 下载引擎（yt-dlp）配置区：引擎说明 + 内置引擎就绪状态 */
const EngineConfig = () => {
  return (
    <div className="flex flex-col gap-2">
      <div className="text-sm font-light">下载引擎</div>
      <div className="rounded-md border border-emerald-100 bg-emerald-50 p-2 text-xs leading-relaxed text-emerald-700">
        引擎下载模式（yt-dlp）：支持上千个网站。
        <br />· B 站 / YouTube 等：yt-dlp 直接下载（海外站需可访问外网）
        <br />· 抖音：自动委托专用解析器，需在「下载器配置 → 抖音」粘贴 Cookie
        <br />· 快手 / 小红书：yt-dlp 不支持，当前版本暂不可用
      </div>
      <div className="flex items-center justify-between rounded border border-neutral-200 p-2 text-xs">
        <span className="text-gray-500">内置引擎（无需安装）</span>
        <span className="text-emerald-600">✓ yt-dlp 已就绪（恒可用）</span>
      </div>
    </div>
  )
}
export default EngineConfig

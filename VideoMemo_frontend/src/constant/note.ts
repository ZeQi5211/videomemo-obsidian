/* -------------------- 常量 -------------------- */
import {
  BiliBiliLogo,
  DouyinLogo,
  KuaishouLogo,
  LocalLogo,
  XhsLogo,
  YoutubeLogo,
} from '@/components/Icons/platform.tsx'

export const noteFormats = [
  { label: '目录', value: 'toc' },
  { label: '原文内容略精简易读版', value: 'condensed' },
  { label: '原片跳转', value: 'link' },
  { label: '原片截图', value: 'screenshot' },
  { label: 'AI总结', value: 'summary' },
] as const

export const noteStyles = [
  { label: 'Obsidian 深度精读', value: 'obsidian_deep' },
  { label: 'Obsidian 精简归纳', value: 'obsidian_quick' },
  { label: '精简', value: 'minimal' },
  { label: '详细', value: 'detailed' },
  { label: '教程', value: 'tutorial' },
  { label: '学术', value: 'academic' },
  { label: '小红书', value: 'xiaohongshu' },
  { label: '生活向', value: 'life_journal' },
  { label: '任务导向', value: 'task_oriented' },
  { label: '商业风格', value: 'business' },
  { label: '会议纪要', value: 'meeting_minutes' },
] as const

export const videoPlatforms = [
  { label: '哔哩哔哩', value: 'bilibili', logo: BiliBiliLogo },
  { label: 'YouTube', value: 'youtube', logo: YoutubeLogo },
  { label: '抖音', value: 'douyin', logo: DouyinLogo },
  { label: '快手', value: 'kuaishou', logo: KuaishouLogo },
  { label: '小红书', value: 'xiaohongshu', logo: XhsLogo },
  { label: '本地视频', value: 'local', logo: LocalLogo },
] as const

export const COOKIE_OPTIONAL_PLATFORMS = new Set(['youtube', 'douyin'])

/** 下载模式：工作区顶部三选一 */
export const downloadModes = [
  {
    label: '智能 Cookie',
    value: 'cookie',
    desc: '原平台下载器，可配站点 Cookie',
  },
  {
    label: '引擎下载',
    value: 'engine',
    desc: 'yt-dlp 引擎，可选清晰度',
  },
  {
    label: '本地视频',
    value: 'local',
    desc: '拖入本地视频直接转写',
  },
  {
    label: '微信视频号下载',
    value: 'wxchannels',
    desc: '微信 PC 端直接下载视频号视频',
  },
] as const

/** engine 模式下载视频的清晰度 */
export const videoQualityOptions = [
  { label: '仅音频', value: 'audio' },
  { label: '最佳', value: 'best' },
  { label: '1080p', value: '1080p' },
  { label: '720p', value: '720p' },
  { label: '480p', value: '480p' },
  { label: '360p', value: '360p' },
] as const

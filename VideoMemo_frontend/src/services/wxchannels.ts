import request from '@/utils/request.ts'

export interface WxChannelsStatus {
  binary: string
  binary_exists: boolean
  pid: number | null
  running: boolean
  api_addr: string
  api_listening: boolean
  proxy_addr: string
  proxy_listening: boolean
  version: string
  download_dir: string
  download_dir_exists: boolean
}

export interface WxDownloadItem {
  path: string
  name: string
  size: number
  mtime: number
  ext: string
}

export const getWxChannelsStatus = async (): Promise<WxChannelsStatus> => {
  return await request.get('/wxchannels/status')
}

export const startWxChannels = async (): Promise<WxChannelsStatus> => {
  // 首次运行会弹 UAC，等待用户确认可能超过请求超时 —— 属预期内，不弹全局错误 toast
  return await request.post('/wxchannels/start', undefined, { suppressToast: true } as any)
}

export const stopWxChannels = async (): Promise<WxChannelsStatus> => {
  return await request.post('/wxchannels/stop', undefined, { suppressToast: true } as any)
}

export const getWxChannelsDownloads = async (limit = 30): Promise<WxDownloadItem[]> => {
  return await request.get('/wxchannels/downloads', { params: { limit } })
}

export interface WxDownloadResult {
  file: string
  name: string
  size: number
  title: string
  author: string
}

export const downloadWxShare = async (url: string): Promise<WxDownloadResult> => {
  // 下载可能耗时数分钟，覆盖默认 10s 超时；失败原因由业务代码自行 toast（不弹全局红 toast）
  return await request.post('/wxchannels/download', { url }, {
    timeout: 600000,
    suppressToast: true,
  } as any)
}

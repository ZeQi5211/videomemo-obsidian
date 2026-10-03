import request from '@/utils/request.ts'

export const getDownloaderCookie = async id => {
  return await request.get('/get_downloader_cookie/' + id)
}

export const updateDownloaderCookie = async (data: {
  cookie: string
  platform: string
  /** 可选：从浏览器读 cookie（yt-dlp cookiesfrombrowser）。空字符串=清除。 */
  browser?: string
}) => {
  return await request.post('/update_downloader_cookie', data)
}

export const syncDownloaderCookieFromBrowser = async (data: {
  platform: string
  browser: string
}): Promise<{
  platform: string
  browser: string
  cookie: string
  count: number
}> => {
  return await request.post('/sync_downloader_cookie_from_browser', data)
}

export interface CustomPlatform {
  key: string
  name: string
  match: string
}

export const listCustomPlatforms = async (): Promise<CustomPlatform[]> => {
  return await request.get('/custom_platforms')
}

export const upsertCustomPlatform = async (data: CustomPlatform): Promise<CustomPlatform> => {
  return await request.post('/custom_platforms', data)
}

export const deleteCustomPlatform = async (key: string) => {
  return await request.delete('/custom_platforms/' + key)
}

/* ---- 下载模式：双引擎（yt-dlp + lux）配置 ---- */

export interface DownloadModeConfig {
  engine_dir: string
  default_dir: string
  lux_installed: boolean
  ytdlp_exe_installed: boolean
  ytdlp_python: boolean
}

export const getDownloadModeConfig = async (): Promise<DownloadModeConfig> => {
  return await request.get('/download_mode_config')
}

export const updateDownloadModeConfig = async (engine_dir: string): Promise<DownloadModeConfig> => {
  return await request.post('/download_mode_config', { engine_dir })
}

export const installDownloadEngine = async (engine: 'lux' | 'ytdlp'): Promise<{ msg: string }> => {
  return await request.post('/download_mode_install', { engine })
}

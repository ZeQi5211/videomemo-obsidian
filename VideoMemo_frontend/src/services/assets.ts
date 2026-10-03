import request from '@/utils/request'

export interface AssetFile {
  name: string
  size: number
  size_text: string
  mtime: string
  ext: string
  url: string | null
  kind: 'audio' | 'video' | 'image' | 'text'
  category: string
}

export interface AssetCategory {
  id: string
  kind: 'media' | 'image' | 'text'
  files: AssetFile[]
}

export interface AssetProject {
  id: string
  name: string
  video_id: string
  platform: string
  created_at: string
  files_total: number
  categories: AssetCategory[]
}

export interface AssetsData {
  projects: AssetProject[]
  shared: AssetCategory[]
  stats: Record<string, number>
}

export interface AssetOpPayload {
  scope: 'project' | 'category' | 'file'
  project_id?: string
  category?: string
  file?: string
}

export const listAssets = async (): Promise<AssetsData> => {
  const res = await request.get('/assets/list', { suppressToast: true } as never)
  return res as AssetsData
}

export const fetchAssetContent = async (fileName: string): Promise<{ name: string; content: string }> => {
  const res = await request.get('/assets/content', {
    params: { file: fileName },
    suppressToast: true,
  } as never)
  return res as { name: string; content: string }
}

export const deleteAsset = async (payload: AssetOpPayload): Promise<{ removed: number; errors: string[] }> => {
  const res = await request.post('/assets/delete', payload, { suppressToast: true } as never)
  return res as { removed: number; errors: string[] }
}

export const openAsset = async (payload: AssetOpPayload): Promise<void> => {
  await request.post('/assets/open', payload, { suppressToast: true } as never)
}

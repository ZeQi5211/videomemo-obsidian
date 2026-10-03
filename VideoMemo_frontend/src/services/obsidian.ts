import request from '@/utils/request'

export interface ObsidianConfig {
  folder_path: string
  auto_open: boolean
  /** 历史保存过的文件夹路径（最新在前，用于一键切换） */
  history?: string[]
}

export interface ObsidianSyncInfo {
  file_path: string
  filename: string
  folder_path: string
  title: string
}

/** 读取已保存的 Obsidian 同步配置 */
export const getObsidianConfig = async (): Promise<ObsidianConfig> => {
  return await request.get('/obsidian_config')
}

/** 保存 Obsidian 同步配置（folder_path 为目标文件夹绝对路径） */
export const saveObsidianConfig = async (
  folderPath: string,
  autoOpen?: boolean,
): Promise<ObsidianConfig> => {
  return await request.post('/obsidian_config', {
    folder_path: folderPath,
    auto_open: autoOpen,
  })
}

/** 测试目标文件夹路径是否有效（存在/可写） */
export const testObsidianPath = async (folderPath: string): Promise<{ ok: boolean; folder_path: string }> => {
  return await request.post('/obsidian_test', { folder_path: folderPath })
}

/**
 * 一键同步当前笔记到 Obsidian 文件夹。
 * sourceUrl 传当前视频 URL（用于生成来源链接，放在 frontmatter 之后）。
 */
export const syncNoteToObsidian = async (params: {
  taskId: string
  versionId?: string
  sourceUrl?: string
}): Promise<ObsidianSyncInfo> => {
  return await request.post('/obsidian_sync', {
    task_id: params.taskId,
    version_id: params.versionId,
    source_url: params.sourceUrl,
  })
}

/**
 * 前端「下载 markdown」用的 Obsidian 兼容归一化（与后端 ensure_obsidian_frontmatter 同逻辑）。
 * 旧笔记的来源链接行可能在文件最开头，会挤占 frontmatter 第一行，导致 Obsidian 不识别属性。
 * 这里把来源链接行移到 frontmatter 之后（无 frontmatter 时保持原样放最前）。
 */
export function normalizeMarkdownForObsidianExport(content: string): string {
  if (!content) return content
  const lines = content.split('\n')

  // 0. frontmatter tags 行标点兜底：LLM 可能用中文逗号/顿号分隔数组，
  //    会导致 Obsidian 把整个 tags 解析成单个字符串标签（层级标签失效）
  const firstNonEmptyAll = lines.findIndex(l => l.trim())
  if (firstNonEmptyAll !== -1 && lines[firstNonEmptyAll].trim() === '---') {
    let closeAll = -1
    for (let i = firstNonEmptyAll + 1; i < lines.length; i++) {
      if (lines[i].trim() === '---') {
        closeAll = i
        break
      }
    }
    if (closeAll !== -1) {
      for (let i = firstNonEmptyAll + 1; i < closeAll; i++) {
        const t = lines[i].trim()
        if (t.startsWith('tags:') || t.startsWith('tag:')) {
          lines[i] = lines[i]
            .replace(/，/g, ',')
            .replace(/、/g, ',')
            .replace(/；/g, ',')
            .replace(/,\s+/g, ', ')
          break
        }
      }
    }
  }

  const headerIdx = lines.findIndex(
    l => l.trim().startsWith('> 来源链接：') || l.trim().startsWith('来源链接：')
  )
  if (headerIdx === -1) return lines.join('\n')
  const headerLine = lines[headerIdx]
  const rest = lines.filter((_, i) => i !== headerIdx)

  // 找到第一个非空行，判断是否是 frontmatter 开始
  const firstNonEmpty = rest.findIndex(l => l.trim())
  if (firstNonEmpty === -1 || rest[firstNonEmpty].trim() !== '---') {
    // 无 frontmatter：保持原位置（恢复原样）
    return content
  }
  // 找闭合 ---（第二个）
  let closeIdx = -1
  for (let i = firstNonEmpty + 1; i < rest.length; i++) {
    if (rest[i].trim() === '---') {
      closeIdx = i
      break
    }
  }
  if (closeIdx === -1) return content
  // 插入到闭合行之后（补一个空行分隔）；去掉前导空行，避免 frontmatter 被空行挤出第一行
  let out = [...rest.slice(0, closeIdx + 1), '', headerLine, ...rest.slice(closeIdx + 1)]
  while (out.length && out[0].trim() === '') out.shift()
  return out.join('\n')
}

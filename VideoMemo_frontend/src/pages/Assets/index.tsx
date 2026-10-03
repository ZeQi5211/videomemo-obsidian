import { FC, useCallback, useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import {
  AudioLines,
  Boxes,
  ChevronLeft,
  Clapperboard,
  Download,
  FileJson,
  FileText,
  Film,
  FolderOpen,
  Grid3x3,
  Image as ImageIcon,
  Loader2,
  RefreshCcw,
  Scissors,
  Trash2,
  X,
} from 'lucide-react'
import { toast } from 'react-hot-toast'
import { trVm, useVmLang } from '@/i18n/redesign'
import {
  deleteAsset,
  fetchAssetContent,
  listAssets,
  openAsset,
  type AssetCategory,
  type AssetFile,
  type AssetProject,
  type AssetsData,
} from '@/services/assets'

const CATEGORY_META: Record<string, { zh: string; en: string; icon: JSX.Element }> = {
  audio: { zh: '音频', en: 'Audio', icon: <AudioLines size={16} /> },
  video: { zh: '视频', en: 'Video', icon: <Film size={16} /> },
  covers: { zh: '封面', en: 'Covers', icon: <ImageIcon size={16} /> },
  screenshots: { zh: '原片截图', en: 'Screenshots', icon: <Scissors size={16} /> },
  frames: { zh: '抽帧', en: 'Frames', icon: <Boxes size={16} /> },
  grids: { zh: '网格图', en: 'Grids', icon: <Grid3x3 size={16} /> },
  video_transcripts: { zh: '视频级转写缓存', en: 'Video transcripts', icon: <FileJson size={16} /> },
  transcripts: { zh: '转写/元信息缓存', en: 'Transcripts', icon: <FileJson size={16} /> },
  notes: { zh: '笔记缓存', en: 'Notes', icon: <FileText size={16} /> },
}
const catLabel = (id: string, lang: 'zh' | 'en') => {
  const m = CATEGORY_META[id]
  return m ? (lang === 'zh' ? m.zh : m.en) : id
}

/** 取分类/项目的封面缩略图 URL（优先封面，其次任意图片分类第一张）。 */
const firstImage = (categories: AssetCategory[]): string | null => {
  const byKind = (ids: string[]) => {
    for (const id of ids) {
      const c = categories.find(x => x.id === id)
      const f = c?.files.find(x => x.kind === 'image' && x.url)
      if (f?.url) return f.url
    }
    return null
  }
  return byKind(['covers', 'screenshots', 'frames', 'grids'])
}

const platformTag = (p: string) =>
  p === 'bilibili' ? 'B站' : p === 'youtube' ? 'YT' : p === 'douyin' ? '抖音' : p === 'xiaohongshu' ? '小红书' : p || '—'

/** 数据加载 hook。 */
const useAssetData = (lang: 'zh' | 'en') => {
  const [data, setData] = useState<AssetsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [reloadKey, setReloadKey] = useState(0)
  const reload = useCallback(() => setReloadKey(k => k + 1), [])

  useEffect(() => {
    setLoading(true)
    listAssets()
      .then(setData)
      .catch(() => toast.error(trVm('assetsLoadFailed', lang)))
      .finally(() => setLoading(false))
  }, [reloadKey, lang])

  return { data, loading, reload }
}

/** 删除动作（带确认），成功后刷新。 */
const useAssetActions = (reload: () => void, lang: 'zh' | 'en') => {
  const confirm = (message: string) => window.confirm(message)

  const doDelete = useCallback(
    (payload: Parameters<typeof deleteAsset>[0], confirmMsg: string) => {
      if (!confirm(confirmMsg)) return
      deleteAsset(payload)
        .then(res => {
          toast.success(`${trVm('assetsDeleteDone', lang)}（${res.removed}）`)
          reload()
        })
        .catch(() => toast.error(trVm('assetsDeleteFail', lang)))
    },
    [reload, lang],
  )

  return {
    deleteProject: (p: AssetProject) =>
      doDelete(
        { scope: 'project', project_id: p.id },
        trVm('assetsDeleteProjectConfirm', lang).replace('N', String(p.files_total)),
      ),
    deleteCategory: (c: AssetCategory, projectId?: string) =>
      doDelete(
        { scope: 'category', project_id: projectId, category: c.id },
        trVm('assetsDeleteCategoryConfirm', lang).replace('N', String(c.files.length)),
      ),
    deleteFile: (f: AssetFile) =>
      doDelete({ scope: 'file', category: f.category, file: f.name }, trVm('assetsDeleteFileConfirm', lang)),
  }
}

/** 文件卡片：缩略图 + 名称 + 大小/时间 + hover 操作（打开位置 / 删除）。 */
const FileTile: FC<{ file: AssetFile; lang: 'zh' | 'en'; onPreview: (f: AssetFile) => void; onDelete: (f: AssetFile) => void }> = ({
  file,
  lang,
  onPreview,
  onDelete,
}) => {
  const [hover, setHover] = useState(false)
  return (
    <div
      className="vm-card vm-card-pad"
      onClick={() => onPreview(file)}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        cursor: 'pointer',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        minWidth: 0,
        position: 'relative',
        transition: 'transform .12s ease, box-shadow .12s ease',
      }}
    >
      {hover && (
        <div
          style={{
            position: 'absolute',
            top: 8,
            right: 8,
            display: 'flex',
            gap: 6,
            zIndex: 5,
          }}
        >
          <button
            className="vm-btn vm-btn-outline vm-btn-sm"
            title={trVm('assetsOpenLocation', lang)}
            onClick={e => {
              e.stopPropagation()
              openAsset({ scope: 'file', category: file.category, file: file.name })
                .catch(() => toast.error(trVm('assetsDeleteFail', lang)))
            }}
            style={{ padding: 5, lineHeight: 1 }}
          >
            <FolderOpen size={13} />
          </button>
          <button
            className="vm-btn vm-btn-outline vm-btn-sm"
            title={trVm('assetsDeleteFile', lang)}
            onClick={e => {
              e.stopPropagation()
              onDelete(file)
            }}
            style={{ padding: 5, lineHeight: 1, color: 'var(--vm-danger, #dc2626)' }}
          >
            <Trash2 size={13} />
          </button>
        </div>
      )}
      <div
        style={{
          width: '100%',
          aspectRatio: '16/10',
          borderRadius: 8,
          background: 'var(--vm-card-sunken, #f1f3f5)',
          display: 'grid',
          placeItems: 'center',
          overflow: 'hidden',
          color: 'var(--vm-faint)',
        }}
      >
        {file.kind === 'image' && file.url ? (
          <img
            src={file.url}
            alt={file.name}
            loading="lazy"
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          />
        ) : (
          <span style={{ opacity: 0.85 }}>{CATEGORY_META[file.category]?.icon ?? <FileText size={20} />}</span>
        )}
      </div>
      <div style={{ minWidth: 0 }}>
        <div
          title={file.name}
          style={{
            fontWeight: 600,
            fontSize: 13,
            color: 'var(--vm-text)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {file.name}
        </div>
        <div className="vm-faint vm-mono" style={{ fontSize: 11, marginTop: 3, display: 'flex', gap: 8 }}>
          <span>{file.size_text}</span>
          <span>{file.mtime}</span>
        </div>
      </div>
    </div>
  )
}

/** 分类区块：分类头（打开位置 / 删除分类）+ 文件网格。 */
const CategorySection: FC<{
  cat: AssetCategory
  projectId?: string
  lang: 'zh' | 'en'
  onPreview: (f: AssetFile) => void
  onDeleteCategory: (c: AssetCategory, projectId?: string) => void
  onDeleteFile: (f: AssetFile) => void
}> = ({ cat, projectId, lang, onPreview, onDeleteCategory, onDeleteFile }) => {
  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '2px 0 10px', flexWrap: 'wrap' }}>
        <span style={{ color: 'var(--vm-accent, #4f46e5)', display: 'grid' }}>
          {CATEGORY_META[cat.id]?.icon ?? <Clapperboard size={16} />}
        </span>
        <span style={{ fontWeight: 700, fontSize: 14, color: 'var(--vm-text)' }}>{catLabel(cat.id, lang)}</span>
        <span className="vm-faint vm-mono" style={{ fontSize: 12 }}>
          {cat.files.length}
        </span>
        <span style={{ flex: 1 }} />
        <button
          className="vm-btn vm-btn-outline vm-btn-sm"
          title={trVm('assetsOpenLocation', lang)}
          onClick={() =>
            openAsset({ scope: 'category', category: cat.id }).catch(() => toast.error(trVm('assetsDeleteFail', lang)))
          }
        >
          <FolderOpen size={14} />
          {trVm('assetsOpenLocation', lang)}
        </button>
        <button
          className="vm-btn vm-btn-outline vm-btn-sm"
          title={trVm('assetsDeleteCategory', lang)}
          onClick={() => onDeleteCategory(cat, projectId)}
          style={{ color: 'var(--vm-danger, #dc2626)' }}
        >
          <Trash2 size={14} />
          {trVm('assetsDeleteCategory', lang)}
        </button>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 12 }}>
        {cat.files.map(f => (
          <FileTile key={f.name} file={f} lang={lang} onPreview={onPreview} onDelete={onDeleteFile} />
        ))}
      </div>
    </div>
  )
}

/** 预览弹层：图片放大 / 音视频播放 / 文本内容。 */
const PreviewModal: FC<{ file: AssetFile | null; lang: 'zh' | 'en'; onClose: () => void }> = ({ file, lang, onClose }) => {
  const [content, setContent] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setContent(null)
    if (file && file.kind === 'text' && file.url) {
      setLoading(true)
      fetchAssetContent(file.name)
        .then(r => setContent(r.content))
        .catch(() => toast.error(trVm('assetsLoadFailed', lang)))
        .finally(() => setLoading(false))
    }
  }, [file, lang])

  if (!file) return null
  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(15,23,42,.55)',
        zIndex: 1000,
        display: 'grid',
        placeItems: 'center',
        padding: 24,
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: 'var(--vm-card-bg, #fff)',
          borderRadius: 14,
          maxWidth: 960,
          width: '100%',
          maxHeight: '88vh',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          boxShadow: '0 24px 60px rgba(0,0,0,.25)',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 10,
            padding: '12px 16px',
            borderBottom: '1px solid var(--vm-border, #eee)',
          }}
        >
          <span
            title={file.name}
            style={{
              fontWeight: 600,
              fontSize: 14,
              color: 'var(--vm-text)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {file.name}
          </span>
          <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
            {file.url && !file.url.startsWith('/api/') && (
              <a
                className="vm-btn vm-btn-outline vm-btn-sm"
                href={file.url}
                target="_blank"
                rel="noreferrer"
                title={trVm('assetsOpen', lang)}
              >
                <Download size={14} />
              </a>
            )}
            <button className="vm-btn vm-btn-outline vm-btn-sm" onClick={onClose} title={trVm('close', lang)}>
              <X size={14} />
            </button>
          </div>
        </div>
        <div style={{ overflow: 'auto', padding: 16, flex: 1, minHeight: 0 }}>
          {file.kind === 'image' && file.url && (
            <img src={file.url} alt={file.name} style={{ width: '100%', borderRadius: 8, display: 'block' }} />
          )}
          {file.kind === 'audio' && file.url && <audio controls autoPlay style={{ width: '100%' }} src={file.url} />}
          {file.kind === 'video' && file.url && (
            <video controls autoPlay style={{ width: '100%', borderRadius: 8 }} src={file.url} />
          )}
          {file.kind === 'text' && (
            <pre
              style={{
                margin: 0,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
                fontSize: 12.5,
                lineHeight: 1.65,
                color: 'var(--vm-text)',
                maxHeight: '70vh',
                overflow: 'auto',
              }}
            >
              {loading ? '…' : content ?? trVm('assetsEmpty', lang)}
            </pre>
          )}
        </div>
      </div>
    </div>
  )
}

/** 项目卡片。 */
const ProjectCard: FC<{
  project: AssetProject
  lang: 'zh' | 'en'
  onOpen: () => void
  onOpenLocation: () => void
  onDelete: () => void
}> = ({ project, lang, onOpen, onOpenLocation, onDelete }) => {
  const [hover, setHover] = useState(false)
  const cover = firstImage(project.categories)
  return (
    <div
      className="vm-card vm-card-pad"
      onClick={onOpen}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        cursor: 'pointer',
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        minWidth: 0,
        position: 'relative',
        transition: 'transform .12s ease, box-shadow .12s ease',
      }}
    >
      {hover && (
        <div style={{ position: 'absolute', top: 8, right: 8, display: 'flex', gap: 6, zIndex: 5 }}>
          <button
            className="vm-btn vm-btn-outline vm-btn-sm"
            title={trVm('assetsOpenLocation', lang)}
            onClick={e => {
              e.stopPropagation()
              onOpenLocation()
            }}
            style={{ padding: 5, lineHeight: 1 }}
          >
            <FolderOpen size={13} />
          </button>
          <button
            className="vm-btn vm-btn-outline vm-btn-sm"
            title={trVm('assetsDeleteProject', lang)}
            onClick={e => {
              e.stopPropagation()
              onDelete()
            }}
            style={{ padding: 5, lineHeight: 1, color: 'var(--vm-danger, #dc2626)' }}
          >
            <Trash2 size={13} />
          </button>
        </div>
      )}
      <div
        style={{
          width: '100%',
          aspectRatio: '16/9',
          borderRadius: 8,
          background: 'var(--vm-card-sunken, #f1f3f5)',
          display: 'grid',
          placeItems: 'center',
          overflow: 'hidden',
          color: 'var(--vm-faint)',
        }}
      >
        {cover ? (
          <img src={cover} alt={project.name} loading="lazy" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        ) : (
          <Film size={26} style={{ opacity: 0.5 }} />
        )}
      </div>
      <div style={{ minWidth: 0 }}>
        <div
          title={project.name}
          style={{
            fontWeight: 700,
            fontSize: 14,
            color: 'var(--vm-text)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {project.name}
        </div>
        <div className="vm-faint" style={{ fontSize: 11.5, marginTop: 3, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <span
            style={{
              background: 'var(--vm-accent-soft, #eef2ff)',
              color: 'var(--vm-accent, #4f46e5)',
              borderRadius: 4,
              padding: '1px 6px',
              fontWeight: 600,
            }}
          >
            {platformTag(project.platform)}
          </span>
          <span>{project.created_at}</span>
          <span className="vm-mono">
            {project.files_total} {trVm('assetsProjectFiles', lang)}
          </span>
        </div>
        <div style={{ display: 'flex', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
          {project.categories.map(c => (
            <span
              key={c.id}
              title={catLabel(c.id, lang)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                fontSize: 11,
                color: 'var(--vm-faint)',
                background: 'var(--vm-card-sunken, #f1f3f5)',
                borderRadius: 6,
                padding: '2px 6px',
              }}
            >
              {CATEGORY_META[c.id]?.icon}
              <span className="vm-mono">{c.files.length}</span>
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}

/** 通用头部：返回 + 标题 + 右侧动作。 */
const SectionHeader: FC<{
  title: string
  sub?: string
  lang: 'zh' | 'en'
  actions?: JSX.Element
}> = ({ title, sub, lang, actions }) => {
  const navigate = useNavigate()
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14, flexWrap: 'wrap' }}>
      <button
        className="vm-btn vm-btn-outline vm-btn-sm"
        onClick={() => navigate('/assets')}
        style={{ flexShrink: 0 }}
      >
        <ChevronLeft size={15} />
        {trVm('assetsBack', lang)}
      </button>
      <span style={{ minWidth: 0, flex: 1 }}>
        <span style={{ display: 'block', fontWeight: 700, fontSize: 15, color: 'var(--vm-text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {title}
        </span>
        {sub && <span className="vm-faint" style={{ fontSize: 12 }}>{sub}</span>}
      </span>
      {actions}
    </div>
  )
}

/** 视图一：项目列表。 */
const ProjectsView: FC<{ data: AssetsData; loading: boolean; reload: () => void; lang: 'zh' | 'en' }> = ({
  data,
  loading,
  reload,
  lang,
}) => {
  const navigate = useNavigate()
  const actions = useAssetActions(reload, lang)
  const [preview, setPreview] = useState<AssetFile | null>(null)

  const stats = data?.stats ?? {}
  const totalImages =
    (stats.screenshots ?? 0) + (stats.frames ?? 0) + (stats.grids ?? 0) + (stats.covers ?? 0)
  const totalText = (stats.transcripts ?? 0) + (stats.notes ?? 0) + (stats.video_transcripts ?? 0)
  const sharedCount = data?.shared.reduce((n, c) => n + c.files.length, 0) ?? 0

  const statCards = [
    { icon: <Film size={17} />, label: trVm('assetsProjects', lang), value: stats.projects ?? 0 },
    { icon: <AudioLines size={17} />, label: trVm('assetsAudio', lang), value: stats.audio ?? 0 },
    { icon: <ImageIcon size={17} />, label: trVm('assetsImages', lang), value: totalImages },
    { icon: <FileJson size={17} />, label: trVm('assetsText', lang), value: totalText },
    { icon: <FolderOpen size={17} />, label: trVm('assetsShared', lang), value: sharedCount },
  ]

  return (
    <div className="vm-page">
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 10, marginBottom: 14 }}>
        {statCards.map((s, i) => (
          <div key={i} className="vm-card vm-card-pad" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span
              style={{
                width: 34,
                height: 34,
                borderRadius: 9,
                display: 'grid',
                placeItems: 'center',
                background: 'var(--vm-accent-soft, #eef2ff)',
                color: 'var(--vm-accent, #4f46e5)',
                flexShrink: 0,
              }}
            >
              {s.icon}
            </span>
            <span style={{ minWidth: 0 }}>
              <span className="vm-mono" style={{ display: 'block', fontSize: 18, fontWeight: 700, color: 'var(--vm-text)' }}>
                {s.value}
              </span>
              <span className="vm-faint" style={{ fontSize: 12 }}>{s.label}</span>
            </span>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, marginBottom: 12, flexWrap: 'wrap' }}>
        <span style={{ fontWeight: 700, fontSize: 14, color: 'var(--vm-text)' }}>
          {trVm('assetsProjects', lang)}
          <span className="vm-faint vm-mono" style={{ fontSize: 12, marginLeft: 6 }}>
            {data?.projects.length ?? 0}
          </span>
        </span>
        <div style={{ display: 'flex', gap: 8 }}>
          {sharedCount > 0 && (
            <button className="vm-btn vm-btn-outline vm-btn-sm" onClick={() => navigate('/assets/shared')}>
              <FolderOpen size={14} />
              {trVm('assetsShared', lang)}
              <span className="vm-mono" style={{ fontSize: 11, marginLeft: 3 }}>{sharedCount}</span>
            </button>
          )}
          <button className="vm-btn vm-btn-outline vm-btn-sm" onClick={reload} disabled={loading}>
            {loading ? <Loader2 size={15} className="vm-spin" /> : <RefreshCcw size={15} />}
            {trVm('assetsRefresh', lang)}
          </button>
        </div>
      </div>

      {loading ? (
        <div className="vm-empty">
          <Loader2 size={28} className="vm-spin" />
          <p>{trVm('assetsLoading', lang)}</p>
        </div>
      ) : !data || data.projects.length === 0 ? (
        <div className="vm-empty">
          <FolderOpen size={30} />
          <p>{trVm('assetsEmpty', lang)}</p>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 14 }}>
          {data.projects.map(p => (
            <ProjectCard
              key={p.id}
              project={p}
              lang={lang}
              onOpen={() => navigate(`/assets/${encodeURIComponent(p.id)}`)}
              onOpenLocation={() =>
                openAsset({ scope: 'project', project_id: p.id }).catch(() => toast.error(trVm('assetsDeleteFail', lang)))
              }
              onDelete={() => actions.deleteProject(p)}
            />
          ))}
        </div>
      )}

      <PreviewModal file={preview} lang={lang} onClose={() => setPreview(null)} />
    </div>
  )
}

/** 视图二/三：项目详情 与 共享区（共用：分类头 + 文件网格）。 */
const DetailView: FC<{
  title: string
  sub?: string
  categories: AssetCategory[]
  projectId?: string
  loading: boolean
  reload: () => void
  lang: 'zh' | 'en'
  headerActions?: JSX.Element
}> = ({ title, sub, categories, projectId, loading, reload, lang, headerActions }) => {
  const actions = useAssetActions(reload, lang)
  const [preview, setPreview] = useState<AssetFile | null>(null)

  return (
    <div className="vm-page">
      <SectionHeader title={title} sub={sub} lang={lang} actions={headerActions} />

      {loading ? (
        <div className="vm-empty">
          <Loader2 size={28} className="vm-spin" />
          <p>{trVm('assetsLoading', lang)}</p>
        </div>
      ) : categories.length === 0 ? (
        <div className="vm-empty">
          <FolderOpen size={30} />
          <p>{trVm('assetsEmptyProject', lang)}</p>
        </div>
      ) : (
        categories.map(cat => (
          <CategorySection
            key={cat.id}
            cat={cat}
            projectId={projectId}
            lang={lang}
            onPreview={setPreview}
            onDeleteCategory={actions.deleteCategory}
            onDeleteFile={actions.deleteFile}
          />
        ))
      )}

      <PreviewModal file={preview} lang={lang} onClose={() => setPreview(null)} />
    </div>
  )
}

const Assets: FC = () => {
  const lang = useVmLang()
  const { projectId } = useParams<{ projectId: string }>()
  const location = useLocation()
  const isShared = location.pathname.endsWith('/shared')
  const { data, loading, reload } = useAssetData(lang)

  const project = useMemo(
    () => data?.projects.find(p => p.id === projectId) ?? null,
    [data, projectId],
  )
  const actions = useAssetActions(reload, lang)

  if (isShared) {
    return (
      <DetailView
        title={trVm('assetsShared', lang)}
        sub={trVm('assetsSharedSub', lang)}
        categories={data?.shared ?? []}
        loading={loading}
        reload={reload}
        lang={lang}
      />
    )
  }

  if (projectId) {
    return (
      <DetailView
        title={project?.name ?? projectId}
        sub={
          project
            ? `${platformTag(project.platform)} · ${project.created_at} · ${project.files_total} ${trVm('assetsProjectFiles', lang)}`
            : undefined
        }
        categories={project?.categories ?? []}
        projectId={projectId}
        loading={loading}
        reload={reload}
        lang={lang}
        headerActions={
          project ? (
            <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
              <button
                className="vm-btn vm-btn-outline vm-btn-sm"
                onClick={() =>
                  openAsset({ scope: 'project', project_id: project.id }).catch(() =>
                    toast.error(trVm('assetsDeleteFail', lang)),
                  )
                }
              >
                <FolderOpen size={14} />
                {trVm('assetsOpenLocation', lang)}
              </button>
              <button
                className="vm-btn vm-btn-outline vm-btn-sm"
                onClick={() => actions.deleteProject(project)}
                style={{ color: 'var(--vm-danger, #dc2626)' }}
              >
                <Trash2 size={14} />
                {trVm('assetsDeleteProject', lang)}
              </button>
            </div>
          ) : undefined
        }
      />
    )
  }

  return <ProjectsView data={data} loading={loading} reload={reload} lang={lang} />
}

export default Assets

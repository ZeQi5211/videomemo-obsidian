import { useEffect, useRef } from 'react'
import { useTaskStore } from '@/store/taskStore'
import { get_task_status } from '@/services/note.ts'
import toast from 'react-hot-toast'

/**
 * 自适应轮询：轮询间隔根据「当前活跃任务数」动态调整。
 * - 1~3 个任务：3s（进度显示灵敏，开销极低）
 * - 4~10 个任务：6s
 * - >10 个任务：10s（任务很多时摊平请求量，避免同一时刻打大量请求）
 * 每个任务单次轮询 = 1 个轻量 GET + 单条 DB 读（<1ms），开销可忽略；
 * 进度数字的实际跳动节奏由后端节流控制（约 10~20s 一次），
 * 因此任务多时放宽到 10s 也几乎不影响用户看到的进度体验。
 */
export const useTaskPolling = () => {
  const tasks = useTaskStore(state => state.tasks)
  const updateTaskContent = useTaskStore(state => state.updateTaskContent)
  const updateTaskStatus = useTaskStore(state => state.updateTaskStatus)
  const removeTask = useTaskStore(state => state.removeTask)

  const tasksRef = useRef(tasks)

  // 每次 tasks 更新，把最新的 tasks 同步进去
  useEffect(() => {
    tasksRef.current = tasks
  }, [tasks])

  const pendingCount = tasks.filter(
    task => task.status != 'SUCCESS' && task.status != 'FAILED'
  ).length
  const interval = pendingCount <= 3 ? 3000 : pendingCount <= 10 ? 6000 : 10000

  useEffect(() => {
    const timer = setInterval(async () => {
      const pendingTasks = tasksRef.current.filter(
        task => task.status != 'SUCCESS' && task.status != 'FAILED'
      )

      // 无活跃任务时跳过轮询
      if (pendingTasks.length === 0) return

      for (const task of pendingTasks) {
        try {
          const res = await get_task_status(task.id)
          const { status, paused, cache, progress } = res

          if (status === 'SUCCESS' && status !== task.status) {
            const result = res.result || {}
            updateTaskContent(task.id, {
              status,
              markdown: result.markdown,
              transcript: result.transcript,
              audioMeta: result.audio_meta,
              totalTokens: result.total_tokens,
              feishu: result.feishu, // 生成后自动推送飞书的结果（未推送则为 undefined）
              paused: false,
              cache,
              completedAt: new Date().toISOString(), // 补记完成时间
            })
            toast.success('笔记生成成功')
          } else if (status === 'FAILED' && status !== task.status) {
            updateTaskContent(task.id, { status, paused: false })
            console.warn(`⚠️ 任务 ${task.id} 失败`)
          } else if (
            status &&
            (status !== task.status || !!paused !== !!task.paused || cache !== task.cache || progress)
          ) {
            // 处理中：状态或暂停标记变化时同步（含流式生成进度）
            updateTaskContent(task.id, { status, paused: !!paused, cache, progress })
          }
        } catch (e) {
          console.error('❌ 任务轮询失败：', e)
          updateTaskContent(task.id, { status: 'FAILED' })
        }
      }
    }, interval)

    return () => clearInterval(timer)
  }, [interval])
}

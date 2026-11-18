import service from './index'

/**
 * 创建模拟
 * @param {Object} data - { project_id, graph_id?, enable_twitter?, enable_reddit? }
 */
export const createSimulation = (data) => {
  return service.post('/api/simulation/create', data)
}

/**
 * 准备模拟环境（异步任务）
 * @param {Object} data - { simulation_id, entity_types?, use_llm_for_profiles?, parallel_profile_count?, force_regenerate? }
 */
export const prepareSimulation = (data) => {
  return service.post('/api/simulation/prepare', data)
}

/**
 * 查询准备任务进度
 * @param {Object} data - { task_id?, simulation_id? }
 */
export const getPrepareStatus = (data) => {
  return service.post('/api/simulation/prepare/status', data)
}

/**
 * 获取模拟状态
 * @param {string} simulationId
 */
export const getSimulation = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}`)
}

/**
 * 获取模拟的 Agent Profiles
 * @param {string} simulationId
 * @param {string} [platform] - 'reddit' | 'twitter'（省略时由后端根据模拟配置自动选择）
 */
export const getSimulationProfiles = (simulationId, platform) => {
  const params = platform ? { platform } : {}
  return service.get(`/api/simulation/${simulationId}/profiles`, { params })
}

/**
 * 实时获取生成中的 Agent Profiles
 * @param {string} simulationId
 * @param {string} [platform] - 'reddit' | 'twitter'（省略时由后端根据模拟配置自动选择）
 */
export const getSimulationProfilesRealtime = (simulationId, platform) => {
  const params = platform ? { platform } : {}
  return service.get(`/api/simulation/${simulationId}/profiles/realtime`, { params })
}

/**
 * 获取模拟配置
 * @param {string} simulationId
 */
export const getSimulationConfig = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/config`)
}

/**
 * 实时获取生成中的模拟配置
 * @param {string} simulationId
 * @returns {Promise} 返回配置信息，包含元数据和配置内容
 */
export const getSimulationConfigRealtime = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/config/realtime`)
}

/**
 * 列出所有模拟
 * @param {string} projectId - 可选，按项目ID过滤
 */
export const listSimulations = (projectId) => {
  const params = projectId ? { project_id: projectId } : {}
  return service.get('/api/simulation/list', { params })
}

/**
 * 启动模拟
 * @param {Object} data - { simulation_id, platform?, max_rounds?, enable_graph_memory_update? }
 */
export const startSimulation = (data) => {
  return service.post('/api/simulation/start', data)
}

/**
 * 停止模拟
 * @param {Object} data - { simulation_id }
 */
export const stopSimulation = (data) => {
  return service.post('/api/simulation/stop', data)
}

/**
 * 获取模拟运行实时状态
 * @param {string} simulationId
 */
export const getRunStatus = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/run-status`)
}

/**
 * 获取模拟运行详细状态（包含最近动作）
 * @param {string} simulationId
 */
export const getRunStatusDetail = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/run-status/detail`)
}

/**
 * 获取模拟中的帖子
 * @param {string} simulationId
 * @param {string} [platform] - 'reddit' | 'twitter'（省略时由后端根据模拟配置自动选择）
 * @param {number} limit - 返回数量
 * @param {number} offset - 偏移量
 */
export const getSimulationPosts = (simulationId, platform, limit = 50, offset = 0) => {
  const params = { limit, offset }
  if (platform) params.platform = platform
  return service.get(`/api/simulation/${simulationId}/posts`, { params })
}

/**
 * 获取模拟时间线（按轮次汇总）
 * @param {string} simulationId
 * @param {number} startRound - 起始轮次
 * @param {number} endRound - 结束轮次
 */
export const getSimulationTimeline = (simulationId, startRound = 0, endRound = null) => {
  const params = { start_round: startRound }
  if (endRound !== null) {
    params.end_round = endRound
  }
  return service.get(`/api/simulation/${simulationId}/timeline`, { params })
}

/**
 * 获取Agent统计信息
 * @param {string} simulationId
 */
export const getAgentStats = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/agent-stats`)
}

/**
 * 获取模拟动作历史
 * @param {string} simulationId
 * @param {Object} params - { limit, offset, platform, agent_id, round_num }
 */
export const getSimulationActions = (simulationId, params = {}) => {
  return service.get(`/api/simulation/${simulationId}/actions`, { params })
}

/**
 * Hivemind analytics: activity per round, interaction network, influence and top posts
 * @param {string} simulationId
 */
export const getSimulationAnalytics = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/analytics`)
}

/**
 * Run dynamics: health card, cascade trees (branching / orphans), engagement consensus
 * @param {string} simulationId
 */
export const getSimulationDynamics = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/dynamics`)
}

/**
 * "What happened" recap: chaptered facts plus the best story available without an LLM call
 * @param {string} simulationId
 */
export const getSimulationRecap = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/recap`)
}

/**
 * Have the AI write (or, with force, rewrite) the "What happened" story and cache it
 * @param {string} simulationId
 * @param {boolean} force
 */
export const writeSimulationRecap = (simulationId, force = false) => {
  return service.post(`/api/simulation/${simulationId}/recap`, { force })
}

/**
 * Briefing: group and company facts plus the best reading available without an LLM call
 * @param {string} simulationId
 */
export const getSimulationBriefing = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/briefing`)
}

/**
 * Have the AI write (or, with force, rewrite) the briefing and cache it
 * @param {string} simulationId
 * @param {boolean} force
 */
export const writeSimulationBriefing = (simulationId, force = false) => {
  return service.post(`/api/simulation/${simulationId}/briefing`, { force })
}

/**
 * Absolute URL for the briefing PDF. write=true has the backend write the AI
 * reading and story first if they are missing (slow the first time, then cached).
 * @param {string} simulationId
 * @param {boolean} write
 */
export const consensusReportPdfUrl = (simulationId, write = false) => {
  const base = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:5001').replace(/\/$/, '')
  return `${base}/api/simulation/${simulationId}/consensus-report.pdf${write ? '?write=1' : ''}`
}

/**
 * Fetch the briefing PDF and hand it to the browser as a download.
 * @param {string} simulationId
 */
export const downloadBriefingPdf = async (simulationId) => {
  const res = await fetch(consensusReportPdfUrl(simulationId, true))
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new Error(body?.error || `HTTP ${res.status}`)
  }
  const url = URL.createObjectURL(await res.blob())
  const a = document.createElement('a')
  a.href = url
  a.download = `${simulationId}-hivemind-briefing.pdf`
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 10000)
}

/**
 * 关闭模拟环境（优雅退出）
 * @param {Object} data - { simulation_id, timeout? }
 */
export const closeSimulationEnv = (data) => {
  return service.post('/api/simulation/close-env', data)
}

/**
 * 获取模拟环境状态
 * @param {Object} data - { simulation_id }
 */
export const getEnvStatus = (data) => {
  return service.post('/api/simulation/env-status', data)
}

/**
 * 批量采访 Agent
 * @param {Object} data - { simulation_id, interviews: [{ agent_id, prompt }] }
 */
export const interviewAgents = (data) => {
  return service.post('/api/simulation/interview/batch', data)
}

/**
 * 获取历史模拟列表（带项目详情）
 * 用于首页历史项目展示
 * @param {number} limit - 返回数量限制
 */
export const getSimulationHistory = (limit = 20) => {
  return service.get('/api/simulation/history', { params: { limit } })
}

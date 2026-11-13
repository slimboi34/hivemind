<template>
  <div 
    class="history-database"
    :class="{ 'no-projects': projects.length === 0 && !loading }"
    ref="historyContainer"
  >
    <!-- 背景装饰：技术网格线（只在有项目时显示） -->
    <div v-if="projects.length > 0 || loading" class="tech-grid-bg">
      <div class="grid-pattern"></div>
      <div class="gradient-overlay"></div>
    </div>

    <!-- 标题区域 -->
    <div class="section-header">
      <div class="section-line"></div>
      <span class="section-title">{{ $t('history.title') }}</span>
      <div class="section-line"></div>
    </div>

    <!-- 卡片容器（只在有项目时显示） -->
    <div v-if="projects.length > 0" class="cards-container" :class="{ expanded: isExpanded }" :style="containerStyle">
      <div 
        v-for="(project, index) in projects" 
        :key="project.simulation_id"
        class="project-card"
        :class="{ expanded: isExpanded, hovering: hoveringCard === index }"
        :style="getCardStyle(index)"
        @mouseenter="hoveringCard = index"
        @mouseleave="hoveringCard = null"
        @click="navigateToProject(project)"
      >
        <!-- 卡片头部：simulation_id 和 功能可用状态 -->
        <div class="card-header">
          <span class="card-id">{{ formatSimulationId(project.simulation_id) }}</span>
          <div class="card-status-icons">
            <span 
              class="status-icon" 
              :class="{ available: project.project_id, unavailable: !project.project_id }"
              :title="$t('history.graphBuild')"
            >◇</span>
            <span 
              class="status-icon available" 
              :title="$t('history.envSetup')"
            >◈</span>
            <span 
              class="status-icon" 
              :class="{ available: project.report_id, unavailable: !project.report_id }"
              :title="$t('history.analysisReport')"
            >◆</span>
          </div>
        </div>

        <!-- 文件列表区域 -->
        <div class="card-files-wrapper">
          <!-- 角落装饰 - 取景框风格 -->
          <div class="corner-mark top-left-only"></div>
          
          <!-- 文件列表 -->
          <div class="files-list" v-if="project.files && project.files.length > 0">
            <div 
              v-for="(file, fileIndex) in project.files.slice(0, 3)" 
              :key="fileIndex"
              class="file-item"
            >
              <span class="file-tag" :class="getFileType(file.filename)">{{ getFileTypeLabel(file.filename) }}</span>
              <span class="file-name">{{ truncateFilename(file.filename, 20) }}</span>
            </div>
            <!-- 如果有更多文件，显示提示 -->
            <div v-if="project.files.length > 3" class="files-more">
              {{ $t('history.moreFiles', { count: project.files.length - 3 }) }}
            </div>
          </div>
          <!-- 无文件时的占位 -->
          <div class="files-empty" v-else>
            <span class="empty-file-icon">◇</span>
            <span class="empty-file-text">{{ $t('history.noFiles') }}</span>
          </div>
        </div>

        <!-- 卡片标题（使用模拟需求的前20字作为标题） -->
        <h3 class="card-title">{{ getSimulationTitle(project.simulation_requirement) }}</h3>

        <!-- 卡片描述（模拟需求完整展示） -->
        <p class="card-desc">{{ truncateText(project.simulation_requirement, 55) }}</p>

        <!-- 卡片底部 -->
        <div class="card-footer">
          <div class="card-datetime">
            <span class="card-date">{{ formatDate(project.created_at) }}</span>
            <span class="card-time">{{ formatTime(project.created_at) }}</span>
          </div>
          <span class="card-progress" :class="getProgressClass(project)">
            <span class="status-dot">●</span> {{ formatRounds(project) }}
          </span>
        </div>
        
        <!-- 底部装饰线 (hover时展开) -->
        <div class="card-bottom-line"></div>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-state">
      <span class="loading-spinner"></span>
      <span class="loading-text">{{ $t('history.loadingText') }}</span>
    </div>

    <!-- 历史回放详情弹窗 -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="selectedProject" class="modal-overlay" @click.self="closeModal">
          <div class="modal-content">
            <!-- 弹窗头部 -->
            <div class="modal-header">
              <div class="modal-title-section">
                <span class="modal-id">{{ formatSimulationId(selectedProject.simulation_id) }}</span>
                <span class="modal-progress" :class="getProgressClass(selectedProject)">
                  <span class="status-dot">●</span> {{ formatRounds(selectedProject) }}
                </span>
                <span class="modal-create-time">{{ formatDate(selectedProject.created_at) }} {{ formatTime(selectedProject.created_at) }}</span>
              </div>
              <button class="modal-close" @click="closeModal">×</button>
            </div>

            <!-- 弹窗内容 -->
            <div class="modal-body">
              <!-- 模拟需求 -->
              <div class="modal-section">
                <div class="modal-label">{{ $t('history.simRequirement') }}</div>
                <div class="modal-requirement">{{ selectedProject.simulation_requirement || $t('common.none') }}</div>
              </div>

              <!-- 文件列表 -->
              <div class="modal-section">
                <div class="modal-label">{{ $t('history.relatedFiles') }}</div>
                <div class="modal-files" v-if="selectedProject.files && selectedProject.files.length > 0">
                  <div v-for="(file, index) in selectedProject.files" :key="index" class="modal-file-item">
                    <span class="file-tag" :class="getFileType(file.filename)">{{ getFileTypeLabel(file.filename) }}</span>
                    <span class="modal-file-name">{{ file.filename }}</span>
                  </div>
                </div>
                <div class="modal-empty" v-else>{{ $t('history.noRelatedFiles') }}</div>
              </div>
            </div>

            <!-- 推演回放分割线 -->
            <div class="modal-divider">
              <span class="divider-line"></span>
              <span class="divider-text">{{ $t('history.replayTitle') }}</span>
              <span class="divider-line"></span>
            </div>

            <!-- 导航按钮 -->
            <div class="modal-actions">
              <button 
                class="modal-btn btn-project" 
                @click="goToProject"
                :disabled="!selectedProject.project_id"
              >
                <span class="btn-step">Step1</span>
                <span class="btn-icon">◇</span>
                <span class="btn-text">{{ $t('history.step1Button') }}</span>
              </button>
              <button 
                class="modal-btn btn-simulation" 
                @click="goToSimulation"
              >
                <span class="btn-step">Step2</span>
                <span class="btn-icon">◈</span>
                <span class="btn-text">{{ $t('history.step2Button') }}</span>
              </button>
              <button 
                class="modal-btn btn-report" 
                @click="goToReport"
                :disabled="!selectedProject.report_id"
              >
                <span class="btn-step">Step4</span>
                <span class="btn-icon">◆</span>
                <span class="btn-text">{{ $t('history.step4Button') }}</span>
              </button>
            </div>
            <!-- 不可回放提示 -->
            <div class="modal-playback-hint">
              <span class="hint-text">{{ $t('history.replayHint') }}</span>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, onActivated, watch, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { getSimulationHistory } from '../api/simulation'

const router = useRouter()
const route = useRoute()
const { t } = useI18n()

// 状态
const projects = ref([])
const loading = ref(true)
const isExpanded = ref(false)
const hoveringCard = ref(null)
const historyContainer = ref(null)
const selectedProject = ref(null)  // 当前选中的项目（用于弹窗）
let observer = null
let isAnimating = false  // 动画锁，防止闪烁
let expandDebounceTimer = null  // 防抖定时器
let pendingState = null  // 记录待执行的目标状态

// 卡片布局配置 - 调整为更宽的比例
const CARDS_PER_ROW = 4
const CARD_WIDTH = 280  
const CARD_HEIGHT = 280 
const CARD_GAP = 24

// 动态计算容器高度样式
const containerStyle = computed(() => {
  if (!isExpanded.value) {
    // 折叠态：固定高度
    return { minHeight: '420px' }
  }
  
  // 展开态：根据卡片数量动态计算高度
  const total = projects.value.length
  if (total === 0) {
    return { minHeight: '280px' }
  }
  
  const rows = Math.ceil(total / CARDS_PER_ROW)
  // 计算实际需要的高度：行数 * 卡片高度 + (行数-1) * 间距 + 少量底部间距
  const expandedHeight = rows * CARD_HEIGHT + (rows - 1) * CARD_GAP + 10
  
  return { minHeight: `${expandedHeight}px` }
})

// 获取卡片样式
const getCardStyle = (index) => {
  const total = projects.value.length
  
  if (isExpanded.value) {
    // 展开态：网格布局
    const transition = 'transform 700ms cubic-bezier(0.23, 1, 0.32, 1), opacity 700ms cubic-bezier(0.23, 1, 0.32, 1), box-shadow 0.3s ease, border-color 0.3s ease'

    const col = index % CARDS_PER_ROW
    const row = Math.floor(index / CARDS_PER_ROW)
    
    // 计算当前行的卡片数量，确保每行居中
    const currentRowStart = row * CARDS_PER_ROW
    const currentRowCards = Math.min(CARDS_PER_ROW, total - currentRowStart)
    
    const rowWidth = currentRowCards * CARD_WIDTH + (currentRowCards - 1) * CARD_GAP
    
    const startX = -(rowWidth / 2) + (CARD_WIDTH / 2)
    const colInRow = index % CARDS_PER_ROW
    const x = startX + colInRow * (CARD_WIDTH + CARD_GAP)
    
    // 向下展开，增加与标题的间距
    const y = 20 + row * (CARD_HEIGHT + CARD_GAP)

    return {
      transform: `translate(${x}px, ${y}px) rotate(0deg) scale(1)`,
      zIndex: 100 + index,
      opacity: 1,
      transition: transition
    }
  } else {
    // 折叠态：扇形堆叠
    const transition = 'transform 700ms cubic-bezier(0.23, 1, 0.32, 1), opacity 700ms cubic-bezier(0.23, 1, 0.32, 1), box-shadow 0.3s ease, border-color 0.3s ease'

    const centerIndex = (total - 1) / 2
    const offset = index - centerIndex
    
    const x = offset * 35
    // 调整起始位置，靠近标题但保持适当间距
    const y = 25 + Math.abs(offset) * 8
    const r = offset * 3
    const s = 0.95 - Math.abs(offset) * 0.05
    
    return {
      transform: `translate(${x}px, ${y}px) rotate(${r}deg) scale(${s})`,
      zIndex: 10 + index,
      opacity: 1,
      transition: transition
    }
  }
}

// 根据轮数进度获取样式类
const getProgressClass = (simulation) => {
  const current = simulation.current_round || 0
  const total = simulation.total_rounds || 0
  
  if (total === 0 || current === 0) {
    // 未开始
    return 'not-started'
  } else if (current >= total) {
    // 已完成
    return 'completed'
  } else {
    // 进行中
    return 'in-progress'
  }
}

// 格式化日期（只显示日期部分）
const formatDate = (dateStr) => {
  if (!dateStr) return ''
  try {
    const date = new Date(dateStr)
    // Use local date components (like formatTime below) so the displayed day
    // matches the displayed time. toISOString() converts to UTC and can show
    // the wrong day for non-UTC clients near midnight.
    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    return `${year}-${month}-${day}`
  } catch {
    return dateStr?.slice(0, 10) || ''
  }
}

// 格式化时间（显示时:分）
const formatTime = (dateStr) => {
  if (!dateStr) return ''
  try {
    const date = new Date(dateStr)
    const hours = date.getHours().toString().padStart(2, '0')
    const minutes = date.getMinutes().toString().padStart(2, '0')
    return `${hours}:${minutes}`
  } catch {
    return ''
  }
}

// 截断文本
const truncateText = (text, maxLength) => {
  if (!text) return ''
  return text.length > maxLength ? text.slice(0, maxLength) + '...' : text
}

// 从模拟需求生成标题（取前20字）
const getSimulationTitle = (requirement) => {
  if (!requirement) return t('history.untitledSimulation')
  const title = requirement.slice(0, 20)
  return requirement.length > 20 ? title + '...' : title
}

// 格式化 simulation_id 显示（截取前6位）
const formatSimulationId = (simulationId) => {
  if (!simulationId) return 'SIM_UNKNOWN'
  const prefix = simulationId.replace('sim_', '').slice(0, 6)
  return `SIM_${prefix.toUpperCase()}`
}

// 格式化轮数显示（当前轮/总轮数）
const formatRounds = (simulation) => {
  const current = simulation.current_round || 0
  const total = simulation.total_rounds || 0
  if (total === 0) return t('history.notStarted')
  return t('history.roundsProgress', { current, total })
}

// 获取文件类型（用于样式）
const getFileType = (filename) => {
  if (!filename) return 'other'
  const ext = filename.split('.').pop()?.toLowerCase()
  const typeMap = {
    'pdf': 'pdf',
    'doc': 'doc', 'docx': 'doc',
    'xls': 'xls', 'xlsx': 'xls', 'csv': 'xls',
    'ppt': 'ppt', 'pptx': 'ppt',
    'txt': 'txt', 'md': 'txt', 'json': 'code',
    'jpg': 'img', 'jpeg': 'img', 'png': 'img', 'gif': 'img',
    'zip': 'zip', 'rar': 'zip', '7z': 'zip'
  }
  return typeMap[ext] || 'other'
}

// 获取文件类型标签文本
const getFileTypeLabel = (filename) => {
  if (!filename) return 'FILE'
  const ext = filename.split('.').pop()?.toUpperCase()
  return ext || 'FILE'
}

// 截断文件名（保留扩展名）
const truncateFilename = (filename, maxLength) => {
  if (!filename) return t('history.unknownFile')
  if (filename.length <= maxLength) return filename
  
  const ext = filename.includes('.') ? '.' + filename.split('.').pop() : ''
  const nameWithoutExt = filename.slice(0, filename.length - ext.length)
  const truncatedName = nameWithoutExt.slice(0, maxLength - ext.length - 3) + '...'
  return truncatedName + ext
}

// 打开项目详情弹窗
const navigateToProject = (simulation) => {
  selectedProject.value = simulation
}

// 关闭弹窗
const closeModal = () => {
  selectedProject.value = null
}

// 导航到图谱构建页面（Project）
const goToProject = () => {
  if (selectedProject.value?.project_id) {
    router.push({
      name: 'Process',
      params: { projectId: selectedProject.value.project_id }
    })
    closeModal()
  }
}

// 导航到环境配置页面（Simulation）
const goToSimulation = () => {
  if (selectedProject.value?.simulation_id) {
    router.push({
      name: 'Simulation',
      params: { simulationId: selectedProject.value.simulation_id }
    })
    closeModal()
  }
}

// 导航到分析报告页面（Report）
const goToReport = () => {
  if (selectedProject.value?.report_id) {
    router.push({
      name: 'Report',
      params: { reportId: selectedProject.value.report_id }
    })
    closeModal()
  }
}

// 加载历史项目
const loadHistory = async () => {
  try {
    loading.value = true
    const response = await getSimulationHistory(20)
    if (response.success) {
      projects.value = response.data || []
    }
  } catch (error) {
    console.error('加载历史项目失败:', error)
    projects.value = []
  } finally {
    loading.value = false
  }
}

// 初始化 IntersectionObserver
const initObserver = () => {
  if (observer) {
    observer.disconnect()
  }
  
  observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        const shouldExpand = entry.isIntersecting
        
        // 更新待执行的目标状态（无论是否在动画中都要记录最新的目标状态）
        pendingState = shouldExpand
        
        // 清除之前的防抖定时器（新的滚动意图会覆盖旧的）
        if (expandDebounceTimer) {
          clearTimeout(expandDebounceTimer)
          expandDebounceTimer = null
        }
        
        // 如果正在动画中，只记录状态，等动画结束后处理
        if (isAnimating) return
        
        // 如果目标状态与当前状态相同，不需要处理
        if (shouldExpand === isExpanded.value) {
          pendingState = null
          return
        }
        
        // 使用防抖延迟状态切换，防止快速闪烁
        // 展开时延迟较短(50ms)，收起时延迟较长(200ms)以增加稳定性
        const delay = shouldExpand ? 50 : 200
        
        expandDebounceTimer = setTimeout(() => {
          // 检查是否正在动画
          if (isAnimating) return
          
          // 检查待执行状态是否仍需要执行（可能已被后续滚动覆盖）
          if (pendingState === null || pendingState === isExpanded.value) return
          
          // 设置动画锁
          isAnimating = true
          isExpanded.value = pendingState
          pendingState = null
          
          // 动画完成后解除锁定，并检查是否有待处理的状态变化
          setTimeout(() => {
            isAnimating = false
            
            // 动画结束后，检查是否有新的待执行状态
            if (pendingState !== null && pendingState !== isExpanded.value) {
              // 延迟一小段时间再执行，避免太快切换
              expandDebounceTimer = setTimeout(() => {
                if (pendingState !== null && pendingState !== isExpanded.value) {
                  isAnimating = true
                  isExpanded.value = pendingState
                  pendingState = null
                  setTimeout(() => {
                    isAnimating = false
                  }, 750)
                }
              }, 100)
            }
          }, 750)
        }, delay)
      })
    },
    {
      // 使用多个阈值，使检测更平滑
      threshold: [0.4, 0.6, 0.8],
      // 调整 rootMargin，视口底部向上收缩，需要滚动更多才触发展开
      rootMargin: '0px 0px -150px 0px'
    }
  )
  
  // 开始观察
  if (historyContainer.value) {
    observer.observe(historyContainer.value)
  }
}

// 监听路由变化，当返回首页时重新加载数据
watch(() => route.path, (newPath) => {
  if (newPath === '/') {
    loadHistory()
  }
})

onMounted(async () => {
  // 确保 DOM 渲染完成后再加载数据
  await nextTick()
  await loadHistory()
  
  // 等待 DOM 渲染后初始化观察器
  setTimeout(() => {
    initObserver()
  }, 100)
})

// 如果使用 keep-alive，在组件激活时重新加载数据
onActivated(() => {
  loadHistory()
})

onUnmounted(() => {
  // 清理 Intersection Observer
  if (observer) {
    observer.disconnect()
    observer = null
  }
  // 清理防抖定时器
  if (expandDebounceTimer) {
    clearTimeout(expandDebounceTimer)
    expandDebounceTimer = null
  }
})
</script>

<style scoped>
/* Past simulations on Home. Card positions come from getCardStyle() in the script. */
.history-database {
  position: relative;
  width: 100%;
  min-height: 280px;
  padding: var(--hm-space-10) 0;
  border-top: 1px solid var(--hm-line);
  overflow: visible;
}

.history-database.no-projects {
  min-height: auto;
  padding: var(--hm-space-10) 0 var(--hm-space-5);
}

/* The old decorative grid is retired; the page's hairlines carry the structure. */
.tech-grid-bg {
  display: none;
}

.section-header {
  position: relative;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--hm-space-5);
  margin-bottom: var(--hm-space-8);
}

.section-line {
  flex: 1;
  max-width: 280px;
  height: 1px;
  background: var(--hm-line);
}

.section-title {
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-2xs);
  font-weight: 500;
  letter-spacing: var(--hm-tracking-label);
  text-transform: uppercase;
  color: var(--hm-ink-4);
}

/* Card deck */
.cards-container {
  position: relative;
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding: 0 var(--hm-space-10);
  transition: min-height 700ms cubic-bezier(0.23, 1, 0.32, 1);
}

.project-card {
  position: absolute;
  width: 280px;
  padding: var(--hm-space-4);
  background: var(--hm-surface);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-lg);
  box-shadow: var(--hm-shadow-xs);
  overflow: hidden;
  cursor: pointer;
  transition: box-shadow var(--hm-duration) var(--hm-ease), border-color var(--hm-duration) var(--hm-ease),
    transform 700ms cubic-bezier(0.23, 1, 0.32, 1), opacity 700ms cubic-bezier(0.23, 1, 0.32, 1);
}

.project-card:hover {
  border-color: var(--hm-line-strong);
  box-shadow: var(--hm-shadow-md);
  z-index: 1000 !important;
}

.project-card.hovering {
  z-index: 1000 !important;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--hm-space-3);
  padding-bottom: var(--hm-space-3);
  border-bottom: 1px solid var(--hm-line);
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-2xs);
}

.card-id {
  color: var(--hm-ink-3);
  font-weight: 500;
  letter-spacing: 0.06em;
}

/* Which stages can be reopened: graph, setup, report */
.card-status-icons {
  display: flex;
  align-items: center;
  gap: 6px;
}

.status-icon {
  font-size: var(--hm-text-xs);
  cursor: default;
}

.status-icon.available {
  color: var(--hm-ink);
}

.status-icon.unavailable {
  color: var(--hm-ink-5);
  opacity: 0.6;
}

.card-progress {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 500;
  font-size: var(--hm-text-2xs);
  letter-spacing: 0.04em;
}

.status-dot {
  font-size: 7px;
}

.card-progress.completed { color: var(--hm-success); }
.card-progress.in-progress { color: var(--hm-signal-ink); }
.card-progress.not-started { color: var(--hm-ink-4); }
.card-status.pending { color: var(--hm-ink-4); }

/* Seed documents */
.card-files-wrapper {
  position: relative;
  width: 100%;
  min-height: 48px;
  max-height: 110px;
  margin-bottom: var(--hm-space-3);
  padding: var(--hm-space-2);
  background: var(--hm-surface-2);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-md);
  overflow: hidden;
}

.files-list {
  display: flex;
  flex-direction: column;
  gap: var(--hm-space-1);
}

.files-more {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2px 6px;
  font-family: var(--hm-font-mono);
  font-size: 10px;
  color: var(--hm-ink-4);
}

.file-item {
  display: flex;
  align-items: center;
  gap: var(--hm-space-2);
  padding: 3px 4px;
  border-radius: var(--hm-radius-xs);
}

.file-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  min-width: 30px;
  height: 16px;
  padding: 0 4px;
  border-radius: 2px;
  background: var(--hm-surface-3);
  color: var(--hm-ink-3);
  font-family: var(--hm-font-mono);
  font-size: 9px;
  font-weight: 500;
  line-height: 1;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.file-name {
  overflow: hidden;
  font-size: var(--hm-text-xs);
  color: var(--hm-ink-2);
  white-space: nowrap;
  text-overflow: ellipsis;
}

.files-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--hm-space-2);
  height: 48px;
  color: var(--hm-ink-4);
}

.empty-file-icon {
  opacity: 0.5;
}

.empty-file-text {
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-2xs);
}

.corner-mark {
  display: none;
}

.card-title {
  margin: 0 0 var(--hm-space-1);
  overflow: hidden;
  font-size: var(--hm-text-base);
  font-weight: 500;
  line-height: 1.4;
  color: var(--hm-ink);
  white-space: nowrap;
  text-overflow: ellipsis;
}

.card-desc {
  display: -webkit-box;
  height: 36px;
  margin: 0 0 var(--hm-space-4);
  overflow: hidden;
  font-size: var(--hm-text-xs);
  line-height: 1.5;
  color: var(--hm-ink-4);
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.card-footer {
  position: relative;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: var(--hm-space-3);
  border-top: 1px solid var(--hm-line);
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-2xs);
  color: var(--hm-ink-4);
}

.card-datetime {
  display: flex;
  align-items: center;
  gap: var(--hm-space-2);
}

/* Signal bar slides in under the hovered card */
.card-bottom-line {
  position: absolute;
  bottom: 0;
  left: 0;
  z-index: 20;
  width: 0;
  height: 2px;
  background-color: var(--hm-signal);
  transition: width 0.5s cubic-bezier(0.23, 1, 0.32, 1);
}

.project-card:hover .card-bottom-line {
  width: 100%;
}

.empty-state,
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--hm-space-3);
  padding: var(--hm-space-12);
  color: var(--hm-ink-4);
  font-size: var(--hm-text-sm);
}

.loading-spinner {
  width: 20px;
  height: 20px;
  border: 2px solid var(--hm-line-strong);
  border-top-color: var(--hm-ink);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 1200px) {
  .project-card {
    width: 240px;
  }
}

@media (max-width: 768px) {
  .cards-container {
    padding: 0 var(--hm-space-5);
  }

  .project-card {
    width: 200px;
  }
}

/* ------------------------------------------------- replay dialog */
.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--hm-overlay);
  backdrop-filter: blur(2px);
}

.modal-content {
  width: 560px;
  max-width: 90vw;
  max-height: 85vh;
  overflow-y: auto;
  background: var(--hm-surface);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-lg);
  box-shadow: var(--hm-shadow-lg);
}

.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-active .modal-content,
.modal-leave-active .modal-content {
  transition: transform 0.2s var(--hm-ease), opacity 0.2s ease;
}

.modal-enter-from .modal-content,
.modal-leave-to .modal-content {
  transform: translateY(8px);
  opacity: 0;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--hm-space-4) var(--hm-space-6);
  border-bottom: 1px solid var(--hm-line);
}

.modal-title-section {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--hm-space-3);
}

.modal-id {
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-sm);
  font-weight: 500;
  letter-spacing: 0.06em;
  color: var(--hm-ink);
}

.modal-progress {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 22px;
  padding: 0 var(--hm-space-2);
  border-radius: var(--hm-radius-pill);
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-2xs);
  font-weight: 500;
  background: var(--hm-surface-3);
}

.modal-progress.completed { color: var(--hm-success); background: var(--hm-success-soft); }
.modal-progress.in-progress { color: var(--hm-signal-ink); background: var(--hm-signal-soft); }
.modal-progress.not-started { color: var(--hm-ink-4); background: var(--hm-surface-3); }

.modal-create-time {
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-2xs);
  color: var(--hm-ink-4);
}

.modal-close {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: var(--hm-radius-sm);
  background: transparent;
  color: var(--hm-ink-4);
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
  transition: background-color var(--hm-duration-fast) var(--hm-ease), color var(--hm-duration-fast) var(--hm-ease);
}

.modal-close:hover {
  background: var(--hm-surface-3);
  color: var(--hm-ink);
}

.modal-body {
  padding: var(--hm-space-6);
}

.modal-section {
  margin-bottom: var(--hm-space-6);
}

.modal-section:last-child {
  margin-bottom: 0;
}

.modal-label {
  margin-bottom: var(--hm-space-2);
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-2xs);
  font-weight: 500;
  letter-spacing: var(--hm-tracking-label);
  text-transform: uppercase;
  color: var(--hm-ink-4);
}

.modal-requirement {
  padding: var(--hm-space-4);
  background: var(--hm-surface-2);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-md);
  font-size: var(--hm-text-base);
  line-height: 1.6;
  color: var(--hm-ink-2);
}

.modal-files {
  display: flex;
  flex-direction: column;
  gap: var(--hm-space-2);
  max-height: 200px;
  overflow-y: auto;
}

.modal-file-item {
  display: flex;
  align-items: center;
  gap: var(--hm-space-3);
  padding: var(--hm-space-2) var(--hm-space-3);
  background: var(--hm-surface);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-md);
}

.modal-file-name {
  flex: 1;
  overflow: hidden;
  font-size: var(--hm-text-sm);
  color: var(--hm-ink-2);
  white-space: nowrap;
  text-overflow: ellipsis;
}

.modal-empty {
  padding: var(--hm-space-4);
  background: var(--hm-surface-2);
  border: 1px dashed var(--hm-line-strong);
  border-radius: var(--hm-radius-md);
  font-size: var(--hm-text-sm);
  color: var(--hm-ink-4);
  text-align: center;
}

.modal-divider {
  display: flex;
  align-items: center;
  gap: var(--hm-space-4);
  padding: 0 var(--hm-space-6);
}

.divider-line {
  flex: 1;
  height: 1px;
  background: var(--hm-line);
}

.divider-text {
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-2xs);
  letter-spacing: var(--hm-tracking-label);
  text-transform: uppercase;
  color: var(--hm-ink-4);
  white-space: nowrap;
}

.modal-actions {
  display: flex;
  gap: var(--hm-space-3);
  padding: var(--hm-space-5) var(--hm-space-6);
}

.modal-btn {
  position: relative;
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: var(--hm-space-4) var(--hm-space-3);
  background: var(--hm-surface);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-md);
  cursor: pointer;
  transition: border-color var(--hm-duration-fast) var(--hm-ease), background-color var(--hm-duration-fast) var(--hm-ease);
}

.modal-btn:hover:not(:disabled) {
  background: var(--hm-surface-2);
  border-color: var(--hm-ink);
}

.modal-btn:disabled {
  background: var(--hm-surface-2);
  opacity: 0.45;
  cursor: not-allowed;
}

.btn-step {
  font-family: var(--hm-font-mono);
  font-size: 10px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--hm-ink-4);
}

.btn-icon {
  font-size: 20px;
  line-height: 1;
  color: var(--hm-ink);
}

.modal-btn:hover:not(:disabled) .btn-icon {
  color: var(--hm-signal);
}

.btn-text {
  font-size: var(--hm-text-sm);
  font-weight: 500;
  color: var(--hm-ink-2);
}

.modal-btn:hover:not(:disabled) .btn-text {
  color: var(--hm-ink);
}

.modal-playback-hint {
  display: flex;
  justify-content: center;
  padding: 0 var(--hm-space-6) var(--hm-space-5);
}

.hint-text {
  font-size: var(--hm-text-xs);
  line-height: 1.5;
  color: var(--hm-ink-4);
  text-align: center;
}
</style>

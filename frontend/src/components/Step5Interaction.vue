<template>
  <div class="interaction-panel">
    <!-- Main Split Layout -->
    <div class="main-split-layout">
      <!-- LEFT PANEL: Report Style -->
      <div class="left-panel report-style" ref="leftPanel">
        <div v-if="reportOutline" class="report-content-wrapper">
          <!-- Report Header -->
          <div class="report-header-block">
            <div class="report-meta">
              <span class="report-tag">Prediction Report</span>
              <span class="report-id">ID: {{ reportId || 'REF-2024-X92' }}</span>
            </div>
            <h1 class="main-title">{{ reportOutline.title }}</h1>
            <p class="sub-title">{{ reportOutline.summary }}</p>
            <div class="header-divider"></div>
          </div>

          <!-- Sections List -->
          <div class="sections-list">
            <div 
              v-for="(section, idx) in reportOutline.sections" 
              :key="idx"
              class="report-section-item"
              :class="{ 
                'is-active': currentSectionIndex === idx + 1,
                'is-completed': isSectionCompleted(idx + 1),
                'is-pending': !isSectionCompleted(idx + 1) && currentSectionIndex !== idx + 1
              }"
            >
              <div class="section-header-row" @click="toggleSectionCollapse(idx)" :class="{ 'clickable': isSectionCompleted(idx + 1) }">
                <span class="section-number">{{ String(idx + 1).padStart(2, '0') }}</span>
                <h3 class="section-title">{{ section.title }}</h3>
                <svg 
                  v-if="isSectionCompleted(idx + 1)" 
                  class="collapse-icon" 
                  :class="{ 'is-collapsed': collapsedSections.has(idx) }"
                  viewBox="0 0 24 24" 
                  width="20" 
                  height="20" 
                  fill="none" 
                  stroke="currentColor" 
                  stroke-width="2"
                >
                  <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
              </div>
              
              <div class="section-body" v-show="!collapsedSections.has(idx)">
                <!-- Completed Content -->
                <div v-if="generatedSections[idx + 1]" class="generated-content" v-html="renderMarkdown(generatedSections[idx + 1])"></div>
                
                <!-- Loading State -->
                <div v-else-if="currentSectionIndex === idx + 1" class="loading-state">
                  <div class="loading-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                      <circle cx="12" cy="12" r="10" stroke-width="4" stroke="#E5E7EB"></circle>
                      <path d="M12 2a10 10 0 0 1 10 10" stroke-width="4" stroke="#4B5563" stroke-linecap="round"></path>
                    </svg>
                  </div>
                  <span class="loading-text">{{ $t('step4.generatingSection', { title: section.title }) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Waiting State -->
        <div v-if="!reportOutline" class="waiting-placeholder">
          <div class="waiting-animation">
            <div class="waiting-ring"></div>
            <div class="waiting-ring"></div>
            <div class="waiting-ring"></div>
          </div>
          <span class="waiting-text">Waiting for Report Agent...</span>
        </div>
      </div>

      <!-- RIGHT PANEL: Interaction Interface -->
      <div class="right-panel" ref="rightPanel">
        <!-- Unified Action Bar - Professional Design -->
        <div class="action-bar">
        <div class="action-bar-header">
          <svg class="action-bar-icon" viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
          </svg>
          <div class="action-bar-text">
            <span class="action-bar-title">{{ $t('step5.interactiveTools') }}</span>
            <span class="action-bar-subtitle mono">{{ $t('step5.agentsAvailable', { count: profiles.length }) }}</span>
          </div>
        </div>
          <div class="action-bar-tabs">
            <button 
              class="tab-pill"
              :class="{ active: activeTab === 'chat' && chatTarget === 'report_agent' }"
              @click="selectReportAgentChat"
            >
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path>
              </svg>
              <span>{{ $t('step5.chatWithReportAgent') }}</span>
            </button>
            <div class="agent-dropdown" v-if="profiles.length > 0">
              <button 
                class="tab-pill agent-pill"
                :class="{ active: activeTab === 'chat' && chatTarget === 'agent' }"
                @click="toggleAgentDropdown"
              >
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                  <circle cx="12" cy="7" r="4"></circle>
                </svg>
                <span>{{ selectedAgent ? selectedAgent.username : $t('step5.chatWithAgent') }}</span>
                <svg class="dropdown-arrow" :class="{ open: showAgentDropdown }" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
              </button>
              <div v-if="showAgentDropdown" class="dropdown-menu">
                <div class="dropdown-header">{{ $t('step5.selectChatTarget') }}</div>
                <div 
                  v-for="(agent, idx) in profiles" 
                  :key="idx"
                  class="dropdown-item"
                  @click="selectAgent(agent, idx)"
                >
                  <div class="agent-avatar">{{ (agent.username || 'A')[0] }}</div>
                  <div class="agent-info">
                    <span class="agent-name">{{ agent.username }}</span>
                    <span class="agent-role">{{ agent.profession || $t('step2.unknownProfession') }}</span>
                  </div>
                </div>
              </div>
            </div>
            <div class="tab-divider"></div>
            <button
              class="tab-pill survey-pill"
              :class="{ active: activeTab === 'survey' }"
              @click="selectSurveyTab"
            >
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M9 11l3 3L22 4"></path>
                <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>
              </svg>
              <span>{{ $t('step5.sendSurvey') }}</span>
            </button>
          </div>
        </div>

        <!-- Chat Mode -->
        <div v-if="activeTab === 'chat'" class="chat-container">

          <!-- Report Agent Tools Card -->
          <div v-if="chatTarget === 'report_agent'" class="report-agent-tools-card">
            <div class="tools-card-header">
              <div class="tools-card-avatar">R</div>
              <div class="tools-card-info">
                <div class="tools-card-name">{{ $t('step5.reportAgentChat') }}</div>
                <div class="tools-card-subtitle">{{ $t('step5.reportAgentDesc') }}</div>
              </div>
              <button class="tools-card-toggle" @click="showToolsDetail = !showToolsDetail">
                <svg :class="{ 'is-expanded': showToolsDetail }" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
              </button>
            </div>
            <div v-if="showToolsDetail" class="tools-card-body">
              <div class="tools-grid">
                <div class="tool-item tool-purple">
                  <div class="tool-icon-wrapper">
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M9 18h6M10 22h4M12 2a7 7 0 0 0-4 12.5V17a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1v-2.5A7 7 0 0 0 12 2z"></path>
                    </svg>
                  </div>
                  <div class="tool-content">
                    <div class="tool-name">{{ $t('step5.toolInsightForge') }}</div>
                    <div class="tool-desc">{{ $t('step5.toolInsightForgeDesc') }}</div>
                  </div>
                </div>
                <div class="tool-item tool-blue">
                  <div class="tool-icon-wrapper">
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                      <circle cx="12" cy="12" r="10"></circle>
                      <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
                    </svg>
                  </div>
                  <div class="tool-content">
                    <div class="tool-name">{{ $t('step5.toolPanoramaSearch') }}</div>
                    <div class="tool-desc">{{ $t('step5.toolPanoramaSearchDesc') }}</div>
                  </div>
                </div>
                <div class="tool-item tool-orange">
                  <div class="tool-icon-wrapper">
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
                    </svg>
                  </div>
                  <div class="tool-content">
                    <div class="tool-name">{{ $t('step5.toolQuickSearch') }}</div>
                    <div class="tool-desc">{{ $t('step5.toolQuickSearchDesc') }}</div>
                  </div>
                </div>
                <div class="tool-item tool-green">
                  <div class="tool-icon-wrapper">
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
                      <circle cx="9" cy="7" r="4"></circle>
                      <path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"></path>
                    </svg>
                  </div>
                  <div class="tool-content">
                    <div class="tool-name">{{ $t('step5.toolInterviewSubAgent') }}</div>
                    <div class="tool-desc">{{ $t('step5.toolInterviewSubAgentDesc') }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Agent Profile Card -->
          <div v-if="chatTarget === 'agent' && selectedAgent" class="agent-profile-card">
            <div class="profile-card-header">
              <div class="profile-card-avatar">{{ (selectedAgent.username || 'A')[0] }}</div>
              <div class="profile-card-info">
                <div class="profile-card-name">{{ selectedAgent.username }}</div>
                <div class="profile-card-meta">
                  <span v-if="selectedAgent.name" class="profile-card-handle">@{{ selectedAgent.name }}</span>
                  <span class="profile-card-profession">{{ selectedAgent.profession || $t('step2.unknownProfession') }}</span>
                </div>
              </div>
              <button class="profile-card-toggle" @click="showFullProfile = !showFullProfile">
                <svg :class="{ 'is-expanded': showFullProfile }" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
              </button>
            </div>
            <div v-if="showFullProfile && selectedAgent.bio" class="profile-card-body">
              <div class="profile-card-bio">
                <div class="profile-card-label">{{ $t('step5.profileBio') }}</div>
                <p>{{ selectedAgent.bio }}</p>
              </div>
            </div>
          </div>

          <!-- Chat Messages -->
          <div class="chat-messages" ref="chatMessages">
            <div v-if="chatTarget === 'agent' && agentsOffline" class="offline-note">{{ $t('step5.agentsOffline') }}</div>
            <div v-if="chatHistory.length === 0 && !(chatTarget === 'agent' && agentsOffline)" class="chat-empty">
              <div class="empty-icon">
                <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                </svg>
              </div>
              <p class="empty-text">
                {{ chatTarget === 'report_agent' ? $t('step5.chatEmptyReportAgent') : $t('step5.chatEmptyAgent') }}
              </p>
            </div>
            <div 
              v-for="(msg, idx) in chatHistory" 
              :key="idx"
              class="chat-message"
              :class="msg.role"
            >
              <div class="message-avatar">
                <span v-if="msg.role === 'user'">U</span>
                <span v-else>{{ msg.role === 'assistant' && chatTarget === 'report_agent' ? 'R' : (selectedAgent?.username?.[0] || 'A') }}</span>
              </div>
              <div class="message-content">
                <div class="message-header">
                  <span class="sender-name">
                    {{ msg.role === 'user' ? 'You' : (chatTarget === 'report_agent' ? 'Report Agent' : (selectedAgent?.username || 'Agent')) }}
                  </span>
                  <span class="message-time">{{ formatTime(msg.timestamp) }}</span>
                </div>
                <div class="message-text" v-html="renderMarkdown(msg.content)"></div>
              </div>
            </div>
            <div v-if="isSending" class="chat-message assistant">
              <div class="message-avatar">
                <span>{{ chatTarget === 'report_agent' ? 'R' : (selectedAgent?.username?.[0] || 'A') }}</span>
              </div>
              <div class="message-content">
                <div class="typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            </div>
          </div>

          <!-- Chat Input -->
          <div class="chat-input-area">
            <textarea 
              v-model="chatInput"
              class="chat-input"
              :placeholder="$t('step5.chatInputPlaceholder')"
              @keydown.enter.exact.prevent="sendMessage"
              :disabled="isSending || (chatTarget === 'agent' && (!selectedAgent || agentsOffline))"
              rows="1"
              ref="chatInputRef"
            ></textarea>
            <button 
              class="send-btn"
              @click="sendMessage"
              :disabled="!chatInput.trim() || isSending || (chatTarget === 'agent' && (!selectedAgent || agentsOffline))"
            >
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="22" y1="2" x2="11" y2="13"></line>
                <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
              </svg>
            </button>
          </div>
        </div>

        <!-- Survey Mode -->
        <div v-if="activeTab === 'survey'" class="survey-container">
          <!-- Survey Setup -->
          <div class="survey-setup">
            <div class="setup-section">
              <div class="section-header">
                <span class="section-title">{{ $t('step5.selectSurveyTarget') }}</span>
                <span class="selection-count">{{ $t('step5.selectedCount', { selected: selectedAgents.size, total: profiles.length }) }}</span>
              </div>
              <div class="agents-grid">
                <label 
                  v-for="(agent, idx) in profiles" 
                  :key="idx"
                  class="agent-checkbox"
                  :class="{ checked: selectedAgents.has(idx) }"
                >
                  <input 
                    type="checkbox" 
                    :checked="selectedAgents.has(idx)"
                    @change="toggleAgentSelection(idx)"
                  >
                  <div class="checkbox-avatar">{{ (agent.username || 'A')[0] }}</div>
                  <div class="checkbox-info">
                    <span class="checkbox-name">{{ agent.username }}</span>
                    <span class="checkbox-role">{{ agent.profession || $t('step2.unknownProfession') }}</span>
                  </div>
                  <div class="checkbox-indicator">
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="3">
                      <polyline points="20 6 9 17 4 12"></polyline>
                    </svg>
                  </div>
                </label>
              </div>
              <div class="selection-actions">
                <button class="action-link" @click="selectAllAgents">{{ $t('step5.selectAll') }}</button>
                <span class="action-divider">|</span>
                <button class="action-link" @click="clearAgentSelection">{{ $t('step5.clearSelection') }}</button>
              </div>
            </div>

            <div class="setup-section">
              <div class="section-header">
                <span class="section-title">{{ $t('step5.surveyQuestions') }}</span>
              </div>
              <textarea 
                v-model="surveyQuestion"
                class="survey-input"
                :placeholder="$t('step5.surveyInputPlaceholder')"
                rows="3"
              ></textarea>
            </div>

            <div v-if="agentsOffline" class="offline-note">{{ $t('step5.agentsOffline') }}</div>
            <button 
              class="survey-submit-btn"
              :disabled="agentsOffline || selectedAgents.size === 0 || !surveyQuestion.trim() || isSurveying"
              @click="submitSurvey"
            >
              <span v-if="isSurveying" class="loading-spinner"></span>
              <span v-else>{{ $t('step5.submitSurvey') }}</span>
            </button>
          </div>

          <!-- Survey Results -->
          <div v-if="surveyResults.length > 0" class="survey-results">
            <div class="results-header">
              <span class="results-title">{{ $t('step5.surveyResults') }}</span>
              <span class="results-count">{{ $t('step5.surveyResultsCount', { count: surveyResults.length }) }}</span>
            </div>
            <div class="results-list">
              <div 
                v-for="(result, idx) in surveyResults" 
                :key="idx"
                class="result-card"
              >
                <div class="result-header">
                  <div class="result-avatar">{{ (result.agent_name || 'A')[0] }}</div>
                  <div class="result-info">
                    <span class="result-name">{{ result.agent_name }}</span>
                    <span class="result-role">{{ result.profession || $t('step2.unknownProfession') }}</span>
                  </div>
                </div>
                <div class="result-question">
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"></circle>
                    <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path>
                    <line x1="12" y1="17" x2="12.01" y2="17"></line>
                  </svg>
                  <span>{{ result.question }}</span>
                </div>
                <div class="result-answer" v-html="renderMarkdown(result.answer)"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { chatWithReport, getReport, getAgentLog } from '../api/report'
import { interviewAgents, getSimulationProfilesRealtime, getEnvStatus } from '../api/simulation'

const { t } = useI18n()

const props = defineProps({
  reportId: String,
  simulationId: String
})

const emit = defineEmits(['add-log', 'update-status'])

// State
const activeTab = ref('chat')
const chatTarget = ref('report_agent')
const showAgentDropdown = ref(false)
const selectedAgent = ref(null)
const selectedAgentIndex = ref(null)
const showFullProfile = ref(true)
const showToolsDetail = ref(true)

// Chat State
const chatInput = ref('')
const chatHistory = ref([])
const chatHistoryCache = ref({}) // 缓存所有对话记录: { 'report_agent': [], 'agent_0': [], 'agent_1': [], ... }
const isSending = ref(false)
const chatMessages = ref(null)
const chatInputRef = ref(null)

// Survey State
const selectedAgents = ref(new Set())
const surveyQuestion = ref('')
const surveyResults = ref([])
const isSurveying = ref(false)

// Report Data
const reportOutline = ref(null)
const generatedSections = ref({})
const collapsedSections = ref(new Set())
const currentSectionIndex = ref(null)
const profiles = ref([])

// Helper Methods
const isSectionCompleted = (sectionIndex) => {
  return !!generatedSections.value[sectionIndex]
}

// Refs
const leftPanel = ref(null)
const rightPanel = ref(null)

// Methods
const addLog = (msg) => {
  emit('add-log', msg)
}

const toggleSectionCollapse = (idx) => {
  if (!generatedSections.value[idx + 1]) return
  const newSet = new Set(collapsedSections.value)
  if (newSet.has(idx)) {
    newSet.delete(idx)
  } else {
    newSet.add(idx)
  }
  collapsedSections.value = newSet
}

const selectChatTarget = (target) => {
  chatTarget.value = target
  if (target === 'report_agent') {
    showAgentDropdown.value = false
  }
}

// 保存当前对话记录到缓存
const saveChatHistory = () => {
  if (chatHistory.value.length === 0) return
  
  if (chatTarget.value === 'report_agent') {
    chatHistoryCache.value['report_agent'] = [...chatHistory.value]
  } else if (selectedAgentIndex.value !== null) {
    chatHistoryCache.value[`agent_${selectedAgentIndex.value}`] = [...chatHistory.value]
  }
}

const selectReportAgentChat = () => {
  // 保存当前对话记录
  saveChatHistory()
  
  activeTab.value = 'chat'
  chatTarget.value = 'report_agent'
  selectedAgent.value = null
  selectedAgentIndex.value = null
  showAgentDropdown.value = false
  
  // 恢复 Report Agent 的对话记录
  chatHistory.value = chatHistoryCache.value['report_agent'] || []
}

const selectSurveyTab = () => {
  activeTab.value = 'survey'
  selectedAgent.value = null
  selectedAgentIndex.value = null
  showAgentDropdown.value = false
}

const toggleAgentDropdown = () => {
  showAgentDropdown.value = !showAgentDropdown.value
  if (showAgentDropdown.value) {
    activeTab.value = 'chat'
    chatTarget.value = 'agent'
  }
}

const selectAgent = (agent, idx) => {
  // 保存当前对话记录
  saveChatHistory()
  
  selectedAgent.value = agent
  selectedAgentIndex.value = idx
  chatTarget.value = 'agent'
  showAgentDropdown.value = false
  
  // 恢复该 Agent 的对话记录
  chatHistory.value = chatHistoryCache.value[`agent_${idx}`] || []
  addLog(t('log.selectChatTarget', { name: agent.username }))
}

const formatTime = (timestamp) => {
  if (!timestamp) return ''
  try {
    return new Date(timestamp).toLocaleTimeString('en-US', { 
      hour12: false, 
      hour: '2-digit', 
      minute: '2-digit'
    })
  } catch {
    return ''
  }
}

const renderMarkdown = (content) => {
  if (!content) return ''
  
  let processedContent = content.replace(/^##\s+.+\n+/, '')
  let html = processedContent.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="code-block"><code>$2</code></pre>')
  html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')
  html = html.replace(/^#### (.+)$/gm, '<h5 class="md-h5">$1</h5>')
  html = html.replace(/^### (.+)$/gm, '<h4 class="md-h4">$1</h4>')
  html = html.replace(/^## (.+)$/gm, '<h3 class="md-h3">$1</h3>')
  html = html.replace(/^# (.+)$/gm, '<h2 class="md-h2">$1</h2>')
  html = html.replace(/^> (.+)$/gm, '<blockquote class="md-quote">$1</blockquote>')
  
  // 处理列表 - 支持子列表
  html = html.replace(/^(\s*)- (.+)$/gm, (match, indent, text) => {
    const level = Math.floor(indent.length / 2)
    return `<li class="md-li" data-level="${level}">${text}</li>`
  })
  html = html.replace(/^(\s*)(\d+)\. (.+)$/gm, (match, indent, num, text) => {
    const level = Math.floor(indent.length / 2)
    return `<li class="md-oli" data-level="${level}">${text}</li>`
  })
  
  // 包装无序列表
  html = html.replace(/(<li class="md-li"[^>]*>.*?<\/li>\s*)+/g, '<ul class="md-ul">$&</ul>')
  // 包装有序列表
  html = html.replace(/(<li class="md-oli"[^>]*>.*?<\/li>\s*)+/g, '<ol class="md-ol">$&</ol>')
  
  // 清理列表项之间的所有空白
  html = html.replace(/<\/li>\s+<li/g, '</li><li')
  // 清理列表开始标签后的空白
  html = html.replace(/<ul class="md-ul">\s+/g, '<ul class="md-ul">')
  html = html.replace(/<ol class="md-ol">\s+/g, '<ol class="md-ol">')
  // 清理列表结束标签前的空白
  html = html.replace(/\s+<\/ul>/g, '</ul>')
  html = html.replace(/\s+<\/ol>/g, '</ol>')
  
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')
  html = html.replace(/_(.+?)_/g, '<em>$1</em>')
  html = html.replace(/^---$/gm, '<hr class="md-hr">')
  html = html.replace(/\n\n/g, '</p><p class="md-p">')
  html = html.replace(/\n/g, '<br>')
  html = '<p class="md-p">' + html + '</p>'
  html = html.replace(/<p class="md-p"><\/p>/g, '')
  html = html.replace(/<p class="md-p">(<h[2-5])/g, '$1')
  html = html.replace(/(<\/h[2-5]>)<\/p>/g, '$1')
  html = html.replace(/<p class="md-p">(<ul|<ol|<blockquote|<pre|<hr)/g, '$1')
  html = html.replace(/(<\/ul>|<\/ol>|<\/blockquote>|<\/pre>)<\/p>/g, '$1')
  // 清理块级元素前后的 <br> 标签
  html = html.replace(/<br>\s*(<ul|<ol|<blockquote)/g, '$1')
  html = html.replace(/(<\/ul>|<\/ol>|<\/blockquote>)\s*<br>/g, '$1')
  // 清理 <p><br> 紧跟块级元素的情况（多余空行导致）
  html = html.replace(/<p class="md-p">(<br>\s*)+(<ul|<ol|<blockquote|<pre|<hr)/g, '$2')
  // 清理连续的 <br> 标签
  html = html.replace(/(<br>\s*){2,}/g, '<br>')
  // 清理块级元素后紧跟的段落开始标签前的 <br>
  html = html.replace(/(<\/ol>|<\/ul>|<\/blockquote>)<br>(<p|<div)/g, '$1$2')

  // 修复非连续有序列表的编号：当单项 <ol> 被段落内容隔开时，保持编号递增
  const tokens = html.split(/(<ol class="md-ol">(?:<li class="md-oli"[^>]*>[\s\S]*?<\/li>)+<\/ol>)/g)
  let olCounter = 0
  let inSequence = false
  for (let i = 0; i < tokens.length; i++) {
    if (tokens[i].startsWith('<ol class="md-ol">')) {
      const liCount = (tokens[i].match(/<li class="md-oli"/g) || []).length
      if (liCount === 1) {
        olCounter++
        if (olCounter > 1) {
          tokens[i] = tokens[i].replace('<ol class="md-ol">', `<ol class="md-ol" start="${olCounter}">`)
        }
        inSequence = true
      } else {
        olCounter = 0
        inSequence = false
      }
    } else if (inSequence) {
      if (/<h[2-5]/.test(tokens[i])) {
        olCounter = 0
        inSequence = false
      }
    }
  }
  html = tokens.join('')

  return html
}

// Chat Methods
const sendMessage = async () => {
  if (!chatInput.value.trim() || isSending.value) return
  
  const message = chatInput.value.trim()
  chatInput.value = ''
  
  // Add user message
  chatHistory.value.push({
    role: 'user',
    content: message,
    timestamp: new Date().toISOString()
  })
  
  scrollToBottom()
  isSending.value = true
  
  try {
    if (chatTarget.value === 'report_agent') {
      await sendToReportAgent(message)
    } else {
      await sendToAgent(message)
    }
  } catch (err) {
    addLog(t('log.sendFailed', { error: err.message }))
    chatHistory.value.push({
      role: 'assistant',
      content: t('step5.errorOccurred', { error: err.message }),
      timestamp: new Date().toISOString()
    })
  } finally {
    isSending.value = false
    scrollToBottom()
    // 自动保存对话记录到缓存
    saveChatHistory()
  }
}

const sendToReportAgent = async (message) => {
  addLog(t('log.sendToReportAgent', { message: message.substring(0, 50) }))
  
  // Build chat history for API
  const historyForApi = chatHistory.value
    .slice(0, -1)
    .slice(-10) // Keep last 10 messages
    .map(msg => ({
      role: msg.role,
      content: msg.content
    }))
  
  const res = await chatWithReport({
    simulation_id: props.simulationId,
    message: message,
    chat_history: historyForApi
  })
  
  if (res.success && res.data) {
    chatHistory.value.push({
      role: 'assistant',
      content: res.data.response || res.data.answer || t('step5.noResponse'),
      timestamp: new Date().toISOString()
    })
    addLog(t('log.reportAgentReplied'))
  } else {
    throw new Error(res.error || t('step5.requestFailed'))
  }
}

const sendToAgent = async (message) => {
  if (!selectedAgent.value || selectedAgentIndex.value === null) {
    throw new Error(t('step5.selectAgentFirst'))
  }
  
  addLog(t('log.sendToAgent', { name: selectedAgent.value.username, message: message.substring(0, 50) }))
  
  // Build prompt with chat history
  let prompt = message
  if (chatHistory.value.length > 1) {
    const historyContext = chatHistory.value
      .slice(0, -1)
      .slice(-6)
      .map(msg => `${msg.role === 'user' ? t('step5.historyAsker') : t('step5.historyYou')}: ${msg.content}`)
      .join('\n')
    prompt = t('step5.historyPrompt', { history: historyContext, message })
  }
  
  const res = await interviewAgents({
    simulation_id: props.simulationId,
    interviews: [{
      agent_id: selectedAgentIndex.value,
      prompt: prompt
    }]
  })
  
  if (res.success && res.data) {
    // 正确的数据路径: res.data.result.results 是一个对象字典
    // 格式: {"twitter_0": {...}, "reddit_0": {...}} 或单平台 {"reddit_0": {...}}
    const resultData = res.data.result || res.data
    const resultsDict = resultData.results || resultData
    
    // 将对象字典转换为数组，优先获取 reddit 平台的回复
    let responseContent = null
    const agentId = selectedAgentIndex.value
    
    if (typeof resultsDict === 'object' && !Array.isArray(resultsDict)) {
      // 优先使用 reddit 平台回复，其次 twitter
      const redditKey = `reddit_${agentId}`
      const twitterKey = `twitter_${agentId}`
      const agentResult = resultsDict[redditKey] || resultsDict[twitterKey] || Object.values(resultsDict)[0]
      if (agentResult) {
        responseContent = agentResult.response || agentResult.answer
      }
    } else if (Array.isArray(resultsDict) && resultsDict.length > 0) {
      // 兼容数组格式
      responseContent = resultsDict[0].response || resultsDict[0].answer
    }
    
    if (responseContent) {
      chatHistory.value.push({
        role: 'assistant',
        content: responseContent,
        timestamp: new Date().toISOString()
      })
      addLog(t('log.agentReplied', { name: selectedAgent.value.username }))
    } else {
      throw new Error(t('step5.noResponse'))
    }
  } else {
    throw new Error(res.error || t('step5.requestFailed'))
  }
}

const scrollToBottom = () => {
  nextTick(() => {
    if (chatMessages.value) {
      chatMessages.value.scrollTop = chatMessages.value.scrollHeight
    }
  })
}

// Survey Methods
const toggleAgentSelection = (idx) => {
  const newSet = new Set(selectedAgents.value)
  if (newSet.has(idx)) {
    newSet.delete(idx)
  } else {
    newSet.add(idx)
  }
  selectedAgents.value = newSet
}

const selectAllAgents = () => {
  const newSet = new Set()
  profiles.value.forEach((_, idx) => newSet.add(idx))
  selectedAgents.value = newSet
}

const clearAgentSelection = () => {
  selectedAgents.value = new Set()
}

const submitSurvey = async () => {
  if (selectedAgents.value.size === 0 || !surveyQuestion.value.trim()) return
  
  isSurveying.value = true
  addLog(t('log.sendSurvey', { count: selectedAgents.value.size }))
  
  try {
    const interviews = Array.from(selectedAgents.value).map(idx => ({
      agent_id: idx,
      prompt: surveyQuestion.value.trim()
    }))
    
    const res = await interviewAgents({
      simulation_id: props.simulationId,
      interviews: interviews
    })
    
    if (res.success && res.data) {
      // 正确的数据路径: res.data.result.results 是一个对象字典
      // 格式: {"twitter_0": {...}, "reddit_0": {...}, "twitter_1": {...}, ...}
      const resultData = res.data.result || res.data
      const resultsDict = resultData.results || resultData
      
      // 将对象字典转换为数组格式
      const surveyResultsList = []
      
      for (const interview of interviews) {
        const agentIdx = interview.agent_id
        const agent = profiles.value[agentIdx]
        
        // 优先使用 reddit 平台回复，其次 twitter
        let responseContent = t('step5.noResponse')

        if (typeof resultsDict === 'object' && !Array.isArray(resultsDict)) {
          const redditKey = `reddit_${agentIdx}`
          const twitterKey = `twitter_${agentIdx}`
          const agentResult = resultsDict[redditKey] || resultsDict[twitterKey]
          if (agentResult) {
            responseContent = agentResult.response || agentResult.answer || t('step5.noResponse')
          }
        } else if (Array.isArray(resultsDict)) {
          // 兼容数组格式
          const matchedResult = resultsDict.find(r => r.agent_id === agentIdx)
          if (matchedResult) {
            responseContent = matchedResult.response || matchedResult.answer || t('step5.noResponse')
          }
        }
        
        surveyResultsList.push({
          agent_id: agentIdx,
          agent_name: agent?.username || `Agent ${agentIdx}`,
          profession: agent?.profession,
          question: surveyQuestion.value.trim(),
          answer: responseContent
        })
      }
      
      surveyResults.value = surveyResultsList
      addLog(t('log.receivedReplies', { count: surveyResults.value.length }))
    } else {
      throw new Error(res.error || t('step5.requestFailed'))
    }
  } catch (err) {
    addLog(t('log.surveySendFailed', { error: err.message }))
  } finally {
    isSurveying.value = false
  }
}

// Load Report Data
const loadReportData = async () => {
  if (!props.reportId) return
  
  try {
    addLog(t('log.loadReportData', { id: props.reportId }))
    
    // Get report info
    const reportRes = await getReport(props.reportId)
    if (reportRes.success && reportRes.data) {
      // Load agent logs to get report outline and sections
      await loadAgentLogs()
    }
  } catch (err) {
    addLog(t('log.loadReportFailed', { error: err.message }))
  }
}

const loadAgentLogs = async () => {
  if (!props.reportId) return
  
  try {
    const res = await getAgentLog(props.reportId, 0)
    if (res.success && res.data) {
      const logs = res.data.logs || []
      
      logs.forEach(log => {
        if (log.action === 'planning_complete' && log.details?.outline) {
          reportOutline.value = log.details.outline
        }
        
        if (log.action === 'section_complete' && log.section_index < 100 && log.details?.content) {
          generatedSections.value[log.section_index] = log.details.content
        }
      })
      
      addLog(t('log.reportDataLoaded'))
    }
  } catch (err) {
    addLog(t('log.loadReportLogFailed', { error: err.message }))
  }
}

// Simulated people can only be interviewed while their run's environment is still up
// (kept alive for a while after the last round). Earlier runs: say so up front.
const envAlive = ref(null)
const agentsOffline = computed(() => envAlive.value === false)
const checkEnv = async () => {
  if (!props.simulationId) return
  try {
    const res = await getEnvStatus({ simulation_id: props.simulationId })
    envAlive.value = !!res.data?.env_alive
  } catch {
    envAlive.value = null
  }
}

const loadProfiles = async () => {
  if (!props.simulationId) return
  
  try {
    const res = await getSimulationProfilesRealtime(props.simulationId)
    if (res.success && res.data) {
      profiles.value = res.data.profiles || []
      addLog(t('log.loadedProfiles', { count: profiles.value.length }))
    }
  } catch (err) {
    addLog(t('log.loadProfilesFailed', { error: err.message }))
  }
}

// Click outside to close dropdown
const handleClickOutside = (e) => {
  const dropdown = document.querySelector('.agent-dropdown')
  if (dropdown && !dropdown.contains(e.target)) {
    showAgentDropdown.value = false
  }
}

// Lifecycle
onMounted(() => {
  addLog(t('log.step5Init'))
  loadReportData()
  loadProfiles()
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})

watch(() => props.reportId, (newId) => {
  if (newId) {
    loadReportData()
  }
}, { immediate: true })

watch(() => props.simulationId, (newId) => {
  if (newId) {
    loadProfiles()
    checkEnv()
  }
}, { immediate: true })
</script>

<style scoped>
.offline-note {
  margin: var(--hm-space-3, 12px) 0;
  padding: var(--hm-space-3, 12px) var(--hm-space-4, 16px);
  background: var(--hm-surface-2);
  border: 1px solid var(--hm-line);
  border-left: 3px solid var(--hm-signal);
  border-radius: var(--hm-radius-md, 8px);
  font-size: 13px;
  line-height: 1.5;
  color: var(--hm-ink-2);
}

.interaction-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--hm-paper);
  font-family: var(--hm-font-sans);
  overflow: hidden;
}

.mono {
  font-family: var(--hm-font-mono);
}

.main-split-layout {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* ===================== Left: the report (same reading surface as Step 4) */
.left-panel.report-style {
  width: 45%;
  min-width: 450px;
  background: var(--hm-paper);
  border-right: 1px solid var(--hm-line);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  padding: var(--hm-space-10) var(--hm-space-12) var(--hm-space-16);
}

.left-panel::-webkit-scrollbar {
  width: 10px;
}

.left-panel::-webkit-scrollbar-thumb {
  background: transparent;
  border: 3px solid transparent;
  border-radius: var(--hm-radius-pill);
  background-clip: padding-box;
}

.left-panel:hover::-webkit-scrollbar-thumb {
  background-color: var(--hm-line-strong);
}

.report-content-wrapper {
  max-width: 720px;
  margin: 0 auto;
  width: 100%;
}

.report-header-block {
  margin-bottom: var(--hm-space-10);
}

.report-meta {
  display: flex;
  align-items: center;
  gap: var(--hm-space-3);
  margin-bottom: var(--hm-space-5);
}

.report-tag {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 var(--hm-space-2);
  background: var(--hm-ink);
  color: var(--hm-surface);
  border-radius: var(--hm-radius-xs);
  font-size: var(--hm-text-2xs);
  font-weight: 500;
  font-family: var(--hm-font-mono);
  letter-spacing: var(--hm-tracking-label);
  text-transform: uppercase;
}

.report-id {
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-2xs);
  color: var(--hm-ink-4);
}

/* Scoped under the header block so global .main-title rules elsewhere cannot override it */
.report-header-block .main-title {
  font-family: var(--hm-font-display);
  font-size: 30px;
  font-weight: 500;
  color: var(--hm-ink);
  line-height: 1.12;
  letter-spacing: var(--hm-tracking-display);
  margin: 0 0 var(--hm-space-4) 0;
  text-wrap: balance;
}

.sub-title {
  font-family: var(--hm-font-sans);
  font-size: var(--hm-text-md);
  font-style: normal;
  font-weight: 400;
  line-height: var(--hm-leading-relaxed);
  color: var(--hm-ink-3);
  margin: 0 0 var(--hm-space-8) 0;
}

.header-divider {
  height: 1px;
  background: var(--hm-line);
  width: 100%;
}

.sections-list {
  display: flex;
  flex-direction: column;
  gap: var(--hm-space-10);
}

.report-section-item {
  display: flex;
  flex-direction: column;
  gap: var(--hm-space-4);
}

.section-header-row {
  display: flex;
  align-items: baseline;
  gap: var(--hm-space-3);
  padding: var(--hm-space-2) var(--hm-space-3);
  margin: calc(-1 * var(--hm-space-2)) calc(-1 * var(--hm-space-3));
  border-radius: var(--hm-radius-md);
  transition: background-color var(--hm-duration-fast) var(--hm-ease);
}

.section-header-row.clickable {
  cursor: pointer;
}

.section-header-row.clickable:hover {
  background-color: var(--hm-surface-2);
}

.collapse-icon {
  margin-left: auto;
  color: var(--hm-ink-4);
  transition: transform var(--hm-duration) var(--hm-ease);
  flex-shrink: 0;
  align-self: center;
}

.collapse-icon.is-collapsed {
  transform: rotate(-90deg);
}

.section-number {
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-sm);
  font-weight: 500;
  color: var(--hm-ink-4);
  min-width: 20px;
}

.section-title {
  font-family: var(--hm-font-display);
  font-size: 20px;
  font-weight: 500;
  line-height: var(--hm-leading-snug);
  letter-spacing: -0.015em;
  color: var(--hm-ink);
  margin: 0;
  transition: color var(--hm-duration) var(--hm-ease);
}

.report-section-item.is-pending .section-number,
.report-section-item.is-pending .section-title {
  color: var(--hm-ink-5);
}

.report-section-item.is-completed .section-title {
  color: var(--hm-ink);
}

.section-body {
  padding-left: 32px;
  overflow: hidden;
}

.generated-content {
  font-family: var(--hm-font-sans);
  font-size: 15px;
  line-height: 1.75;
  color: var(--hm-ink-2);
}

.generated-content :deep(p) {
  margin-bottom: 1em;
}

.generated-content :deep(.md-h2),
.generated-content :deep(.md-h3),
.generated-content :deep(.md-h4) {
  font-family: var(--hm-font-display);
  color: var(--hm-ink);
  line-height: var(--hm-leading-snug);
  letter-spacing: -0.01em;
  margin-top: 1.6em;
  margin-bottom: 0.6em;
  font-weight: 500;
}

.generated-content :deep(.md-h2) { font-size: 17px; margin-top: 0; }
.generated-content :deep(.md-h3) { font-size: 16px; }
.generated-content :deep(.md-h4) { font-size: 15px; }

.generated-content :deep(.md-ul),
.generated-content :deep(.md-ol) {
  padding-left: var(--hm-space-6);
  margin: var(--hm-space-3) 0;
}

.generated-content :deep(.md-li),
.generated-content :deep(.md-oli) {
  margin: 6px 0;
}

.generated-content :deep(.md-quote) {
  border-left: 3px solid var(--hm-signal);
  padding: 2px 0 2px var(--hm-space-4);
  margin: 1.5em 0;
  color: var(--hm-ink-2);
  font-family: var(--hm-font-sans);
  font-style: normal;
}

.generated-content :deep(.code-block) {
  background: var(--hm-surface-2);
  padding: var(--hm-space-3);
  border-radius: var(--hm-radius-md);
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-xs);
  overflow-x: auto;
  margin: 1em 0;
  border: 1px solid var(--hm-line);
}

.generated-content :deep(strong) {
  font-weight: 600;
  color: var(--hm-ink);
}

.loading-state {
  display: flex;
  align-items: center;
  gap: var(--hm-space-3);
  padding: var(--hm-space-3) var(--hm-space-4);
  background: var(--hm-signal-soft);
  border-radius: var(--hm-radius-md);
  color: var(--hm-signal-ink);
  font-size: var(--hm-text-base);
}

.loading-icon {
  width: 16px;
  height: 16px;
  animation: spin 0.9s linear infinite;
  display: flex;
  align-items: center;
  justify-content: center;
}

.loading-icon svg {
  width: 16px;
  height: 16px;
}

.loading-icon circle {
  stroke: rgba(122, 77, 0, 0.18);
}

.loading-icon path {
  stroke: var(--hm-signal-ink);
}

.loading-text {
  font-size: var(--hm-text-base);
  font-weight: 500;
  color: var(--hm-signal-ink);
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.waiting-placeholder {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--hm-space-6);
  padding: var(--hm-space-10);
  color: var(--hm-ink-4);
}

.waiting-animation {
  position: relative;
  width: 40px;
  height: 40px;
}

.waiting-ring {
  position: absolute;
  inset: 0;
  border: 2px solid var(--hm-signal);
  border-radius: 50%;
  opacity: 0;
  animation: ripple 2s var(--hm-ease) infinite;
}

.waiting-ring:nth-child(2) {
  animation-delay: 0.4s;
}

.waiting-ring:nth-child(3) {
  animation-delay: 0.8s;
}

@keyframes ripple {
  0% { transform: scale(0.4); opacity: 1; }
  100% { transform: scale(1.6); opacity: 0; }
}

.waiting-text {
  font-size: var(--hm-text-base);
  color: var(--hm-ink-3);
}

/* ===================== Right: the interaction workbench */
.right-panel {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: var(--hm-paper);
  overflow: hidden;
}

/* Action bar: title on the left, one segmented control for the three modes */
.action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--hm-space-3) var(--hm-space-4);
  padding: var(--hm-space-3) var(--hm-space-5);
  border-bottom: 1px solid var(--hm-line);
  background: var(--hm-surface);
}

.action-bar-header {
  display: flex;
  align-items: center;
  gap: var(--hm-space-3);
  min-width: 0;
}

.action-bar-icon {
  width: 20px;
  height: 20px;
  color: var(--hm-ink-3);
  flex-shrink: 0;
}

.action-bar-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.action-bar-title {
  font-size: var(--hm-text-sm);
  font-weight: 600;
  color: var(--hm-ink);
}

.action-bar-subtitle {
  font-size: var(--hm-text-2xs);
  color: var(--hm-ink-4);
}

.action-bar-subtitle.mono {
  font-family: var(--hm-font-mono);
}

.action-bar-tabs {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 3px;
  background: var(--hm-surface-3);
  border-radius: var(--hm-radius-md);
  margin-left: auto;
}

.tab-pill {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 30px;
  padding: 0 var(--hm-space-3);
  font-family: var(--hm-font-sans);
  font-size: var(--hm-text-xs);
  font-weight: 600;
  color: var(--hm-ink-3);
  background: transparent;
  border: none;
  border-radius: var(--hm-radius-sm);
  cursor: pointer;
  white-space: nowrap;
  transition: background-color var(--hm-duration-fast) var(--hm-ease), color var(--hm-duration-fast) var(--hm-ease);
}

.tab-pill:hover {
  color: var(--hm-ink);
}

.tab-pill.active {
  background: var(--hm-surface);
  color: var(--hm-ink);
  box-shadow: var(--hm-shadow-xs);
}

.tab-pill svg {
  flex-shrink: 0;
  color: var(--hm-ink-4);
}

.tab-pill.active svg {
  color: var(--hm-ink);
}

.tab-divider {
  width: 1px;
  height: 16px;
  background: var(--hm-line-strong);
  margin: 0 var(--hm-space-1);
}

.agent-pill {
  width: 180px;
  justify-content: space-between;
}

.agent-pill span {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: left;
}

/* Survey pill: same as every other mode, no special colour */
.survey-pill,
.survey-pill:hover {
  background: transparent;
}

.survey-pill.active {
  background: var(--hm-surface);
  color: var(--hm-ink);
  box-shadow: var(--hm-shadow-xs);
}

/* Chat Container */
.chat-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Report Agent card */
.report-agent-tools-card,
.agent-profile-card {
  border-bottom: 1px solid var(--hm-line);
  background: var(--hm-surface-2);
}

.tools-card-header,
.profile-card-header {
  display: flex;
  align-items: center;
  gap: var(--hm-space-3);
  padding: var(--hm-space-4) var(--hm-space-5);
}

/* The Report Agent gets an Ink tile with an On-ink initial, like the app icon */
.tools-card-avatar {
  width: 40px;
  height: 40px;
  min-width: 40px;
  background: var(--hm-ink);
  color: var(--hm-on-ink);
  border-radius: var(--hm-radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--hm-font-display);
  font-size: var(--hm-text-lg);
  font-weight: 500;
  flex-shrink: 0;
}

.profile-card-avatar {
  width: 40px;
  height: 40px;
  min-width: 40px;
  background: var(--hm-ink);
  color: var(--hm-surface);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--hm-text-md);
  font-weight: 600;
  flex-shrink: 0;
}

.tools-card-info,
.profile-card-info {
  flex: 1;
  min-width: 0;
}

.tools-card-name,
.profile-card-name {
  font-size: var(--hm-text-base);
  font-weight: 600;
  color: var(--hm-ink);
  margin-bottom: 2px;
}

.tools-card-subtitle {
  font-size: var(--hm-text-xs);
  line-height: var(--hm-leading-normal);
  color: var(--hm-ink-3);
}

.tools-card-toggle,
.profile-card-toggle {
  width: 30px;
  height: 30px;
  background: var(--hm-surface);
  border: 1px solid var(--hm-line-strong);
  border-radius: var(--hm-radius-sm);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--hm-ink-3);
  flex-shrink: 0;
  transition: background-color var(--hm-duration-fast) var(--hm-ease), border-color var(--hm-duration-fast) var(--hm-ease);
}

.tools-card-toggle:hover,
.profile-card-toggle:hover {
  background: var(--hm-surface-2);
  border-color: var(--hm-ink-5);
  color: var(--hm-ink);
}

.tools-card-toggle svg,
.profile-card-toggle svg {
  transition: transform var(--hm-duration) var(--hm-ease);
}

.tools-card-toggle svg.is-expanded,
.profile-card-toggle svg.is-expanded {
  transform: rotate(180deg);
}

.tools-card-body {
  padding: 0 var(--hm-space-5) var(--hm-space-4);
}

.tools-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--hm-space-2);
}

.tool-item {
  display: flex;
  gap: var(--hm-space-3);
  padding: var(--hm-space-3);
  background: var(--hm-surface);
  border-radius: var(--hm-radius-md);
  border: 1px solid var(--hm-line);
  transition: border-color var(--hm-duration-fast) var(--hm-ease);
}

.tool-item:hover {
  border-color: var(--hm-line-strong);
}

/* Neutral icon chips for every tool */
.tool-icon-wrapper,
.tool-purple .tool-icon-wrapper,
.tool-blue .tool-icon-wrapper,
.tool-orange .tool-icon-wrapper,
.tool-green .tool-icon-wrapper {
  width: 28px;
  height: 28px;
  min-width: 28px;
  border-radius: var(--hm-radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: var(--hm-surface-3);
  color: var(--hm-ink-2);
}

.tool-content {
  flex: 1;
  min-width: 0;
}

.tool-name {
  font-size: var(--hm-text-xs);
  font-weight: 600;
  color: var(--hm-ink);
  margin-bottom: 2px;
}

.tool-desc {
  font-size: var(--hm-text-2xs);
  color: var(--hm-ink-4);
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* Agent profile card */
.profile-card-meta {
  display: flex;
  align-items: baseline;
  gap: var(--hm-space-2);
  min-width: 0;
  font-size: var(--hm-text-xs);
  color: var(--hm-ink-3);
}

.profile-card-handle {
  flex-shrink: 0;
  white-space: nowrap;
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-2xs);
  color: var(--hm-ink-4);
}

.profile-card-profession {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--hm-text-xs);
  color: var(--hm-ink-3);
}

.profile-card-body {
  padding: 0 var(--hm-space-5) var(--hm-space-4);
  display: flex;
  flex-direction: column;
  gap: var(--hm-space-3);
}

.profile-card-label {
  font-size: var(--hm-text-2xs);
  font-weight: 500;
  font-family: var(--hm-font-mono);
  letter-spacing: var(--hm-tracking-label);
  text-transform: uppercase;
  color: var(--hm-ink-4);
  margin-bottom: 6px;
}

.profile-card-bio {
  background: var(--hm-surface);
  padding: var(--hm-space-3) var(--hm-space-4);
  border-radius: var(--hm-radius-md);
  border: 1px solid var(--hm-line);
}

.profile-card-bio p {
  margin: 0;
  font-size: var(--hm-text-sm);
  line-height: 1.6;
  color: var(--hm-ink-2);
}

/* Agent dropdown */
.agent-dropdown {
  position: relative;
}

.dropdown-arrow {
  margin-left: var(--hm-space-1);
  transition: transform var(--hm-duration) var(--hm-ease);
}

.dropdown-arrow.open {
  transform: rotate(180deg);
}

.dropdown-menu {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  width: 320px;
  max-width: calc(100vw - 32px);
  padding: var(--hm-space-1);
  background: var(--hm-surface);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-md);
  box-shadow: var(--hm-shadow-md);
  max-height: 340px;
  overflow-y: auto;
  z-index: 100;
}

.dropdown-header {
  padding: var(--hm-space-2) 10px;
  font-size: var(--hm-text-2xs);
  font-weight: 500;
  font-family: var(--hm-font-mono);
  letter-spacing: var(--hm-tracking-label);
  text-transform: uppercase;
  color: var(--hm-ink-4);
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: var(--hm-space-2) 10px;
  border-radius: var(--hm-radius-sm);
  cursor: pointer;
  transition: background-color var(--hm-duration-fast) var(--hm-ease);
}

.dropdown-item:hover {
  background: var(--hm-surface-3);
}

.agent-avatar {
  width: 28px;
  height: 28px;
  min-width: 28px;
  background: var(--hm-surface-3);
  color: var(--hm-ink-2);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--hm-text-2xs);
  font-weight: 600;
  flex-shrink: 0;
}

.dropdown-item:hover .agent-avatar {
  background: var(--hm-ink);
  color: var(--hm-surface);
}

.agent-info {
  display: flex;
  flex-direction: column;
  gap: 1px;
  flex: 1;
  min-width: 0;
}

.agent-name {
  font-size: var(--hm-text-sm);
  font-weight: 600;
  color: var(--hm-ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.agent-role {
  font-size: var(--hm-text-2xs);
  color: var(--hm-ink-4);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Chat messages */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--hm-space-6) var(--hm-space-5);
  display: flex;
  flex-direction: column;
  gap: var(--hm-space-5);
}

.chat-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--hm-space-4);
  color: var(--hm-ink-4);
}

.empty-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: var(--hm-surface-2);
  border: 1px solid var(--hm-line);
  color: var(--hm-ink-5);
}

.empty-icon svg {
  width: 28px;
  height: 28px;
}

.empty-text {
  font-size: var(--hm-text-base);
  text-align: center;
  max-width: 300px;
  line-height: 1.6;
  color: var(--hm-ink-3);
}

.chat-message {
  display: flex;
  gap: var(--hm-space-3);
}

.chat-message.user {
  flex-direction: row-reverse;
}

.message-avatar {
  width: 32px;
  height: 32px;
  min-width: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--hm-text-xs);
  font-weight: 600;
  flex-shrink: 0;
}

.chat-message.user .message-avatar {
  background: var(--hm-ink);
  color: var(--hm-surface);
}

.chat-message.assistant .message-avatar {
  background: var(--hm-surface-3);
  color: var(--hm-ink-2);
}

.message-content {
  max-width: 75%;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.chat-message.user .message-content {
  align-items: flex-end;
}

.message-header {
  display: flex;
  align-items: baseline;
  gap: var(--hm-space-2);
}

.chat-message.user .message-header {
  flex-direction: row-reverse;
}

.sender-name {
  font-size: var(--hm-text-xs);
  font-weight: 600;
  color: var(--hm-ink-2);
}

.message-time {
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-2xs);
  color: var(--hm-ink-4);
}

.message-text {
  padding: 10px 14px;
  border-radius: var(--hm-radius-lg);
  font-size: var(--hm-text-base);
  line-height: 1.6;
  counter-reset: list-counter;
}

.chat-message.user .message-text {
  background: var(--hm-ink);
  color: var(--hm-surface);
  border-top-right-radius: var(--hm-radius-xs);
}

.chat-message.assistant .message-text {
  background: var(--hm-surface-2);
  border: 1px solid var(--hm-line);
  color: var(--hm-ink-2);
  border-top-left-radius: var(--hm-radius-xs);
}

.message-text :deep(.md-p) {
  margin: 0;
}

.message-text :deep(.md-p:last-child) {
  margin-bottom: 0;
}

/* Ordered lists continue numbering across blocks */
.message-text :deep(.md-ol) {
  list-style: none;
  padding-left: 0;
  margin: var(--hm-space-2) 0;
}

.message-text :deep(.md-oli) {
  counter-increment: list-counter;
  display: flex;
  gap: var(--hm-space-2);
  margin: var(--hm-space-1) 0;
}

.message-text :deep(.md-oli)::before {
  content: counter(list-counter) ".";
  font-weight: 600;
  color: var(--hm-ink-4);
  min-width: 20px;
  flex-shrink: 0;
}

.message-text :deep(.md-ul) {
  padding-left: var(--hm-space-5);
  margin: var(--hm-space-2) 0;
}

.message-text :deep(.md-li) {
  margin: var(--hm-space-1) 0;
}

/* Typing indicator */
.typing-indicator {
  display: flex;
  align-items: center;
  gap: 4px;
  height: 40px;
  padding: 0 var(--hm-space-4);
  background: var(--hm-surface-2);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-lg);
  border-top-left-radius: var(--hm-radius-xs);
}

.typing-indicator span {
  width: 6px;
  height: 6px;
  background: var(--hm-ink-5);
  border-radius: 50%;
  animation: typing 1.2s infinite var(--hm-ease);
}

.typing-indicator span:nth-child(1) { animation-delay: 0s; }
.typing-indicator span:nth-child(2) { animation-delay: 0.15s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.3s; }

@keyframes typing {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.5; }
  30% { transform: translateY(-4px); opacity: 1; }
}

/* Chat input */
.chat-input-area {
  padding: var(--hm-space-4) var(--hm-space-5);
  border-top: 1px solid var(--hm-line);
  background: var(--hm-surface);
  display: flex;
  gap: var(--hm-space-2);
  align-items: flex-end;
}

.chat-input {
  flex: 1;
  min-height: 44px;
  padding: 11px 14px;
  font-family: var(--hm-font-sans);
  font-size: var(--hm-text-base);
  line-height: 1.5;
  color: var(--hm-ink);
  background: var(--hm-surface);
  border: 1px solid var(--hm-line-strong);
  border-radius: var(--hm-radius-md);
  resize: none;
  transition: border-color var(--hm-duration-fast) var(--hm-ease), box-shadow var(--hm-duration-fast) var(--hm-ease);
}

.chat-input:focus {
  outline: none;
  border-color: var(--hm-ink);
  box-shadow: 0 0 0 1px var(--hm-ink);
}

.chat-input:disabled {
  background: var(--hm-surface-2);
  cursor: not-allowed;
}

.send-btn {
  width: 44px;
  height: 44px;
  flex-shrink: 0;
  background: var(--hm-signal);
  color: var(--hm-ink);
  border: none;
  border-radius: var(--hm-radius-md);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color var(--hm-duration-fast) var(--hm-ease);
}

.send-btn:hover:not(:disabled) {
  background: var(--hm-signal-hover);
}

.send-btn:disabled {
  background: var(--hm-surface-3);
  color: var(--hm-ink-5);
  cursor: not-allowed;
}

/* Survey */
.survey-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.survey-setup {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: var(--hm-space-6) var(--hm-space-5);
  border-bottom: 1px solid var(--hm-line);
  overflow: hidden;
}

.setup-section {
  margin-bottom: var(--hm-space-6);
}

.setup-section:first-child {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.setup-section:last-child {
  margin-bottom: 0;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: var(--hm-space-3);
}

.setup-section .section-header .section-title {
  font-family: var(--hm-font-sans);
  font-size: var(--hm-text-sm);
  font-weight: 600;
  letter-spacing: 0;
  color: var(--hm-ink);
}

.selection-count {
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-2xs);
  color: var(--hm-ink-4);
}

.agents-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: var(--hm-space-2);
  flex: 1;
  overflow-y: auto;
  padding: 2px;
  align-content: start;
}

.agent-checkbox {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px var(--hm-space-3);
  background: var(--hm-surface);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-md);
  cursor: pointer;
  transition: border-color var(--hm-duration-fast) var(--hm-ease), box-shadow var(--hm-duration-fast) var(--hm-ease);
}

.agent-checkbox:hover {
  border-color: var(--hm-line-strong);
}

/* Selection is ink; green is reserved for success */
.agent-checkbox.checked {
  background: var(--hm-surface);
  border-color: var(--hm-ink);
}

.agent-checkbox input {
  display: none;
}

.checkbox-avatar {
  width: 28px;
  height: 28px;
  min-width: 28px;
  background: var(--hm-surface-3);
  color: var(--hm-ink-2);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--hm-text-2xs);
  font-weight: 600;
  flex-shrink: 0;
}

.agent-checkbox.checked .checkbox-avatar {
  background: var(--hm-ink);
  color: var(--hm-surface);
}

.checkbox-info {
  flex: 1;
  min-width: 0;
}

.checkbox-name {
  display: block;
  font-size: var(--hm-text-xs);
  font-weight: 600;
  color: var(--hm-ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.checkbox-role {
  display: block;
  font-size: var(--hm-text-2xs);
  color: var(--hm-ink-4);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.checkbox-indicator {
  width: 18px;
  height: 18px;
  border: 1.5px solid var(--hm-line-strong);
  border-radius: var(--hm-radius-xs);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: var(--hm-surface);
  transition: background-color var(--hm-duration-fast) var(--hm-ease), border-color var(--hm-duration-fast) var(--hm-ease);
}

.agent-checkbox.checked .checkbox-indicator {
  background: var(--hm-ink);
  border-color: var(--hm-ink);
}

.checkbox-indicator svg {
  width: 12px;
  height: 12px;
  opacity: 0;
  transform: scale(0.5);
  transition: opacity var(--hm-duration-fast) var(--hm-ease), transform var(--hm-duration-fast) var(--hm-ease);
}

.agent-checkbox.checked .checkbox-indicator svg {
  opacity: 1;
  transform: scale(1);
}

.selection-actions {
  display: flex;
  align-items: center;
  gap: var(--hm-space-2);
  margin-top: var(--hm-space-3);
}

.action-link {
  font-family: var(--hm-font-sans);
  font-size: var(--hm-text-xs);
  font-weight: 600;
  color: var(--hm-ink-3);
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
}

.action-link:hover {
  color: var(--hm-ink);
  text-decoration: underline;
  text-underline-offset: 3px;
}

.action-divider {
  color: var(--hm-line-strong);
}

.survey-input {
  width: 100%;
  padding: var(--hm-space-3) 14px;
  font-family: var(--hm-font-sans);
  font-size: var(--hm-text-base);
  line-height: 1.5;
  color: var(--hm-ink);
  background: var(--hm-surface);
  border: 1px solid var(--hm-line-strong);
  border-radius: var(--hm-radius-md);
  resize: none;
  transition: border-color var(--hm-duration-fast) var(--hm-ease), box-shadow var(--hm-duration-fast) var(--hm-ease);
}

.survey-input:focus {
  outline: none;
  border-color: var(--hm-ink);
  box-shadow: 0 0 0 1px var(--hm-ink);
}

.survey-submit-btn {
  width: 100%;
  height: 44px;
  padding: 0 var(--hm-space-6);
  font-family: var(--hm-font-sans);
  font-size: var(--hm-text-base);
  font-weight: 600;
  color: var(--hm-ink);
  background: var(--hm-signal);
  border: none;
  border-radius: var(--hm-radius-sm);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--hm-space-2);
  margin-top: var(--hm-space-5);
  transition: background-color var(--hm-duration-fast) var(--hm-ease);
}

.survey-submit-btn:hover:not(:disabled) {
  background: var(--hm-signal-hover);
}

.survey-submit-btn:disabled {
  background: var(--hm-surface-3);
  color: var(--hm-ink-5);
  cursor: not-allowed;
}

.loading-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: var(--hm-surface);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.survey-results {
  flex: 1;
  overflow-y: auto;
  padding: var(--hm-space-6) var(--hm-space-5);
  background: var(--hm-surface-2);
}

.results-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: var(--hm-space-4);
}

.results-title {
  font-size: var(--hm-text-base);
  font-weight: 600;
  color: var(--hm-ink);
}

.results-count {
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-2xs);
  color: var(--hm-ink-4);
}

.results-list {
  display: flex;
  flex-direction: column;
  gap: var(--hm-space-3);
}

.result-card {
  background: var(--hm-surface);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-lg);
  padding: var(--hm-space-5);
}

.result-header {
  display: flex;
  align-items: center;
  gap: var(--hm-space-3);
  margin-bottom: var(--hm-space-3);
}

.result-avatar {
  width: 32px;
  height: 32px;
  min-width: 32px;
  background: var(--hm-ink);
  color: var(--hm-surface);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--hm-text-xs);
  font-weight: 600;
  flex-shrink: 0;
}

.result-info {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.result-name {
  font-size: var(--hm-text-base);
  font-weight: 600;
  color: var(--hm-ink);
}

.result-role {
  font-size: var(--hm-text-xs);
  color: var(--hm-ink-4);
}

.result-question {
  display: flex;
  align-items: flex-start;
  gap: var(--hm-space-2);
  padding: 10px var(--hm-space-3);
  background: var(--hm-surface-2);
  border-radius: var(--hm-radius-md);
  margin-bottom: var(--hm-space-3);
  font-size: var(--hm-text-sm);
  color: var(--hm-ink-3);
}

.result-question svg {
  flex-shrink: 0;
  margin-top: 2px;
  color: var(--hm-ink-4);
}

.result-answer {
  font-size: var(--hm-text-base);
  line-height: 1.7;
  color: var(--hm-ink-2);
}

/* Markdown in chat and survey answers */
:deep(.md-p) {
  margin: 0 0 var(--hm-space-3) 0;
}

:deep(.md-h2) {
  font-size: var(--hm-text-lg);
  font-weight: 600;
  color: var(--hm-ink);
  margin: var(--hm-space-6) 0 var(--hm-space-3) 0;
}

:deep(.md-h3) {
  font-size: var(--hm-text-md);
  font-weight: 600;
  color: var(--hm-ink);
  margin: var(--hm-space-5) 0 10px 0;
}

:deep(.md-h4) {
  font-size: var(--hm-text-base);
  font-weight: 600;
  color: var(--hm-ink-2);
  margin: var(--hm-space-4) 0 var(--hm-space-2) 0;
}

:deep(.md-h5) {
  font-size: var(--hm-text-sm);
  font-weight: 600;
  color: var(--hm-ink-3);
  margin: var(--hm-space-3) 0 6px 0;
}

:deep(.md-ul), :deep(.md-ol) {
  margin: var(--hm-space-3) 0;
  padding-left: var(--hm-space-6);
}

:deep(.md-li), :deep(.md-oli) {
  margin: 6px 0;
}

.chat-messages :deep(.md-quote),
.result-answer :deep(.md-quote) {
  margin: var(--hm-space-3) 0;
  padding: 2px 0 2px 14px;
  background: transparent;
  border-left: 3px solid var(--hm-signal);
  color: var(--hm-ink-2);
}

:deep(.code-block) {
  margin: var(--hm-space-3) 0;
  padding: var(--hm-space-3) var(--hm-space-4);
  background: var(--hm-console-bg);
  border-radius: var(--hm-radius-md);
  overflow-x: auto;
}

:deep(.code-block code) {
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-xs);
  color: var(--hm-console-text);
}

:deep(.inline-code) {
  font-family: var(--hm-font-mono);
  font-size: 0.9em;
  background: var(--hm-surface-3);
  padding: 1px 5px;
  border-radius: var(--hm-radius-xs);
  color: var(--hm-ink);
}

:deep(.md-hr) {
  border: none;
  border-top: 1px solid var(--hm-line);
  margin: var(--hm-space-6) 0;
}
</style>

<template>
  <div class="simulation-panel">
    <!-- Top Control Bar -->
    <div class="control-bar">
      <div class="status-group">
        <!-- Twitter platform progress -->
        <div class="platform-status twitter" :class="{ active: runStatus.twitter_running, completed: runStatus.twitter_completed }">
          <div class="platform-header">
            <svg class="platform-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
            </svg>
            <span class="platform-name">Info Plaza</span>
            <span v-if="runStatus.twitter_completed" class="status-badge">
              <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="3">
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
            </span>
          </div>
          <div class="platform-stats">
            <span class="stat">
              <span class="stat-label">ROUND</span>
              <span class="stat-value mono">{{ runStatus.twitter_current_round || 0 }}<span class="stat-total">/{{ runStatus.total_rounds || maxRounds || '-' }}</span></span>
            </span>
            <span class="stat">
              <span class="stat-label">TIME</span>
              <span class="stat-value mono">{{ twitterElapsedTime }}</span>
            </span>
            <span class="stat">
              <span class="stat-label">ACTS</span>
              <span class="stat-value mono">{{ runStatus.twitter_actions_count || 0 }}</span>
            </span>
          </div>
          <!-- Available actions hint -->
          <div class="actions-tooltip">
            <div class="tooltip-title">Available Actions</div>
            <div class="tooltip-actions">
              <span class="tooltip-action">POST</span>
              <span class="tooltip-action">LIKE</span>
              <span class="tooltip-action">REPOST</span>
              <span class="tooltip-action">QUOTE</span>
              <span class="tooltip-action">FOLLOW</span>
              <span class="tooltip-action">IDLE</span>
            </div>
          </div>
        </div>
        
        <!-- Reddit platform progress -->
        <div class="platform-status reddit" :class="{ active: runStatus.reddit_running, completed: runStatus.reddit_completed }">
          <div class="platform-header">
            <svg class="platform-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path>
            </svg>
            <span class="platform-name">Topic Community</span>
            <span v-if="runStatus.reddit_completed" class="status-badge">
              <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="3">
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
            </span>
          </div>
          <div class="platform-stats">
            <span class="stat">
              <span class="stat-label">ROUND</span>
              <span class="stat-value mono">{{ runStatus.reddit_current_round || 0 }}<span class="stat-total">/{{ runStatus.total_rounds || maxRounds || '-' }}</span></span>
            </span>
            <span class="stat">
              <span class="stat-label">TIME</span>
              <span class="stat-value mono">{{ redditElapsedTime }}</span>
            </span>
            <span class="stat">
              <span class="stat-label">ACTS</span>
              <span class="stat-value mono">{{ runStatus.reddit_actions_count || 0 }}</span>
            </span>
          </div>
          <!-- Available actions hint -->
          <div class="actions-tooltip">
            <div class="tooltip-title">Available Actions</div>
            <div class="tooltip-actions">
              <span class="tooltip-action">POST</span>
              <span class="tooltip-action">COMMENT</span>
              <span class="tooltip-action">LIKE</span>
              <span class="tooltip-action">DISLIKE</span>
              <span class="tooltip-action">SEARCH</span>
              <span class="tooltip-action">TREND</span>
              <span class="tooltip-action">FOLLOW</span>
              <span class="tooltip-action">MUTE</span>
              <span class="tooltip-action">REFRESH</span>
              <span class="tooltip-action">IDLE</span>
            </div>
          </div>
        </div>
      </div>

      <div class="action-controls">
        <button
          class="action-btn secondary"
          :disabled="!simulationId"
          @click="openAnalytics"
        >
          {{ $t('analytics.open') }}
        </button>
        <button
          class="action-btn primary"
          :disabled="phase !== 2 || isGeneratingReport"
          @click="handleNextStep"
        >
          <span v-if="isGeneratingReport" class="loading-spinner-small"></span>
          {{ isGeneratingReport ? $t('step3.generatingReportBtn') : $t('step3.startGenerateReportBtn') }}
          <span v-if="!isGeneratingReport" class="arrow-icon">→</span>
        </button>
      </div>
    </div>

    <!-- Main Content: Dual Timeline -->
    <div class="main-content-area" ref="scrollContainer">
      <!-- Timeline Header -->
      <div class="timeline-header" v-if="allActions.length > 0">
        <div class="timeline-stats">
          <span class="total-count">TOTAL EVENTS: <span class="mono">{{ allActions.length }}</span></span>
          <span class="platform-breakdown">
            <span class="breakdown-item twitter">
              <svg class="mini-icon" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>
              <span class="mono">{{ twitterActionsCount }}</span>
            </span>
            <span class="breakdown-divider">/</span>
            <span class="breakdown-item reddit">
              <svg class="mini-icon" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>
              <span class="mono">{{ redditActionsCount }}</span>
            </span>
          </span>
        </div>
      </div>
      
      <!-- Timeline Feed -->
      <div class="timeline-feed">
        <div class="timeline-axis"></div>
        
        <TransitionGroup name="timeline-item">
          <div 
            v-for="action in chronologicalActions" 
            :key="action._uniqueId || action.id || `${action.timestamp}-${action.agent_id}`" 
            class="timeline-item"
            :class="action.platform"
          >
            <div class="timeline-marker">
              <div class="marker-dot"></div>
            </div>
            
            <div class="timeline-card">
              <div class="card-header">
                <div class="agent-info">
                  <div class="avatar-placeholder">{{ (action.agent_name || 'A')[0] }}</div>
                  <span class="agent-name">{{ action.agent_name }}</span>
                </div>
                
                <div class="header-meta">
                  <div class="platform-indicator">
                    <svg v-if="action.platform === 'twitter'" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>
                    <svg v-else viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>
                  </div>
                  <div class="action-badge" :class="getActionTypeClass(action.action_type)">
                    {{ getActionTypeLabel(action.action_type) }}
                  </div>
                </div>
              </div>
              
              <div class="card-body">
                <!-- CREATE_POST: publish a post -->
                <div v-if="action.action_type === 'CREATE_POST' && action.action_args?.content" class="content-text main-text">
                  {{ action.action_args.content }}
                </div>

                <!-- QUOTE_POST: quote a post -->
                <template v-if="action.action_type === 'QUOTE_POST'">
                  <div v-if="action.action_args?.quote_content" class="content-text">
                    {{ action.action_args.quote_content }}
                  </div>
                  <div v-if="action.action_args?.original_content" class="quoted-block">
                    <div class="quote-header">
                      <svg class="icon-small" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path></svg>
                      <span class="quote-label">@{{ action.action_args.original_author_name || 'User' }}</span>
                    </div>
                    <div class="quote-text">
                      {{ truncateContent(action.action_args.original_content, 150) }}
                    </div>
                  </div>
                </template>

                <!-- REPOST: repost a post -->
                <template v-if="action.action_type === 'REPOST'">
                  <div class="repost-info">
                    <svg class="icon-small" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="17 1 21 5 17 9"></polyline><path d="M3 11V9a4 4 0 0 1 4-4h14"></path><polyline points="7 23 3 19 7 15"></polyline><path d="M21 13v2a4 4 0 0 1-4 4H3"></path></svg>
                    <span class="repost-label">Reposted from @{{ action.action_args?.original_author_name || 'User' }}</span>
                  </div>
                  <div v-if="action.action_args?.original_content" class="repost-content">
                    {{ truncateContent(action.action_args.original_content, 200) }}
                  </div>
                </template>

                <!-- LIKE_POST: like a post -->
                <template v-if="action.action_type === 'LIKE_POST'">
                  <div class="like-info">
                    <svg class="icon-small filled" viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>
                    <span class="like-label">Liked @{{ action.action_args?.post_author_name || 'User' }}'s post</span>
                  </div>
                  <div v-if="action.action_args?.post_content" class="liked-content">
                    "{{ truncateContent(action.action_args.post_content, 120) }}"
                  </div>
                </template>

                <!-- CREATE_COMMENT: post a comment -->
                <template v-if="action.action_type === 'CREATE_COMMENT'">
                  <div v-if="action.action_args?.content" class="content-text">
                    {{ action.action_args.content }}
                  </div>
                  <div v-if="action.action_args?.post_id" class="comment-context">
                    <svg class="icon-small" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>
                    <span>Reply to post #{{ action.action_args.post_id }}</span>
                  </div>
                </template>

                <!-- SEARCH_POSTS: search posts -->
                <template v-if="action.action_type === 'SEARCH_POSTS'">
                  <div class="search-info">
                    <svg class="icon-small" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                    <span class="search-label">Search Query:</span>
                    <span class="search-query">"{{ action.action_args?.query || '' }}"</span>
                  </div>
                </template>

                <!-- FOLLOW: follow a user -->
                <template v-if="action.action_type === 'FOLLOW'">
                  <div class="follow-info">
                    <svg class="icon-small" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="8.5" cy="7" r="4"></circle><line x1="20" y1="8" x2="20" y2="14"></line><line x1="23" y1="11" x2="17" y2="11"></line></svg>
                    <span class="follow-label">Followed @{{ action.action_args?.target_user || action.action_args?.user_id || 'User' }}</span>
                  </div>
                </template>

                <!-- UPVOTE / DOWNVOTE -->
                <template v-if="action.action_type === 'UPVOTE_POST' || action.action_type === 'DOWNVOTE_POST'">
                  <div class="vote-info">
                    <svg v-if="action.action_type === 'UPVOTE_POST'" class="icon-small" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="18 15 12 9 6 15"></polyline></svg>
                    <svg v-else class="icon-small" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"></polyline></svg>
                    <span class="vote-label">{{ action.action_type === 'UPVOTE_POST' ? 'Upvoted' : 'Downvoted' }} Post</span>
                  </div>
                  <div v-if="action.action_args?.post_content" class="voted-content">
                    "{{ truncateContent(action.action_args.post_content, 120) }}"
                  </div>
                </template>

                <!-- DO_NOTHING: no action (silent) -->
                <template v-if="action.action_type === 'DO_NOTHING'">
                  <div class="idle-info">
                    <svg class="icon-small" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
                    <span class="idle-label">Action Skipped</span>
                  </div>
                </template>

                <!-- Generic fallback: unknown types, or anything with content not handled above -->
                <div v-if="!['CREATE_POST', 'QUOTE_POST', 'REPOST', 'LIKE_POST', 'CREATE_COMMENT', 'SEARCH_POSTS', 'FOLLOW', 'UPVOTE_POST', 'DOWNVOTE_POST', 'DO_NOTHING'].includes(action.action_type) && action.action_args?.content" class="content-text">
                  {{ action.action_args.content }}
                </div>
              </div>

              <div class="card-footer">
                <span class="time-tag">R{{ action.round_num }} • {{ formatActionTime(action.timestamp) }}</span>
                <!-- Platform tag removed as it is in header now -->
              </div>
            </div>
          </div>
        </TransitionGroup>

        <div v-if="allActions.length === 0 && startError" class="waiting-state start-error" role="alert">
          <span>{{ startError }}</span>
          <button class="action-btn secondary" :disabled="isStarting" @click="doStartSimulation">{{ $t('step3.tryAgain') }}</button>
        </div>
        <div v-else-if="allActions.length === 0" class="waiting-state">
          <div class="pulse-ring"></div>
          <span>{{ $t('step3.waitingForActions') }}</span>
        </div>
      </div>
    </div>

    <!-- Bottom Info / Logs -->
    <div class="system-logs">
      <div class="log-header">
        <span class="log-title">SIMULATION MONITOR</span>
        <span class="log-id">{{ simulationId || 'NO_SIMULATION' }}</span>
      </div>
      <div class="log-content" ref="logContent">
        <div class="log-line" v-for="(log, idx) in systemLogs" :key="idx">
          <span class="log-time">{{ log.time }}</span>
          <span class="log-msg">{{ log.msg }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  startSimulation,
  stopSimulation,
  getRunStatus,
  getRunStatusDetail
} from '../api/simulation'
import { generateReport } from '../api/report'

const { t } = useI18n()

const props = defineProps({
  simulationId: String,
  maxRounds: Number, // maximum rounds, passed in from Step 2
  minutesPerRound: {
    type: Number,
    default: 30 // 30 minutes per round by default
  },
  projectData: Object,
  graphData: Object,
  systemLogs: Array
})

const emit = defineEmits(['go-back', 'next-step', 'add-log', 'update-status'])

const router = useRouter()
const route = useRoute()

// Hivemind: open the analytics view in a new tab so the running simulation view keeps polling
const openAnalytics = () => {
  if (!props.simulationId) return
  const { href } = router.resolve({ name: 'Analytics', params: { simulationId: props.simulationId } })
  window.open(href, '_blank')
}

// State
const isGeneratingReport = ref(false)
const phase = ref(0) // 0: not started, 1: running, 2: finished
const isStarting = ref(false)
const isStopping = ref(false)
const startError = ref(null)
const runStatus = ref({})
const allActions = ref([]) // all actions (accumulated incrementally)
const actionIds = ref(new Set()) // set of action IDs used for de-duplication
const scrollContainer = ref(null)

// Computed
// Show actions in chronological order (newest last, i.e. at the bottom)
const chronologicalActions = computed(() => {
  return allActions.value
})

// Action counts per platform
const twitterActionsCount = computed(() => {
  return allActions.value.filter(a => a.platform === 'twitter').length
})

const redditActionsCount = computed(() => {
  return allActions.value.filter(a => a.platform === 'reddit').length
})

// Format the simulated elapsed time (from the round number and minutes per round)
const formatElapsedTime = (currentRound) => {
  if (!currentRound || currentRound <= 0) return '0h 0m'
  const totalMinutes = currentRound * props.minutesPerRound
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  return `${hours}h ${minutes}m`
}

// Simulated elapsed time on Twitter
const twitterElapsedTime = computed(() => {
  return formatElapsedTime(runStatus.value.twitter_current_round || 0)
})

// Simulated elapsed time on Reddit
const redditElapsedTime = computed(() => {
  return formatElapsedTime(runStatus.value.reddit_current_round || 0)
})

// Methods
const addLog = (msg) => {
  emit('add-log', msg)
}

// Reset all state (used when restarting the simulation)
const resetAllState = () => {
  phase.value = 0
  runStatus.value = {}
  allActions.value = []
  actionIds.value = new Set()
  prevTwitterRound.value = 0
  prevRedditRound.value = 0
  startError.value = null
  isStarting.value = false
  isStopping.value = false
  stopPolling()  // stop any polling left over from before
}

// Start the simulation
const doStartSimulation = async () => {
  if (!props.simulationId) {
    addLog(t('log.errorMissingSimId'))
    return
  }

  // Reset all state first so the previous simulation cannot affect this one
  resetAllState()
  
  isStarting.value = true
  startError.value = null
  addLog(t('log.startingDualSim'))
  emit('update-status', 'processing')
  
  try {
    const params = {
      simulation_id: props.simulationId,
      platform: 'parallel',
      force: true,  // force a fresh start
      enable_graph_memory_update: true  // turn on live graph updates
    }
    
    if (props.maxRounds) {
      params.max_rounds = props.maxRounds
      addLog(t('log.setMaxRounds', { rounds: props.maxRounds }))
    }
    
    addLog(t('log.graphMemoryUpdateEnabled'))
    
    const res = await startSimulation(params)
    
    if (res.success && res.data) {
      if (res.data.force_restarted) {
        addLog(t('log.oldSimCleared'))
      }
      addLog(t('log.engineStarted'))
      addLog(`  ├─ PID: ${res.data.process_pid || '-'}`)
      
      phase.value = 1
      runStatus.value = res.data
      
      startStatusPolling()
      startDetailPolling()
    } else {
      startError.value = res.error || t('common.unknownError')
      addLog(t('log.startFailed', { error: res.error || t('common.unknownError') }))
      emit('update-status', 'error')
    }
  } catch (err) {
    startError.value = err.message
    addLog(t('log.startException', { error: err.message }))
    emit('update-status', 'error')
  } finally {
    isStarting.value = false
  }
}

// Stop the simulation
const handleStopSimulation = async () => {
  if (!props.simulationId) return
  
  isStopping.value = true
  addLog(t('log.stoppingSim'))
  
  try {
    const res = await stopSimulation({ simulation_id: props.simulationId })
    
    if (res.success) {
      addLog(t('log.simStoppedSuccess'))
      phase.value = 2
      stopPolling()
      emit('update-status', 'completed')
    } else {
      addLog(t('log.stopFailed', { error: res.error || t('common.unknownError') }))
    }
  } catch (err) {
    addLog(t('log.stopException', { error: err.message }))
  } finally {
    isStopping.value = false
  }
}

// Poll the status
let statusTimer = null
let detailTimer = null

const startStatusPolling = () => {
  statusTimer = setInterval(fetchRunStatus, 2000)
}

const startDetailPolling = () => {
  fetchRunStatusDetail()  // load the feed now, not 3 s later (a finished run stops polling first)
  detailTimer = setInterval(fetchRunStatusDetail, 3000)
}

const stopPolling = () => {
  if (statusTimer) {
    clearInterval(statusTimer)
    statusTimer = null
  }
  if (detailTimer) {
    clearInterval(detailTimer)
    detailTimer = null
  }
}

// Track each platform's previous round, to detect changes and log them
const prevTwitterRound = ref(0)
const prevRedditRound = ref(0)

const fetchRunStatus = async () => {
  if (!props.simulationId) return
  
  try {
    const res = await getRunStatus(props.simulationId)
    
    if (res.success && res.data) {
      const data = res.data
      
      runStatus.value = data
      
      // Detect round changes on each platform and log them
      if (data.twitter_current_round > prevTwitterRound.value) {
        addLog(`[Plaza] R${data.twitter_current_round}/${data.total_rounds} | T:${data.twitter_simulated_hours || 0}h | A:${data.twitter_actions_count}`)
        prevTwitterRound.value = data.twitter_current_round
      }
      
      if (data.reddit_current_round > prevRedditRound.value) {
        addLog(`[Community] R${data.reddit_current_round}/${data.total_rounds} | T:${data.reddit_simulated_hours || 0}h | A:${data.reddit_actions_count}`)
        prevRedditRound.value = data.reddit_current_round
      }
      
      // Detect whether the simulation has finished (from runner_status or the platforms' completion state)
      const isCompleted = data.runner_status === 'completed' || data.runner_status === 'stopped'
      const isFailed = data.runner_status === 'failed'
      // Hivemind: all rounds done and memory written; agents stay up for interviews
      const readyEnvAlive = data.runner_status === 'running' && data.ready_for_report
      
      // runner_status is authoritative because the backend only publishes a
      // terminal state after the Zep ingestion barrier has completed.
      if (isFailed) {
        addLog(t('log.simFailed') + (data.error ? `: ${data.error}` : ''))
        phase.value = 2
        stopPolling()
        emit('update-status', 'error')
      } else if (isCompleted || readyEnvAlive) {
        addLog(readyEnvAlive ? t('log.roundsDoneEnvAlive') : t('log.simCompleted'))
        phase.value = 2
        stopPolling()
        fetchRunStatusDetail()  // pick up the actions logged since the last poll
        emit('update-status', 'completed')
      }
    }
  } catch (err) {
    console.warn('Failed to fetch run status:', err)
  }
}

// Check whether every enabled platform has finished
const checkPlatformsCompleted = (data) => {
  // No platform data at all: return false
  if (!data) return false
  
  // Check each platform's completion state
  const twitterCompleted = data.twitter_completed === true
  const redditCompleted = data.reddit_completed === true
  
  // If at least one platform has finished, check whether every enabled platform has
  // A platform counts as enabled if actions_count > 0 or it has ever been running
  const twitterEnabled = (data.twitter_actions_count > 0) || data.twitter_running || twitterCompleted
  const redditEnabled = (data.reddit_actions_count > 0) || data.reddit_running || redditCompleted
  
  // No platform enabled: return false
  if (!twitterEnabled && !redditEnabled) return false
  
  // Check whether every enabled platform has finished
  if (twitterEnabled && !twitterCompleted) return false
  if (redditEnabled && !redditCompleted) return false
  
  return true
}

const fetchRunStatusDetail = async () => {
  if (!props.simulationId) return
  
  try {
    const res = await getRunStatusDetail(props.simulationId)
    
    if (res.success && res.data) {
      // Use all_actions to get the complete action list
      const serverActions = res.data.all_actions || []
      
      // Add new actions incrementally (de-duplicated)
      let newActionsAdded = 0
      serverActions.forEach(action => {
        // Build a unique ID
        const actionId = action.id || `${action.timestamp}-${action.platform}-${action.agent_id}-${action.action_type}`
        
        if (!actionIds.value.has(actionId)) {
          actionIds.value.add(actionId)
          allActions.value.push({
            ...action,
            _uniqueId: actionId
          })
          newActionsAdded++
        }
      })
      
      // No auto-scroll, so the user can browse the timeline freely
      // New actions are appended at the bottom
    }
  } catch (err) {
    console.warn('Failed to fetch detailed status:', err)
  }
}

// Helpers
const getActionTypeLabel = (type) => {
  const labels = {
    'CREATE_POST': 'POST',
    'REPOST': 'REPOST',
    'LIKE_POST': 'LIKE',
    'CREATE_COMMENT': 'COMMENT',
    'LIKE_COMMENT': 'LIKE',
    'DO_NOTHING': 'IDLE',
    'FOLLOW': 'FOLLOW',
    'SEARCH_POSTS': 'SEARCH',
    'QUOTE_POST': 'QUOTE',
    'UPVOTE_POST': 'UPVOTE',
    'DOWNVOTE_POST': 'DOWNVOTE'
  }
  return labels[type] || type || 'UNKNOWN'
}

const getActionTypeClass = (type) => {
  const classes = {
    'CREATE_POST': 'badge-post',
    'REPOST': 'badge-action',
    'LIKE_POST': 'badge-action',
    'CREATE_COMMENT': 'badge-comment',
    'LIKE_COMMENT': 'badge-action',
    'QUOTE_POST': 'badge-post',
    'FOLLOW': 'badge-meta',
    'SEARCH_POSTS': 'badge-meta',
    'UPVOTE_POST': 'badge-action',
    'DOWNVOTE_POST': 'badge-action',
    'DO_NOTHING': 'badge-idle'
  }
  return classes[type] || 'badge-default'
}

const truncateContent = (content, maxLength = 100) => {
  if (!content) return ''
  if (content.length > maxLength) return content.substring(0, maxLength) + '...'
  return content
}

const formatActionTime = (timestamp) => {
  if (!timestamp) return ''
  try {
    return new Date(timestamp).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return ''
  }
}

const handleNextStep = async () => {
  if (!props.simulationId) {
    addLog(t('log.errorMissingSimId'))
    return
  }

  if (isGeneratingReport.value) {
    addLog(t('log.reportRequestSent'))
    return
  }
  
  isGeneratingReport.value = true
  addLog(t('log.startingReportGen'))
  
  try {
    const res = await generateReport({
      simulation_id: props.simulationId,
      // The public site makes one report per run; asking again returns that report.
      force_regenerate: import.meta.env.VITE_PUBLIC !== '1'
    })
    
    if (res.success && res.data) {
      const reportId = res.data.report_id
      addLog(t('log.reportGenTaskStarted', { reportId }))
      
      // Go to the report page
      router.push({ name: 'Report', params: { reportId } })
    } else {
      addLog(t('log.reportGenFailed', { error: res.error || t('common.unknownError') }))
      isGeneratingReport.value = false
    }
  } catch (err) {
    addLog(t('log.reportGenException', { error: err.message }))
    isGeneratingReport.value = false
  }
}

// Scroll log to bottom
const logContent = ref(null)
watch(() => props.systemLogs?.length, () => {
  nextTick(() => {
    if (logContent.value) {
      logContent.value.scrollTop = logContent.value.scrollHeight
    }
  })
})

// Hivemind: opening this page must not restart (and re-bill) an existing run.
// Only Step 2's Start button (?start=1) or a never-started simulation starts one;
// refreshes, the Analytics back button and history links reattach to the run.
const resumeExistingRun = async () => {
  try {
    const res = await getRunStatus(props.simulationId)
    const status = res?.data?.runner_status
    if (!status || status === 'idle') return false
    runStatus.value = res.data
    phase.value = (['completed', 'stopped', 'failed'].includes(status) || res.data.ready_for_report) ? 2 : 1
    addLog(t('log.resumeExistingRun', { status }))
    startStatusPolling()
    startDetailPolling()
    return true
  } catch (err) {
    return false
  }
}

onMounted(async () => {
  addLog(t('log.step3Init'))
  if (!props.simulationId) return
  const explicitStart = route.query.start === '1'
  if (explicitStart) {
    const { start, ...rest } = route.query
    router.replace({ query: rest })
  }
  if (!explicitStart && await resumeExistingRun()) return
  doStartSimulation()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.start-error {
  gap: var(--hm-space-3, 12px);
  max-width: 460px;
  margin: 0 auto;
  text-align: center;
  color: var(--hm-danger);
}

.simulation-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--hm-paper);
  font-family: var(--hm-font-sans);
}

/* ------------------------------------------------------------ control bar */
.control-bar {
  z-index: 10;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--hm-space-2) var(--hm-space-4);
  min-height: 68px;
  padding: var(--hm-space-3) var(--hm-space-5);
  background: var(--hm-surface);
  border-bottom: 1px solid var(--hm-line);
}

.status-group {
  display: flex;
  flex-wrap: wrap;
  gap: var(--hm-space-2);
}

.platform-status {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: var(--hm-space-1);
  flex: 0 0 auto;
  min-width: 150px;
  padding: var(--hm-space-2) var(--hm-space-3);
  background: var(--hm-surface-2);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-md);
  cursor: default;
  transition: border-color var(--hm-duration) var(--hm-ease), box-shadow var(--hm-duration) var(--hm-ease), background-color var(--hm-duration) var(--hm-ease);
}

.platform-status.active {
  background: var(--hm-surface);
  border-color: var(--hm-signal);
  box-shadow: 0 0 0 3px var(--hm-signal-soft);
}

.platform-status.completed {
  background: var(--hm-surface);
  border-color: var(--hm-line);
}

.platform-header {
  display: flex;
  align-items: center;
  gap: 6px;
}

.platform-icon {
  color: var(--hm-ink-3);
  flex-shrink: 0;
}

.platform-status.active .platform-icon {
  color: var(--hm-signal-ink);
}

.platform-name {
  font-size: var(--hm-text-2xs);
  font-weight: 500;
  font-family: var(--hm-font-mono);
  letter-spacing: var(--hm-tracking-label);
  text-transform: uppercase;
  color: var(--hm-ink);
  white-space: nowrap;
}

.status-badge {
  display: flex;
  align-items: center;
  margin-left: auto;
  color: var(--hm-success-dot);
}

.platform-stats {
  display: flex;
  gap: var(--hm-space-3);
}

.stat {
  display: flex;
  align-items: baseline;
  gap: var(--hm-space-1);
  white-space: nowrap;
}

.stat-label {
  font-size: 10px;
  font-weight: 500;
  font-family: var(--hm-font-mono);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--hm-ink-4);
}

.stat-value {
  font-size: var(--hm-text-xs);
  font-weight: 600;
  color: var(--hm-ink);
  font-variant-numeric: tabular-nums;
}

.stat-total,
.stat-unit {
  font-size: 10px;
  font-weight: 400;
  color: var(--hm-ink-4);
}

/* Hover tooltip listing the platform's actions */
.actions-tooltip {
  position: absolute;
  top: 100%;
  left: 50%;
  z-index: 100;
  min-width: 200px;
  margin-top: var(--hm-space-2);
  padding: var(--hm-space-3);
  background: var(--hm-ink);
  color: var(--hm-surface);
  border-radius: var(--hm-radius-md);
  box-shadow: var(--hm-shadow-md);
  opacity: 0;
  visibility: hidden;
  transform: translate(-50%, 4px);
  pointer-events: none;
  transition: opacity var(--hm-duration-fast) var(--hm-ease), transform var(--hm-duration-fast) var(--hm-ease), visibility var(--hm-duration-fast);
}

.actions-tooltip::before {
  content: "";
  position: absolute;
  top: -5px;
  left: 50%;
  transform: translateX(-50%);
  border-left: 5px solid transparent;
  border-right: 5px solid transparent;
  border-bottom: 5px solid var(--hm-ink);
}

.platform-status:hover .actions-tooltip {
  opacity: 1;
  visibility: visible;
  transform: translate(-50%, 0);
}

.tooltip-title {
  margin-bottom: var(--hm-space-2);
  font-size: 10px;
  font-weight: 500;
  font-family: var(--hm-font-mono);
  letter-spacing: var(--hm-tracking-label);
  text-transform: uppercase;
  color: var(--hm-console-muted);
}

.tooltip-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--hm-space-1);
}

.tooltip-action {
  padding: 2px 6px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: var(--hm-radius-xs);
  font-family: var(--hm-font-mono);
  font-size: 10px;
  font-weight: 500;
  color: var(--hm-surface);
}

/* Buttons */
.action-controls {
  display: flex;
  gap: var(--hm-space-2);
  flex-shrink: 0;
  margin-left: auto;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--hm-space-2);
  height: 40px;
  padding: 0 var(--hm-space-4);
  border: 1px solid transparent;
  border-radius: var(--hm-radius-sm);
  font-size: var(--hm-text-sm);
  font-weight: 600;
  white-space: nowrap;
  cursor: pointer;
  transition: background-color var(--hm-duration-fast) var(--hm-ease), border-color var(--hm-duration-fast) var(--hm-ease);
}

.action-btn.primary {
  background: var(--hm-signal);
  color: var(--hm-ink);
}

.action-btn.primary:hover:not(:disabled) {
  background: var(--hm-signal-hover);
}

.action-btn.secondary {
  background: var(--hm-surface);
  border-color: var(--hm-line-strong);
  color: var(--hm-ink);
}

.action-btn.secondary:hover:not(:disabled) {
  background: var(--hm-surface-2);
  border-color: var(--hm-ink-5);
}

.action-btn:disabled {
  background: var(--hm-surface-3);
  border-color: transparent;
  color: var(--hm-ink-5);
  cursor: not-allowed;
}

.loading-spinner-small {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: var(--hm-surface);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* ------------------------------------------------------------- timeline */
.main-content-area {
  position: relative;
  flex: 1;
  overflow-y: auto;
  background: var(--hm-surface-2);
}

.timeline-header {
  position: sticky;
  top: 0;
  z-index: 5;
  display: flex;
  justify-content: center;
  padding: var(--hm-space-3) var(--hm-space-6);
  background: rgba(243, 240, 232, 0.9);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--hm-line);
}

.timeline-stats {
  display: flex;
  align-items: center;
  gap: var(--hm-space-4);
  height: 28px;
  padding: 0 var(--hm-space-3);
  background: var(--hm-surface);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-pill);
  font-size: var(--hm-text-2xs);
  color: var(--hm-ink-3);
}

.total-count {
  font-weight: 500;
  font-family: var(--hm-font-mono);
  letter-spacing: 0.06em;
  color: var(--hm-ink-3);
}

.total-count .mono {
  color: var(--hm-ink);
  letter-spacing: 0;
}

.platform-breakdown {
  display: flex;
  align-items: center;
  gap: var(--hm-space-2);
}

.breakdown-item {
  display: flex;
  align-items: center;
  gap: var(--hm-space-1);
  color: var(--hm-ink);
}

.breakdown-divider {
  color: var(--hm-line-strong);
}

.timeline-feed {
  position: relative;
  max-width: 920px;
  min-height: 100%;
  margin: 0 auto;
  padding: var(--hm-space-6) 0;
}

.timeline-axis {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 50%;
  width: 1px;
  background: var(--hm-line-strong);
  transform: translateX(-50%);
}

.timeline-item {
  position: relative;
  display: flex;
  justify-content: center;
  width: 100%;
  margin-bottom: var(--hm-space-6);
}

.timeline-marker {
  position: absolute;
  top: 22px;
  left: 50%;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 11px;
  height: 11px;
  background: var(--hm-surface);
  border: 1.5px solid var(--hm-ink);
  border-radius: 50%;
  transform: translateX(-50%);
}

.marker-dot {
  width: 3px;
  height: 3px;
  background: var(--hm-ink);
  border-radius: 50%;
}

.timeline-card {
  position: relative;
  width: calc(100% - 48px);
  padding: var(--hm-space-4) var(--hm-space-5);
  background: var(--hm-surface);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-md);
  transition: border-color var(--hm-duration-fast) var(--hm-ease), box-shadow var(--hm-duration-fast) var(--hm-ease);
}

.timeline-card:hover {
  border-color: var(--hm-line-strong);
  box-shadow: var(--hm-shadow-sm);
}

/* Info Plaza on the left of the axis, Topic Community on the right */
.timeline-item.twitter {
  justify-content: flex-start;
  padding-right: 50%;
}

.timeline-item.twitter .timeline-card {
  margin-left: auto;
  margin-right: var(--hm-space-8);
}

.timeline-item.reddit {
  justify-content: flex-end;
  padding-left: 50%;
}

.timeline-item.reddit .timeline-card {
  margin-right: auto;
  margin-left: var(--hm-space-8);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--hm-space-2);
  margin-bottom: var(--hm-space-3);
  padding-bottom: var(--hm-space-3);
  border-bottom: 1px solid var(--hm-line);
}

.agent-info {
  display: flex;
  align-items: center;
  gap: var(--hm-space-2);
  min-width: 0;
}

/* Agents are hive cells */
.avatar-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 24px;
  height: 26px;
  background: var(--hm-ink);
  color: var(--hm-surface);
  clip-path: polygon(50% 0, 100% 25%, 100% 75%, 50% 100%, 0 75%, 0 25%);
  font-size: var(--hm-text-2xs);
  font-weight: 700;
  text-transform: uppercase;
}

.agent-name {
  overflow: hidden;
  font-size: var(--hm-text-sm);
  font-weight: 600;
  color: var(--hm-ink);
  white-space: nowrap;
  text-overflow: ellipsis;
}

.header-meta {
  display: flex;
  align-items: center;
  gap: var(--hm-space-2);
  flex-shrink: 0;
}

.platform-indicator {
  display: flex;
  align-items: center;
  color: var(--hm-ink-4);
}

.action-badge {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 var(--hm-space-2);
  border: 1px solid transparent;
  border-radius: var(--hm-radius-pill);
  font-size: 10px;
  font-weight: 500;
  font-family: var(--hm-font-mono);
  letter-spacing: 0.05em;
  text-transform: uppercase;
  white-space: nowrap;
}

.badge-post { background: var(--hm-ink); color: var(--hm-surface); }
.badge-comment { background: var(--hm-surface-3); color: var(--hm-ink-2); }
.badge-action { background: var(--hm-surface); color: var(--hm-ink-3); border-color: var(--hm-line-strong); }
.badge-meta { background: var(--hm-surface-2); color: var(--hm-ink-4); border: 1px dashed var(--hm-line-strong); }
.badge-idle { opacity: 0.6; }

.content-text {
  margin-bottom: var(--hm-space-2);
  font-size: var(--hm-text-sm);
  line-height: 1.6;
  color: var(--hm-ink-2);
}

.content-text.main-text {
  font-size: var(--hm-text-base);
  color: var(--hm-ink);
}

.quoted-block,
.repost-content {
  margin-top: var(--hm-space-2);
  padding: var(--hm-space-2) var(--hm-space-3);
  background: var(--hm-surface-2);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-sm);
  font-size: var(--hm-text-xs);
  line-height: var(--hm-leading-normal);
  color: var(--hm-ink-3);
}

.quote-header,
.repost-info,
.like-info,
.search-info,
.follow-info,
.vote-info,
.idle-info,
.comment-context {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
  font-size: var(--hm-text-xs);
  color: var(--hm-ink-3);
}

.icon-small,
.icon-small.filled {
  flex-shrink: 0;
  color: var(--hm-ink-4);
}

.search-query {
  padding: 0 var(--hm-space-1);
  background: var(--hm-surface-3);
  border-radius: var(--hm-radius-xs);
  font-family: var(--hm-font-mono);
}

.card-footer {
  display: flex;
  justify-content: flex-end;
  margin-top: var(--hm-space-3);
  font-family: var(--hm-font-mono);
  font-size: 10px;
  color: var(--hm-ink-4);
}

/* Waiting state */
.waiting-state {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--hm-space-4);
  font-size: var(--hm-text-sm);
  color: var(--hm-ink-4);
}

.pulse-ring {
  width: 28px;
  height: 28px;
  border: 1.5px solid var(--hm-signal);
  border-radius: 50%;
  animation: ripple 2s var(--hm-ease) infinite;
}

@keyframes ripple {
  0% { transform: scale(0.8); opacity: 1; }
  100% { transform: scale(2.2); opacity: 0; }
}

.timeline-item-enter-active,
.timeline-item-leave-active {
  transition: opacity 0.4s var(--hm-ease), transform 0.4s var(--hm-ease);
}

.timeline-item-enter-from {
  opacity: 0;
  transform: translateY(12px);
}

.timeline-item-leave-to {
  opacity: 0;
}

/* ------------------------------------------------------ live log console */
.system-logs {
  flex-shrink: 0;
  padding: var(--hm-space-3) var(--hm-space-5) var(--hm-space-4);
  background: var(--hm-console-bg);
  border-top: 1px solid var(--hm-console-line);
  color: var(--hm-console-text);
  font-family: var(--hm-font-mono);
}

.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--hm-space-3);
  padding-bottom: var(--hm-space-2);
  margin-bottom: var(--hm-space-2);
  border-bottom: 1px solid var(--hm-console-line);
}

.log-title {
  display: inline-flex;
  align-items: center;
  gap: var(--hm-space-2);
  
  font-size: var(--hm-text-2xs);
  font-weight: 500;
  font-family: var(--hm-font-mono);
  letter-spacing: var(--hm-tracking-label);
  text-transform: uppercase;
  color: var(--hm-console-muted);
}

.log-title::before {
  content: "";
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--hm-on-ink);
}

.log-id {
  font-size: var(--hm-text-2xs);
  color: var(--hm-console-muted);
}

.log-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
  height: 100px;
  overflow-y: auto;
  padding-right: var(--hm-space-1);
}

.log-content::-webkit-scrollbar {
  width: 4px;
}

.log-content::-webkit-scrollbar-thumb {
  background: var(--hm-console-line);
  border: none;
  border-radius: 2px;
}

.log-line {
  display: flex;
  gap: var(--hm-space-3);
  font-size: var(--hm-text-xs);
  line-height: 1.6;
}

.log-time {
  min-width: 84px;
  color: var(--hm-console-muted);
  font-variant-numeric: tabular-nums;
}

.log-msg {
  color: var(--hm-console-text);
  word-break: break-word;
}

.mono {
  font-family: var(--hm-font-mono);
}
</style>

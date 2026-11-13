<template>
  <div class="workbench-panel">
    <div class="scroll-container">
      <!-- Step 01: Ontology -->
      <div class="step-card" :class="{ 'active': currentPhase === 0, 'completed': currentPhase > 0 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">01</span>
            <span class="step-title">{{ $t('step1.ontologyGeneration') }}</span>
          </div>
          <div class="step-status">
            <span v-if="currentPhase > 0" class="badge success">{{ $t('step1.ontologyCompleted') }}</span>
            <span v-else-if="currentPhase === 0" class="badge processing">{{ $t('step1.ontologyGenerating') }}</span>
            <span v-else class="badge pending">{{ $t('step1.ontologyPending') }}</span>
          </div>
        </div>
        
        <div class="card-content">
          <p class="api-note">POST /api/graph/ontology/generate</p>
          <p class="description">
            {{ $t('step1.ontologyDesc') }}
          </p>

          <!-- Loading / Progress -->
          <div v-if="currentPhase === 0 && ontologyProgress" class="progress-section">
            <div class="spinner-sm"></div>
            <span>{{ ontologyProgress.message || $t('step1.analyzingDocs') }}</span>
          </div>

          <!-- Detail Overlay -->
          <div v-if="selectedOntologyItem" class="ontology-detail-overlay">
            <div class="detail-header">
               <div class="detail-title-group">
                  <span class="detail-type-badge">{{ selectedOntologyItem.itemType === 'entity' ? 'ENTITY' : 'RELATION' }}</span>
                  <span class="detail-name">{{ selectedOntologyItem.name }}</span>
               </div>
               <button class="close-btn" aria-label="Close" @click="selectedOntologyItem = null">
                 <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
               </button>
            </div>
            <div class="detail-body">
               <div class="detail-desc">{{ selectedOntologyItem.description }}</div>
               
               <!-- Attributes -->
               <div class="detail-section" v-if="selectedOntologyItem.attributes?.length">
                  <span class="section-label">ATTRIBUTES</span>
                  <div class="attr-list">
                     <div v-for="attr in selectedOntologyItem.attributes" :key="attr.name" class="attr-item">
                        <span class="attr-name">{{ attr.name }}</span>
                        <span class="attr-type">({{ attr.type }})</span>
                        <span class="attr-desc">{{ attr.description }}</span>
                     </div>
                  </div>
               </div>

               <!-- Examples (Entity) -->
               <div class="detail-section" v-if="selectedOntologyItem.examples?.length">
                  <span class="section-label">EXAMPLES</span>
                  <div class="example-list">
                     <span v-for="ex in selectedOntologyItem.examples" :key="ex" class="example-tag">{{ ex }}</span>
                  </div>
               </div>

               <!-- Source/Target (Relation) -->
               <div class="detail-section" v-if="selectedOntologyItem.source_targets?.length">
                  <span class="section-label">CONNECTIONS</span>
                  <div class="conn-list">
                     <div v-for="(conn, idx) in selectedOntologyItem.source_targets" :key="idx" class="conn-item">
                        <span class="conn-node">{{ conn.source }}</span>
                        <span class="conn-arrow">→</span>
                        <span class="conn-node">{{ conn.target }}</span>
                     </div>
                  </div>
               </div>
            </div>
          </div>

          <!-- Generated Entity Tags -->
          <div v-if="projectData?.ontology?.entity_types" class="tags-container" :class="{ 'dimmed': selectedOntologyItem }">
            <span class="tag-label">GENERATED ENTITY TYPES</span>
            <div class="tags-list">
              <span 
                v-for="entity in projectData.ontology.entity_types" 
                :key="entity.name" 
                class="entity-tag clickable"
                @click="selectOntologyItem(entity, 'entity')"
              >
                {{ entity.name }}
              </span>
            </div>
          </div>

          <!-- Generated Relation Tags -->
          <div v-if="projectData?.ontology?.edge_types" class="tags-container" :class="{ 'dimmed': selectedOntologyItem }">
            <span class="tag-label">GENERATED RELATION TYPES</span>
            <div class="tags-list">
              <span 
                v-for="rel in projectData.ontology.edge_types" 
                :key="rel.name" 
                class="entity-tag clickable"
                @click="selectOntologyItem(rel, 'relation')"
              >
                {{ rel.name }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Step 02: Graph Build -->
      <div class="step-card" :class="{ 'active': currentPhase === 1, 'completed': currentPhase > 1 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">02</span>
            <span class="step-title">{{ $t('step1.graphRagBuild') }}</span>
          </div>
          <div class="step-status">
            <span v-if="currentPhase > 1" class="badge success">{{ $t('step1.ontologyCompleted') }}</span>
            <span v-else-if="currentPhase === 1" class="badge processing">{{ buildProgress?.progress || 0 }}%</span>
            <span v-else class="badge pending">{{ $t('step1.ontologyPending') }}</span>
          </div>
        </div>

        <div class="card-content">
          <p class="api-note">POST /api/graph/build</p>
          <p class="description">
            {{ $t('step1.graphRagDesc') }}
          </p>
          
          <!-- Stats Cards -->
          <div class="stats-grid">
            <div class="stat-card">
              <span class="stat-value">{{ graphStats.nodes }}</span>
              <span class="stat-label">{{ $t('step1.entityNodes') }}</span>
            </div>
            <div class="stat-card">
              <span class="stat-value">{{ graphStats.edges }}</span>
              <span class="stat-label">{{ $t('step1.relationEdges') }}</span>
            </div>
            <div class="stat-card">
              <span class="stat-value">{{ graphStats.types }}</span>
              <span class="stat-label">{{ $t('step1.schemaTypes') }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Step 03: Complete -->
      <div class="step-card" :class="{ 'active': currentPhase === 2, 'completed': currentPhase >= 2 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">03</span>
            <span class="step-title">{{ $t('step1.buildComplete') }}</span>
          </div>
          <div class="step-status">
            <span v-if="currentPhase >= 2" class="badge accent">{{ $t('step1.inProgress') }}</span>
          </div>
        </div>
        
        <div class="card-content">
          <p class="api-note">POST /api/simulation/create</p>
          <p class="description">{{ $t('step1.buildCompleteDesc') }}</p>
          <button 
            class="action-btn" 
            :disabled="currentPhase < 2 || creatingSimulation"
            @click="handleEnterEnvSetup"
          >
            <span v-if="creatingSimulation" class="spinner-sm"></span>
            {{ creatingSimulation ? $t('step1.creating') : $t('step1.enterEnvSetup') + ' →' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Bottom Info / Logs -->
    <div class="system-logs">
      <div class="log-header">
        <span class="log-title">SYSTEM DASHBOARD</span>
        <span class="log-id">{{ projectData?.project_id || 'NO_PROJECT' }}</span>
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
import { computed, ref, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { createSimulation } from '../api/simulation'

const router = useRouter()
const { t } = useI18n()

const props = defineProps({
  currentPhase: { type: Number, default: 0 },
  projectData: Object,
  ontologyProgress: Object,
  buildProgress: Object,
  graphData: Object,
  systemLogs: { type: Array, default: () => [] }
})

defineEmits(['next-step'])

const selectedOntologyItem = ref(null)
const logContent = ref(null)
const creatingSimulation = ref(false)

// 进入环境搭建 - 创建 simulation 并跳转
const handleEnterEnvSetup = async () => {
  if (!props.projectData?.project_id || !props.projectData?.graph_id) {
    console.error('缺少项目或图谱信息')
    return
  }
  
  creatingSimulation.value = true
  
  try {
    const res = await createSimulation({
      project_id: props.projectData.project_id,
      graph_id: props.projectData.graph_id,
      enable_twitter: true,
      enable_reddit: true
    })
    
    if (res.success && res.data?.simulation_id) {
      // 跳转到 simulation 页面
      router.push({
        name: 'Simulation',
        params: { simulationId: res.data.simulation_id }
      })
    } else {
      console.error('创建模拟失败:', res.error)
      alert(t('step1.createSimulationFailed', { error: res.error || t('common.unknownError') }))
    }
  } catch (err) {
    console.error('创建模拟异常:', err)
    alert(t('step1.createSimulationException', { error: err.message }))
  } finally {
    creatingSimulation.value = false
  }
}

const selectOntologyItem = (item, type) => {
  selectedOntologyItem.value = { ...item, itemType: type }
}

const graphStats = computed(() => {
  const nodes = props.graphData?.node_count || props.graphData?.nodes?.length || 0
  const edges = props.graphData?.edge_count || props.graphData?.edges?.length || 0
  const types = props.projectData?.ontology?.entity_types?.length || 0
  return { nodes, edges, types }
})

const formatDate = (dateStr) => {
  if (!dateStr) return '--:--:--'
  const d = new Date(dateStr)
  return d.toLocaleTimeString('en-US', { hour12: false }) + '.' + d.getMilliseconds()
}

// Auto-scroll logs
watch(() => props.systemLogs.length, () => {
  nextTick(() => {
    if (logContent.value) {
      logContent.value.scrollTop = logContent.value.scrollHeight
    }
  })
})
</script>

<style scoped>
.workbench-panel {
  height: 100%;
  background-color: var(--hm-paper);
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
}

.scroll-container {
  flex: 1;
  overflow-y: auto;
  padding: var(--hm-space-6);
  display: flex;
  flex-direction: column;
  gap: var(--hm-space-4);
}

/* Step cards */
.step-card {
  position: relative; /* anchors the ontology detail overlay */
  background: var(--hm-surface);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-lg);
  padding: var(--hm-space-5) var(--hm-space-6) var(--hm-space-6);
  transition: border-color var(--hm-duration) var(--hm-ease), box-shadow var(--hm-duration) var(--hm-ease);
}

.step-card.active {
  border-color: var(--hm-signal);
  box-shadow: 0 0 0 3px var(--hm-signal-soft);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--hm-space-3);
  margin-bottom: var(--hm-space-3);
}

.step-info {
  display: flex;
  align-items: baseline;
  gap: var(--hm-space-3);
  min-width: 0;
}

.step-num {
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-sm);
  font-weight: 500;
  color: var(--hm-ink-4);
  font-variant-numeric: tabular-nums;
}

.step-card.completed .step-num {
  color: var(--hm-ink);
}

.step-card.active .step-num {
  color: var(--hm-signal-ink);
}

.step-title {
  font-family: var(--hm-font-display);
  font-size: var(--hm-text-md);
  font-weight: 500;
  letter-spacing: -0.01em;
  color: var(--hm-ink);
}

.step-card:not(.active):not(.completed) .step-title {
  color: var(--hm-ink-3);
}

/* Status badges: same anatomy as .hm-pill */
.badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 22px;
  padding: 0 var(--hm-space-2);
  border-radius: var(--hm-radius-pill);
  font-size: var(--hm-text-2xs);
  font-weight: 500;
  font-family: var(--hm-font-mono);
  letter-spacing: 0.04em;
  text-transform: uppercase;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.badge::before {
  content: "";
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  flex-shrink: 0;
}

.badge.success { background: var(--hm-success-soft); color: var(--hm-success); }
.badge.success::before { background: var(--hm-success-dot); }
.badge.processing,
.badge.accent { background: var(--hm-signal-soft); color: var(--hm-signal-ink); }
.badge.processing::before,
.badge.accent::before { background: var(--hm-signal); animation: hm-pulse 1.4s var(--hm-ease) infinite; }
.badge.pending { background: var(--hm-surface-3); color: var(--hm-ink-3); }
.badge.pending::before { background: var(--hm-ink-5); }

.api-note {
  display: inline-block;
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-2xs);
  color: var(--hm-ink-4);
  margin-bottom: var(--hm-space-2);
}

.description {
  font-size: var(--hm-text-sm);
  color: var(--hm-ink-3);
  line-height: var(--hm-leading-normal);
  margin-bottom: var(--hm-space-4);
  max-width: 68ch;
}

/* Step 01 tags */
.tags-container {
  margin-top: var(--hm-space-4);
  transition: opacity var(--hm-duration) var(--hm-ease);
}

.tags-container.dimmed {
  opacity: 0.3;
  pointer-events: none;
}

.tag-label,
.section-label {
  display: block;
  margin-bottom: var(--hm-space-2);
  font-size: var(--hm-text-2xs);
  font-weight: 500;
  font-family: var(--hm-font-mono);
  letter-spacing: var(--hm-tracking-label);
  text-transform: uppercase;
  color: var(--hm-ink-4);
}

.tags-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--hm-space-2);
}

.entity-tag {
  display: inline-flex;
  align-items: center;
  height: 26px;
  padding: 0 var(--hm-space-2);
  background: var(--hm-surface-2);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-xs);
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-xs);
  color: var(--hm-ink-2);
  transition: background-color var(--hm-duration-fast) var(--hm-ease), border-color var(--hm-duration-fast) var(--hm-ease);
}

.entity-tag.clickable {
  cursor: pointer;
}

.entity-tag.clickable:hover {
  background: var(--hm-surface);
  border-color: var(--hm-ink-5);
  color: var(--hm-ink);
}

/* Ontology detail overlay */
.ontology-detail-overlay {
  position: absolute;
  top: 56px;
  left: var(--hm-space-4);
  right: var(--hm-space-4);
  bottom: var(--hm-space-4);
  z-index: 10;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--hm-surface);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-md);
  box-shadow: var(--hm-shadow-md);
  animation: fadeIn var(--hm-duration) var(--hm-ease);
}

@keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--hm-space-2) var(--hm-space-2) var(--hm-space-2) var(--hm-space-4);
  border-bottom: 1px solid var(--hm-line);
  background: var(--hm-surface-2);
}

.detail-title-group {
  display: flex;
  align-items: center;
  gap: var(--hm-space-2);
  min-width: 0;
}

.detail-type-badge {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 var(--hm-space-2);
  border-radius: var(--hm-radius-pill);
  background: var(--hm-ink);
  color: var(--hm-surface);
  font-size: 10px;
  font-weight: 500;
  font-family: var(--hm-font-mono);
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.detail-name {
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-base);
  font-weight: 600;
  color: var(--hm-ink);
}

.close-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: var(--hm-radius-sm);
  background: transparent;
  color: var(--hm-ink-4);
  cursor: pointer;
  transition: background-color var(--hm-duration-fast) var(--hm-ease), color var(--hm-duration-fast) var(--hm-ease);
}

.close-btn:hover {
  background: var(--hm-surface-3);
  color: var(--hm-ink);
}

.detail-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--hm-space-4);
}

.detail-desc {
  font-size: var(--hm-text-sm);
  color: var(--hm-ink-2);
  line-height: var(--hm-leading-normal);
  margin-bottom: var(--hm-space-4);
  padding-bottom: var(--hm-space-4);
  border-bottom: 1px solid var(--hm-line);
}

.detail-section {
  margin-bottom: var(--hm-space-4);
}

.attr-list,
.conn-list {
  display: flex;
  flex-direction: column;
  gap: var(--hm-space-1);
}

.attr-item {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 6px;
  padding: 6px var(--hm-space-2);
  background: var(--hm-surface-2);
  border-radius: var(--hm-radius-xs);
  font-size: var(--hm-text-xs);
}

.attr-name {
  font-family: var(--hm-font-mono);
  font-weight: 600;
  color: var(--hm-ink);
}

.attr-type {
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-2xs);
  color: var(--hm-ink-4);
}

.attr-desc {
  flex: 1;
  min-width: 150px;
  color: var(--hm-ink-3);
}

.example-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.example-tag {
  padding: 3px var(--hm-space-2);
  background: var(--hm-surface-2);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-xs);
  font-size: var(--hm-text-xs);
  color: var(--hm-ink-2);
}

.conn-item {
  display: flex;
  align-items: center;
  gap: var(--hm-space-2);
  padding: 6px var(--hm-space-2);
  background: var(--hm-surface-2);
  border-radius: var(--hm-radius-xs);
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-xs);
}

.conn-node {
  font-weight: 600;
  color: var(--hm-ink-2);
}

.conn-arrow {
  color: var(--hm-ink-5);
}

/* Step 02 stats */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  background: var(--hm-surface-2);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-md);
}

.stat-card {
  display: flex;
  flex-direction: column;
  gap: var(--hm-space-1);
  padding: var(--hm-space-4) var(--hm-space-5);
}

.stat-card + .stat-card {
  border-left: 1px solid var(--hm-line);
}

.stat-value {
  font-family: var(--hm-font-display);
  font-size: var(--hm-text-2xl);
  font-weight: 500;
  line-height: 1.05;
  letter-spacing: var(--hm-tracking-display);
  font-variant-numeric: tabular-nums;
  color: var(--hm-ink);
}

.stat-label {
  font-size: var(--hm-text-2xs);
  font-weight: 500;
  font-family: var(--hm-font-mono);
  letter-spacing: var(--hm-tracking-label);
  text-transform: uppercase;
  color: var(--hm-ink-4);
}

/* Step 03 primary action */
.action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--hm-space-2);
  width: 100%;
  height: 44px;
  padding: 0 var(--hm-space-5);
  background: var(--hm-signal);
  color: var(--hm-ink);
  border: none;
  border-radius: var(--hm-radius-sm);
  font-size: var(--hm-text-base);
  font-weight: 600;
  cursor: pointer;
  transition: background-color var(--hm-duration-fast) var(--hm-ease);
}

.action-btn:hover:not(:disabled) {
  background: var(--hm-signal-hover);
}

.action-btn:disabled {
  background: var(--hm-surface-3);
  color: var(--hm-ink-5);
  cursor: not-allowed;
}

.action-btn .spinner-sm {
  border-color: rgba(22, 20, 15, 0.2);
  border-top-color: var(--hm-ink);
}

.progress-section {
  display: flex;
  align-items: center;
  gap: var(--hm-space-2);
  margin-bottom: var(--hm-space-3);
  padding: var(--hm-space-2) var(--hm-space-3);
  background: var(--hm-signal-soft);
  border-radius: var(--hm-radius-sm);
  font-size: var(--hm-text-sm);
  color: var(--hm-signal-ink);
}

.spinner-sm {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
  border: 2px solid var(--hm-line-strong);
  border-top-color: var(--hm-ink);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.progress-section .spinner-sm {
  border-color: rgba(122, 77, 0, 0.2);
  border-top-color: var(--hm-signal-ink);
}

@keyframes spin { to { transform: rotate(360deg); } }

@keyframes hm-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}

/* Live log console */
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
  height: 84px;
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
</style>

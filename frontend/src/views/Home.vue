<template>
  <div class="home-container">
    <!-- 顶部导航栏 -->
    <AppHeader />

    <div class="main-content">
      <!-- 上半部分：Hero 区域 -->
      <section class="hero-section">
        <div class="hero-left">
          <div class="tag-row">
            <span class="orange-tag">{{ $t('home.tagline') }}</span>
            <span class="version-text">{{ $t('home.version') }}</span>
          </div>
          
          <h1 class="main-title">
            {{ $t('home.heroTitle1') }}<br>
            <span class="gradient-text">{{ $t('home.heroTitle2') }}</span>
          </h1>
          
          <div class="hero-desc">
            <p>
              <i18n-t keypath="home.heroDesc" tag="span">
                <template #brand><span class="highlight-bold">{{ $t('home.heroDescBrand') }}</span></template>
                <template #agentScale><span class="highlight-orange">{{ $t('home.heroDescAgentScale') }}</span></template>
                <template #optimalSolution><span class="highlight-code">{{ $t('home.heroDescOptimalSolution') }}</span></template>
              </i18n-t>
            </p>
            <p class="slogan-text">
              {{ $t('home.slogan') }}<span class="blinking-cursor">_</span>
            </p>
          </div>
           
          <div class="decoration-square"></div>
        </div>
        
        <div class="hero-right">
          <!-- Logo 区域 -->
          <div class="logo-container">
            <HivemindMark class="hero-logo" :size="136" animated />
          </div>
          
          <button class="scroll-down-btn" @click="scrollToBottom">
            ↓
          </button>
        </div>
      </section>

      <!-- 下半部分：双栏布局 -->
      <section class="dashboard-section">
        <!-- 左栏：状态与步骤 -->
        <div class="left-panel">
          <div class="panel-header">
            <span class="status-dot" aria-hidden="true"></span> {{ $t('home.systemStatus') }}
          </div>
          
          <h2 class="section-title">{{ $t('home.systemReady') }}</h2>
          <p class="section-desc">
            {{ $t('home.systemReadyDesc') }}
          </p>
          
          <!-- 数据指标卡片 -->
          <div class="metrics-row">
            <div class="metric-card">
              <div class="metric-value">{{ $t('home.metricLowCost') }}</div>
              <div class="metric-label">{{ $t('home.metricLowCostDesc') }}</div>
            </div>
            <div class="metric-card">
              <div class="metric-value">{{ $t('home.metricHighAvail') }}</div>
              <div class="metric-label">{{ $t('home.metricHighAvailDesc') }}</div>
            </div>
          </div>

          <!-- 项目模拟步骤介绍 (新增区域) -->
          <div class="steps-container">
            <div class="steps-header">
               <span class="diamond-icon" aria-hidden="true"></span> {{ $t('home.workflowSequence') }}
            </div>
            <div class="workflow-list">
              <div class="workflow-item">
                <span class="step-num">01</span>
                <div class="step-info">
                  <div class="step-title">{{ $t('home.step01Title') }}</div>
                  <div class="step-desc">{{ $t('home.step01Desc') }}</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">02</span>
                <div class="step-info">
                  <div class="step-title">{{ $t('home.step02Title') }}</div>
                  <div class="step-desc">{{ $t('home.step02Desc') }}</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">03</span>
                <div class="step-info">
                  <div class="step-title">{{ $t('home.step03Title') }}</div>
                  <div class="step-desc">{{ $t('home.step03Desc') }}</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">04</span>
                <div class="step-info">
                  <div class="step-title">{{ $t('home.step04Title') }}</div>
                  <div class="step-desc">{{ $t('home.step04Desc') }}</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">05</span>
                <div class="step-info">
                  <div class="step-title">{{ $t('home.step05Title') }}</div>
                  <div class="step-desc">{{ $t('home.step05Desc') }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 右栏：交互控制台 -->
        <div class="right-panel">
          <div class="console-box">
            <!-- 上传区域 -->
            <div class="console-section">
              <div class="console-header">
                <span class="console-label">{{ $t('home.realitySeed') }}</span>
                <span class="console-meta">{{ $t('home.supportedFormats') }}</span>
              </div>
              
              <div 
                class="upload-zone"
                :class="{ 'drag-over': isDragOver, 'has-files': files.length > 0 }"
                @dragover.prevent="handleDragOver"
                @dragleave.prevent="handleDragLeave"
                @drop.prevent="handleDrop"
                @click="triggerFileInput"
              >
                <input
                  ref="fileInput"
                  type="file"
                  multiple
                  accept=".pdf,.md,.txt"
                  @change="handleFileSelect"
                  style="display: none"
                  :disabled="loading"
                />
                
                <div v-if="files.length === 0" class="upload-placeholder">
                  <div class="upload-icon">↑</div>
                  <div class="upload-title">{{ $t('home.dragToUpload') }}</div>
                  <div class="upload-hint">{{ $t('home.orBrowse') }}</div>
                </div>
                
                <div v-else class="file-list">
                  <div v-for="(file, index) in files" :key="index" class="file-item">
                    <span class="file-icon">📄</span>
                    <span class="file-name">{{ file.name }}</span>
                    <button @click.stop="removeFile(index)" class="remove-btn">×</button>
                  </div>
                </div>
              </div>
            </div>

            <!-- 分割线 -->
            <div class="console-divider">
              <span>{{ $t('home.inputParams') }}</span>
            </div>

            <!-- 输入区域 -->
            <div class="console-section">
              <div class="console-header">
                <span class="console-label">{{ $t('home.simulationPrompt') }}</span>
              </div>
              <div class="input-wrapper">
                <textarea
                  v-model="formData.simulationRequirement"
                  class="code-input"
                  :placeholder="$t('home.promptPlaceholder')"
                  rows="6"
                  :disabled="loading"
                ></textarea>
                <div class="model-badge">{{ $t('home.engineBadge') }}</div>
              </div>
            </div>

            <!-- 启动按钮 -->
            <div class="console-section btn-section">
              <button 
                class="start-engine-btn"
                @click="startSimulation"
                :disabled="!canSubmit || loading"
              >
                <span v-if="!loading">{{ $t('home.startEngine') }}</span>
                <span v-else>{{ $t('home.initializing') }}</span>
                <span class="btn-arrow">→</span>
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- 历史项目数据库 -->
      <HistoryDatabase class="home-history" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import HistoryDatabase from '../components/HistoryDatabase.vue'
import AppHeader from '../components/AppHeader.vue'
import HivemindMark from '../components/HivemindMark.vue'

const router = useRouter()

// 表单数据
const formData = ref({
  simulationRequirement: ''
})

// 文件列表
const files = ref([])

// 状态
const loading = ref(false)
const error = ref('')
const isDragOver = ref(false)

// 文件输入引用
const fileInput = ref(null)

// 计算属性:是否可以提交
const canSubmit = computed(() => {
  return formData.value.simulationRequirement.trim() !== '' && files.value.length > 0
})

// 触发文件选择
const triggerFileInput = () => {
  if (!loading.value) {
    fileInput.value?.click()
  }
}

// 处理文件选择
const handleFileSelect = (event) => {
  const selectedFiles = Array.from(event.target.files)
  addFiles(selectedFiles)
}

// 处理拖拽相关
const handleDragOver = (e) => {
  if (!loading.value) {
    isDragOver.value = true
  }
}

const handleDragLeave = (e) => {
  isDragOver.value = false
}

const handleDrop = (e) => {
  isDragOver.value = false
  if (loading.value) return
  
  const droppedFiles = Array.from(e.dataTransfer.files)
  addFiles(droppedFiles)
}

// 添加文件
const addFiles = (newFiles) => {
  const validFiles = newFiles.filter(file => {
    const ext = file.name.split('.').pop().toLowerCase()
    return ['pdf', 'md', 'txt'].includes(ext)
  })
  files.value.push(...validFiles)
}

// 移除文件
const removeFile = (index) => {
  files.value.splice(index, 1)
}

// 滚动到底部
const scrollToBottom = () => {
  window.scrollTo({
    top: document.body.scrollHeight,
    behavior: 'smooth'
  })
}

// 开始模拟 - 立即跳转，API调用在Process页面进行
const startSimulation = () => {
  if (!canSubmit.value || loading.value) return
  
  // 存储待上传的数据
  import('../store/pendingUpload.js').then(({ setPendingUpload }) => {
    setPendingUpload(files.value, formData.value.simulationRequirement)
    
    // 立即跳转到Process页面（使用特殊标识表示新建项目）
    router.push({
      name: 'Process',
      params: { projectId: 'new' }
    })
  })
}
</script>

<style scoped>
/*
 * Home: a landing and upload screen on Paper.
 * The two <section>s use display: contents so .main-content can place the
 * intro, the upload console and the workflow on one grid without moving markup.
 */
.home-container {
  min-height: 100vh;
  background: var(--hm-paper);
  color: var(--hm-ink);
  font-family: var(--hm-font-sans);
}

.main-content {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(400px, 480px);
  grid-template-areas:
    "intro   console"
    "steps   console"
    "history history";
  column-gap: var(--hm-space-16);
  max-width: var(--hm-content-max);
  margin: 0 auto;
  padding: var(--hm-space-12) var(--hm-space-10) var(--hm-space-16);
}

.hero-section,
.dashboard-section {
  display: contents;
}

/* ------------------------------------------------------------ intro */
.hero-left {
  grid-area: intro;
  position: relative;
  z-index: 1;
  padding-bottom: var(--hm-space-12);
}

.tag-row {
  display: flex;
  align-items: center;
  gap: var(--hm-space-3);
  margin-bottom: var(--hm-space-8);
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-2xs);
  letter-spacing: var(--hm-tracking-label);
  text-transform: uppercase;
}

.orange-tag {
  display: inline-flex;
  align-items: center;
  gap: var(--hm-space-2);
  color: var(--hm-ink);
  font-weight: 500;
}

.orange-tag::before {
  content: "";
  width: 9px;
  height: 10px;
  background: var(--hm-signal);
  clip-path: polygon(50% 0, 100% 25%, 100% 75%, 50% 100%, 0 75%, 0 25%);
}

.version-text {
  color: var(--hm-ink-4);
}

.main-title {
  margin: 0 0 var(--hm-space-6);
  font-family: var(--hm-font-display);
  font-size: var(--hm-text-4xl);
  font-weight: 500;
  line-height: var(--hm-leading-tight);
  letter-spacing: -0.035em;
  color: var(--hm-ink);
}

.gradient-text {
  color: var(--hm-ink-4);
}

.hero-desc {
  max-width: 460px;
}

.hero-desc p {
  font-size: var(--hm-text-lg);
  line-height: 1.5;
  letter-spacing: var(--hm-tracking-display);
  color: var(--hm-ink-3);
}

.highlight-bold,
.highlight-orange {
  color: var(--hm-ink);
  font-weight: 500;
}

.highlight-code {
  color: var(--hm-ink);
  font-weight: 500;
}

.hero-desc .slogan-text {
  display: inline-flex;
  align-items: baseline;
  margin-top: var(--hm-space-8);
  padding-top: var(--hm-space-4);
  border-top: 1px solid var(--hm-line);
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-xs);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--hm-ink-2);
}

.blinking-cursor {
  margin-left: 2px;
  color: var(--hm-signal);
  font-weight: 700;
  animation: hm-blink 1.1s step-end infinite;
}

@keyframes hm-blink {
  50% { opacity: 0; }
}

.decoration-square {
  display: none;
}

/* The mark sits beside the lede, under the full-width headline. */
.hero-right {
  grid-area: intro;
  justify-self: end;
  align-self: end;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--hm-space-5);
  margin-bottom: var(--hm-space-12);
}

.logo-container {
  display: grid;
  place-items: center;
  width: 136px;
  height: 136px;
}

.scroll-down-btn {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border: 1px solid var(--hm-line-strong);
  border-radius: 50%;
  background: transparent;
  color: var(--hm-ink-3);
  font-size: var(--hm-text-sm);
  cursor: pointer;
  transition: border-color var(--hm-duration-fast) var(--hm-ease), color var(--hm-duration-fast) var(--hm-ease);
}

.scroll-down-btn:hover {
  border-color: var(--hm-ink);
  color: var(--hm-ink);
}

/* ------------------------------------------------- status and workflow */
.left-panel {
  grid-area: steps;
  display: flex;
  flex-direction: column;
  padding-top: var(--hm-space-8);
  border-top: 1px solid var(--hm-line);
}

.panel-header {
  display: flex;
  align-items: center;
  gap: var(--hm-space-2);
  margin-bottom: var(--hm-space-3);
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-2xs);
  letter-spacing: var(--hm-tracking-label);
  text-transform: uppercase;
  color: var(--hm-ink-4);
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--hm-success-dot);
  box-shadow: 0 0 0 3px var(--hm-success-soft);
}

.section-title {
  margin: 0 0 var(--hm-space-2);
  font-size: var(--hm-text-2xl);
  font-weight: 500;
  letter-spacing: var(--hm-tracking-display);
}

.section-desc {
  max-width: 520px;
  margin-bottom: var(--hm-space-8);
  font-size: var(--hm-text-md);
  line-height: 1.55;
  color: var(--hm-ink-3);
}

.metrics-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin-bottom: var(--hm-space-10);
  border-top: 1px solid var(--hm-line);
  border-bottom: 1px solid var(--hm-line);
}

.metric-card {
  padding: var(--hm-space-5) 0;
}

.metric-card + .metric-card {
  padding-left: var(--hm-space-6);
  border-left: 1px solid var(--hm-line);
}

.metric-value {
  margin-bottom: var(--hm-space-1);
  font-size: var(--hm-text-xl);
  font-weight: 500;
  letter-spacing: var(--hm-tracking-display);
  color: var(--hm-ink);
}

.metric-label {
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-2xs);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--hm-ink-4);
}

.steps-header {
  display: flex;
  align-items: center;
  gap: var(--hm-space-2);
  margin-bottom: var(--hm-space-2);
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-2xs);
  letter-spacing: var(--hm-tracking-label);
  text-transform: uppercase;
  color: var(--hm-ink-4);
}

.diamond-icon {
  width: 9px;
  height: 10px;
  background: var(--hm-ink);
  clip-path: polygon(50% 0, 100% 25%, 100% 75%, 50% 100%, 0 75%, 0 25%);
}

.workflow-list {
  display: flex;
  flex-direction: column;
}

.workflow-item {
  display: grid;
  grid-template-columns: 40px minmax(0, 1fr);
  gap: var(--hm-space-3);
  padding: var(--hm-space-4) 0;
  border-bottom: 1px solid var(--hm-line);
}

.step-num {
  padding-top: 2px;
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-xs);
  color: var(--hm-ink-4);
}

.step-title {
  margin-bottom: 2px;
  font-size: var(--hm-text-md);
  font-weight: 500;
  color: var(--hm-ink);
}

.step-desc {
  font-size: var(--hm-text-sm);
  line-height: 1.5;
  color: var(--hm-ink-4);
}

/* ---------------------------------------------------- upload console */
.right-panel {
  grid-area: console;
  align-self: start;
  position: sticky;
  top: calc(var(--hm-header-h) + var(--hm-space-6));
}

.console-box {
  background: var(--hm-surface);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-lg);
  box-shadow: var(--hm-shadow-sm);
  padding: var(--hm-space-2) 0;
}

.console-section {
  padding: var(--hm-space-5) var(--hm-space-6);
}

.console-section.btn-section {
  padding-top: var(--hm-space-2);
  padding-bottom: var(--hm-space-5);
}

.console-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: var(--hm-space-3);
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-2xs);
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.console-label {
  color: var(--hm-ink);
  font-weight: 500;
}

.console-meta {
  color: var(--hm-ink-4);
}

.upload-zone {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 184px;
  overflow-y: auto;
  border: 1.5px dashed var(--hm-line-strong);
  border-radius: var(--hm-radius-md);
  background: var(--hm-surface-2);
  cursor: pointer;
  transition: border-color var(--hm-duration) var(--hm-ease), background-color var(--hm-duration) var(--hm-ease);
}

.upload-zone:hover {
  border-color: var(--hm-ink-5);
  background: var(--hm-paper);
}

.upload-zone.drag-over {
  border-color: var(--hm-signal);
  background: var(--hm-signal-soft);
}

.upload-zone.has-files {
  align-items: flex-start;
  border-style: solid;
  background: var(--hm-surface);
}

.upload-placeholder {
  text-align: center;
}

.upload-icon {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  margin: 0 auto var(--hm-space-3);
  border-radius: 50%;
  background: var(--hm-surface);
  border: 1px solid var(--hm-line-strong);
  color: var(--hm-ink);
  font-size: var(--hm-text-md);
}

.upload-title {
  margin-bottom: var(--hm-space-1);
  font-size: var(--hm-text-md);
  font-weight: 500;
  color: var(--hm-ink);
}

.upload-hint {
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-2xs);
  letter-spacing: 0.06em;
  color: var(--hm-ink-4);
}

.file-list {
  display: flex;
  flex-direction: column;
  gap: var(--hm-space-2);
  width: 100%;
  padding: var(--hm-space-3);
}

.file-item {
  display: flex;
  align-items: center;
  gap: var(--hm-space-2);
  padding: var(--hm-space-2) var(--hm-space-3);
  background: var(--hm-surface-2);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-sm);
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-xs);
  color: var(--hm-ink-2);
}

/* Replaces the emoji glyph with a document outline, without touching the markup. */
.file-icon {
  width: 12px;
  height: 14px;
  font-size: 0;
  border: 1.5px solid var(--hm-ink-4);
  border-radius: 2px;
  flex-shrink: 0;
}

.file-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.remove-btn {
  display: grid;
  place-items: center;
  width: 22px;
  height: 22px;
  border: none;
  border-radius: var(--hm-radius-xs);
  background: transparent;
  color: var(--hm-ink-4);
  font-size: var(--hm-text-md);
  line-height: 1;
  cursor: pointer;
}

.remove-btn:hover {
  background: var(--hm-surface-3);
  color: var(--hm-ink);
}

.console-divider {
  display: flex;
  align-items: center;
  gap: var(--hm-space-3);
  margin: 0 var(--hm-space-6);
}

.console-divider::before,
.console-divider::after {
  content: "";
  flex: 1;
  height: 1px;
  background: var(--hm-line);
}

.console-divider span {
  font-family: var(--hm-font-mono);
  font-size: 10px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--hm-ink-4);
}

.input-wrapper {
  position: relative;
  border: 1px solid var(--hm-line-strong);
  border-radius: var(--hm-radius-md);
  background: var(--hm-surface);
  transition: border-color var(--hm-duration-fast) var(--hm-ease), box-shadow var(--hm-duration-fast) var(--hm-ease);
}

.input-wrapper:focus-within {
  border-color: var(--hm-signal);
  box-shadow: 0 0 0 3px var(--hm-signal-soft);
}

.code-input {
  display: block;
  width: 100%;
  min-height: 148px;
  padding: var(--hm-space-4) var(--hm-space-4) var(--hm-space-8);
  border: none;
  background: transparent;
  font-family: var(--hm-font-sans);
  font-size: var(--hm-text-base);
  line-height: 1.6;
  color: var(--hm-ink);
  resize: vertical;
  outline: none;
}

.model-badge {
  position: absolute;
  right: var(--hm-space-3);
  bottom: var(--hm-space-2);
  font-family: var(--hm-font-mono);
  font-size: 10px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--hm-ink-5);
  pointer-events: none;
}

.start-engine-btn {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  height: 52px;
  padding: 0 var(--hm-space-5);
  border: none;
  border-radius: var(--hm-radius-sm);
  background: var(--hm-signal);
  color: var(--hm-ink);
  font-family: var(--hm-font-sans);
  font-size: var(--hm-text-md);
  font-weight: 600;
  cursor: pointer;
  transition: background-color var(--hm-duration-fast) var(--hm-ease);
}

.start-engine-btn:hover:not(:disabled) {
  background: var(--hm-signal-hover);
}

.start-engine-btn:disabled {
  background: var(--hm-surface-3);
  color: var(--hm-ink-4);
  cursor: not-allowed;
}

.btn-arrow {
  font-size: var(--hm-text-lg);
  transition: transform var(--hm-duration) var(--hm-ease);
}

.start-engine-btn:hover:not(:disabled) .btn-arrow {
  transform: translateX(3px);
}

/* -------------------------------------------------------- history */
.home-history {
  grid-area: history;
  margin-top: var(--hm-space-16);
}

/* ------------------------------------------------------ responsive */
@media (max-width: 1100px) {
  .main-content {
    grid-template-columns: minmax(0, 1fr);
    grid-template-areas:
      "intro"
      "console"
      "steps"
      "history";
    padding: var(--hm-space-8) var(--hm-space-6) var(--hm-space-12);
  }

  .hero-left {
    padding-right: 0;
    padding-bottom: var(--hm-space-8);
  }

  .hero-right {
    display: none;
  }

  .right-panel {
    position: static;
    margin-bottom: var(--hm-space-10);
  }
}

@media (max-width: 640px) {
  .main-content {
    padding: var(--hm-space-6) var(--hm-space-4) var(--hm-space-10);
  }

  .main-title {
    font-size: 40px;
  }

  .hero-desc p {
    font-size: var(--hm-text-md);
  }

  .console-section {
    padding: var(--hm-space-4);
  }

  .console-divider {
    margin: 0 var(--hm-space-4);
  }
}
</style>

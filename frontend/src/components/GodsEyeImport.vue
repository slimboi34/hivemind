<template>
  <details class="godseye-import" @toggle="onToggle">
    <summary class="godseye-summary">{{ t('godseye.title') }}</summary>

    <div class="godseye-body">
      <p class="godseye-hint">{{ t('godseye.hint') }}</p>

      <div v-if="state === 'checking'" class="godseye-status">{{ t('godseye.checking') }}</div>

      <div v-else-if="state === 'offline'" class="godseye-offline" role="status">
        <div class="godseye-offline-title">{{ t('godseye.notRunningTitle') }}</div>
        <div>{{ t('godseye.notRunningHelp', { url: serverUrl }) }}</div>
        <div v-if="offlineDetail" class="godseye-detail">{{ offlineDetail }}</div>
        <button type="button" class="godseye-btn" @click="checkStatus">{{ t('godseye.checkAgain') }}</button>
      </div>

      <template v-else-if="state === 'ready'">
        <div class="godseye-status">{{ t('godseye.connected', { version: serverVersion }) }}</div>

        <form class="godseye-form" @submit.prevent="fetchBrief">
          <input
            v-model="area"
            class="godseye-input"
            type="text"
            maxlength="200"
            :placeholder="t('godseye.placeholder')"
            :disabled="fetching"
          />
          <button type="submit" class="godseye-btn" :disabled="!area.trim() || !selected.length || fetching">
            {{ fetching ? t('godseye.fetching') : t('godseye.preview') }}
          </button>
        </form>

        <div class="godseye-sections">
          <label v-for="key in sectionKeys" :key="key">
            <input v-model="selected" type="checkbox" :value="key" :disabled="fetching" />
            {{ t(`godseye.sections.${key}`) }}
          </label>
        </div>

        <div v-if="error" class="godseye-error" role="alert">{{ error }}</div>

        <div v-if="brief" class="godseye-preview">
          <div class="godseye-preview-name">{{ brief.filename }}</div>
          <div v-if="missingSections.length" class="godseye-detail">
            {{ t('godseye.noData', { sections: missingSections.join(', ') }) }}
          </div>
          <pre class="godseye-markdown">{{ brief.markdown }}</pre>
          <div class="godseye-actions">
            <button type="button" class="godseye-btn godseye-btn-primary" @click="addToUploads">
              {{ t('godseye.addToUploads') }}
            </button>
            <button type="button" class="godseye-btn" @click="brief = null">{{ t('godseye.discard') }}</button>
          </div>
        </div>

        <div v-if="addedName" class="godseye-status">{{ t('godseye.added', { name: addedName }) }}</div>
      </template>

      <p class="godseye-note">{{ t('godseye.scopeNote') }} {{ t('godseye.termsNote') }}</p>
    </div>
  </details>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { getGodsEyeBrief, getGodsEyeStatus } from '../api/godseye'

const emit = defineEmits(['add-file'])
const { t } = useI18n()

const sectionKeys = ['headlines', 'hazards', 'weather', 'air', 'sea']

const state = ref('idle') // idle | checking | offline | ready
const serverUrl = ref('http://localhost:4173')
const serverVersion = ref('')
const offlineDetail = ref('')
const area = ref('')
const selected = ref([...sectionKeys])
const fetching = ref(false)
const error = ref('')
const brief = ref(null)
const addedName = ref('')

const missingSections = computed(() => {
  const sections = brief.value?.sections || {}
  return sectionKeys
    .filter(key => sections[key]?.status === 'unavailable')
    .map(key => t(`godseye.sections.${key}`))
})

const onToggle = (event) => {
  if (event.target.open && state.value === 'idle') checkStatus()
}

const checkStatus = async () => {
  state.value = 'checking'
  offlineDetail.value = ''
  error.value = ''
  try {
    const res = await getGodsEyeStatus()
    const data = res.data || {}
    serverUrl.value = data.url || serverUrl.value
    if (data.reachable) {
      serverVersion.value = data.version || ''
      state.value = 'ready'
    } else {
      state.value = 'offline'
    }
  } catch (err) {
    // Hivemind's own backend did not answer.
    offlineDetail.value = err.message || ''
    state.value = 'offline'
  }
}

const fetchBrief = async () => {
  if (!area.value.trim() || fetching.value) return
  fetching.value = true
  error.value = ''
  addedName.value = ''
  brief.value = null
  try {
    const res = await getGodsEyeBrief({ area: area.value.trim(), sections: selected.value })
    brief.value = res.data
  } catch (err) {
    if (err.response?.status === 503) {
      state.value = 'offline'
    }
    error.value = err.message || String(err)
  } finally {
    fetching.value = false
  }
}

const addToUploads = () => {
  if (!brief.value) return
  const file = new File([brief.value.markdown], brief.value.filename, { type: 'text/markdown' })
  emit('add-file', file)
  addedName.value = brief.value.filename
  brief.value = null
}
</script>

<style scoped>
.godseye-import {
  margin-top: 12px;
  border: 1px solid #ddd;
  font-size: 0.85rem;
}

.godseye-summary {
  cursor: pointer;
  padding: 8px 12px;
  font-weight: 600;
  user-select: none;
}

.godseye-body {
  padding: 0 12px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.godseye-hint,
.godseye-note {
  margin: 0;
  color: #666;
}

.godseye-note {
  font-size: 0.75rem;
}

.godseye-status,
.godseye-detail {
  color: #666;
}

.godseye-offline {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px;
  border-left: 3px solid #c77700;
  background: #fff8ec;
}

.godseye-offline-title {
  font-weight: 600;
}

.godseye-form {
  display: flex;
  gap: 8px;
}

.godseye-input {
  flex: 1;
  min-width: 0;
  padding: 6px 8px;
  border: 1px solid #ccc;
  font: inherit;
}

.godseye-sections {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
}

.godseye-btn {
  align-self: flex-start;
  padding: 6px 12px;
  border: 1px solid #333;
  background: #fff;
  font: inherit;
  cursor: pointer;
}

.godseye-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.godseye-btn-primary {
  background: #000;
  color: #fff;
}

.godseye-error {
  color: #b00020;
}

.godseye-preview {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.godseye-preview-name {
  font-family: monospace;
}

.godseye-markdown {
  max-height: 260px;
  overflow: auto;
  margin: 0;
  padding: 8px;
  background: #f7f7f7;
  border: 1px solid #e5e5e5;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 0.75rem;
}

.godseye-actions {
  display: flex;
  gap: 8px;
}
</style>

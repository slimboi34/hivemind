<template>
  <div class="language-switcher" ref="switcherRef">
    <button class="switcher-trigger" :aria-expanded="open" aria-haspopup="listbox" @click="toggleDropdown">
      <svg class="globe" viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><circle cx="8" cy="8" r="6.25" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M1.75 8h12.5M8 1.75c1.7 1.8 2.5 3.9 2.5 6.25S9.7 12.45 8 14.25M8 1.75C6.3 3.55 5.5 5.65 5.5 8s.8 4.45 2.5 6.25" fill="none" stroke="currentColor" stroke-width="1.3"/></svg>
      {{ currentLabel }}
      <svg class="caret" :class="{ open }" viewBox="0 0 10 10" width="10" height="10" aria-hidden="true"><path d="M2 3.75 5 6.75l3-3" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>
    </button>
    <ul v-if="open" class="switcher-dropdown" role="listbox">
      <li
        v-for="loc in availableLocales"
        :key="loc.key"
        class="switcher-option"
        :class="{ active: loc.key === locale }"
        role="option"
        :aria-selected="loc.key === locale"
        @click="switchLocale(loc.key)"
      >
        {{ loc.label }}
      </li>
    </ul>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { availableLocales } from '@/i18n/index.js'

const { locale } = useI18n()
const open = ref(false)
const switcherRef = ref(null)

const currentLabel = computed(() => {
  const found = availableLocales.find(l => l.key === locale.value)
  return found ? found.label : locale.value
})

const toggleDropdown = () => {
  open.value = !open.value
}

const switchLocale = (key) => {
  locale.value = key
  localStorage.setItem('locale', key)
  document.documentElement.lang = key
  open.value = false
}

const onClickOutside = (e) => {
  if (switcherRef.value && !switcherRef.value.contains(e.target)) {
    open.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', onClickOutside)
  document.documentElement.lang = locale.value
})

onUnmounted(() => {
  document.removeEventListener('click', onClickOutside)
})
</script>

<style scoped>
/* Lives in the Ink nav bar: mono, uppercase, letter-spaced. */
.language-switcher {
  position: relative;
  display: inline-block;
}

.switcher-trigger {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 30px;
  padding: 0 10px;
  background: transparent;
  color: var(--hm-nav-text);
  border: 1px solid var(--hm-console-line);
  border-radius: var(--hm-radius-sm);
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-2xs);
  font-weight: 500;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  cursor: pointer;
  transition: border-color var(--hm-duration-fast) var(--hm-ease), color var(--hm-duration-fast) var(--hm-ease);
}

.switcher-trigger:hover {
  border-color: #4A4438;
  color: var(--hm-paper);
}

.switcher-trigger:focus-visible {
  outline-color: var(--hm-on-ink);
}

.globe,
.caret {
  color: currentColor;
  opacity: 0.8;
}

.caret {
  transition: transform var(--hm-duration-fast) var(--hm-ease);
}

.caret.open {
  transform: rotate(180deg);
}

.switcher-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  min-width: 100%;
  padding: 4px;
  list-style: none;
  background: var(--hm-surface);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-md);
  box-shadow: var(--hm-shadow-md);
  z-index: 1000;
}

.switcher-option {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border-radius: var(--hm-radius-xs);
  font-size: var(--hm-text-sm);
  color: var(--hm-ink-2);
  white-space: nowrap;
  cursor: pointer;
  transition: background-color var(--hm-duration-fast) var(--hm-ease);
}

.switcher-option:hover {
  background: var(--hm-surface-3);
}

.switcher-option.active {
  color: var(--hm-ink);
  font-weight: 600;
}

.switcher-option.active::after {
  content: "";
  width: 6px;
  height: 6px;
  margin-left: auto;
  border-radius: 50%;
  background: var(--hm-signal);
}
</style>

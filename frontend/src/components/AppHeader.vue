<template>
  <header class="hm-nav">
    <div class="hm-nav__left">
      <router-link to="/" class="hm-nav__brand" aria-label="Hivemind home">
        <img :src="markOnDark" width="22" height="22" alt="" />
        <span>HIVEMIND</span>
      </router-link>

      <template v-if="step || $slots.context">
        <span class="hm-nav__rule" aria-hidden="true"></span>
        <div v-if="step" class="hm-steps">
          <ol class="hm-steps__track" :aria-label="`Step ${step} of ${total}`">
            <li
              v-for="n in total"
              :key="n"
              class="hm-steps__cell"
              :class="{ done: n < step, current: n === step }"
              :aria-current="n === step ? 'step' : undefined"
            ></li>
          </ol>
          <span class="hm-steps__count">{{ step }}/{{ total }}</span>
          <span class="hm-steps__name">{{ stepName }}</span>
        </div>
        <div v-if="$slots.context" class="hm-nav__context">
          <slot name="context" />
        </div>
      </template>
    </div>

    <div class="hm-nav__center">
      <slot name="center" />
    </div>

    <div class="hm-nav__right">
      <slot />
      <LanguageSwitcher />
      <a class="hm-nav__link" :href="sourceUrl" target="_blank" rel="noopener">{{ $t('nav.visitGithub') }}</a>
    </div>
  </header>
</template>

<script setup>
import LanguageSwitcher from './LanguageSwitcher.vue'
import markOnDark from '../assets/brand/mark-on-dark.svg'

// Hivemind's own source (AGPL-3.0: users of a hosted instance are offered the source).
const sourceUrl = 'https://github.com/slimboi34/hivemind'

defineProps({
  step: { type: Number, default: 0 },
  total: { type: Number, default: 5 },
  stepName: { type: String, default: '' }
})
</script>

<style scoped>
/* The product nav from brand/board.html: a full-width Ink bar. */
.hm-nav {
  position: sticky;
  top: 0;
  z-index: 100;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  gap: var(--hm-space-4);
  height: var(--hm-header-h);
  flex-shrink: 0;
  padding: 0 28px;
  background: var(--hm-ink);
  color: var(--hm-paper);
}

.hm-nav__left,
.hm-nav__right {
  display: flex;
  align-items: center;
  gap: var(--hm-space-3);
  min-width: 0;
}

.hm-nav__right {
  justify-content: flex-end;
}

.hm-nav__center {
  display: flex;
  justify-content: center;
}

.hm-nav__brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--hm-paper);
  text-decoration: none;
  font-family: var(--hm-font-mono);
  font-weight: 700;
  font-size: 15px;
  letter-spacing: 0.14em;
  border-radius: var(--hm-radius-xs);
  white-space: nowrap;
}

.hm-nav__brand img {
  display: block;
  width: 22px;
  height: 22px;
}

.hm-nav__rule {
  width: 1px;
  height: 20px;
  margin: 0 var(--hm-space-2);
  background: var(--hm-console-line);
}

.hm-nav__context {
  display: flex;
  align-items: center;
  gap: var(--hm-space-3);
  min-width: 0;
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-xs);
  letter-spacing: 0.08em;
  color: var(--hm-nav-text);
}

.hm-nav__link {
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-xs);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--hm-nav-text);
  text-decoration: none;
  white-space: nowrap;
  margin-left: var(--hm-space-2);
  transition: color var(--hm-duration-fast) var(--hm-ease);
}

.hm-nav__link:hover {
  color: var(--hm-paper);
}

/* Step track: one hex cell per stage, amber for the current one */
.hm-steps {
  display: flex;
  align-items: center;
  gap: var(--hm-space-2);
  min-width: 0;
}

.hm-steps__track {
  display: flex;
  gap: 3px;
  list-style: none;
}

.hm-steps__cell {
  width: 9px;
  height: 10px;
  background: #3D382F;
  clip-path: polygon(50% 0, 100% 25%, 100% 75%, 50% 100%, 0 75%, 0 25%);
}

.hm-steps__cell.done {
  background: var(--hm-paper);
}

.hm-steps__cell.current {
  background: var(--hm-on-ink);
}

.hm-steps__count {
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-2xs);
  color: var(--hm-nav-text);
}

.hm-steps__name {
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-2xs);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--hm-paper);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

@media (max-width: 1180px) {
  .hm-steps__name {
    display: none;
  }
}

@media (max-width: 720px) {
  .hm-nav {
    grid-template-columns: auto 1fr;
    padding: 0 var(--hm-space-4);
  }

  .hm-nav__center,
  .hm-nav__rule,
  .hm-steps,
  .hm-nav__context {
    display: none;
  }
}
</style>

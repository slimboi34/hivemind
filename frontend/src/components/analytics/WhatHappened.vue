<template>
  <section class="card recap" aria-labelledby="recap-title">
    <header class="card-head">
      <div>
        <h3 id="recap-title">{{ $t('analytics.recapTitle') }}</h3>
        <p class="sub">{{ $t('analytics.recapSubtitle') }}</p>
      </div>
      <div class="head-actions">
        <span class="source" :class="sourceClass">
          <span class="source-dot"></span>{{ sourceText }}
        </span>
        <button
          v-if="finished && recap?.can_write"
          class="ghost-btn"
          :disabled="writing"
          @click="emit('write', true)"
        >{{ $t('analytics.recapRewrite') }}</button>
      </div>
    </header>

    <p v-if="writeError" class="write-error">{{ $t('analytics.recapWriteFailed', { error: writeError }) }}</p>

    <p v-if="!chapters.length" class="empty">{{ $t('analytics.recapEmpty') }}</p>

    <template v-else>
      <p class="headline" :class="{ fading: writing }">{{ story.headline }}</p>
      <p class="summary" :class="{ fading: writing }">{{ story.summary }}</p>

      <!-- The arc: one column per stretch, height = everything that happened, split by kind. -->
      <figure class="arc" :aria-label="$t('analytics.recapArcLabel')">
        <div class="arc-cols">
          <button
            v-for="ch in chapters"
            :key="ch.index"
            class="arc-col"
            :title="arcTitle(ch)"
            @click="jump(ch.index)"
          >
            <span class="arc-total">{{ fmt(ch.activity) }}</span>
            <span class="arc-bar" :style="{ height: barHeight(ch) }">
              <span
                v-for="seg in SEGMENTS"
                v-show="ch[seg.key] > 0"
                :key="seg.key"
                class="arc-seg"
                :style="{ flexGrow: ch[seg.key], background: CATEGORY_COLOR[seg.cat] }"
              ></span>
            </span>
            <span class="arc-label">{{ shortTime(ch) }}</span>
          </button>
        </div>
        <figcaption class="legend">
          <span v-for="seg in SEGMENTS" :key="seg.key">
            <span class="sw" :style="{ background: CATEGORY_COLOR[seg.cat] }"></span>{{ $t(`analytics.recap_${seg.key}`) }}
          </span>
        </figcaption>
      </figure>

      <div v-if="story.opening" class="block opening">
        <h4>{{ $t('analytics.recapOpening') }}</h4>
        <p>{{ story.opening }}</p>
        <div v-if="seedAuthors.length" class="chips">
          <button v-for="name in seedAuthors.slice(0, SEED_CHIPS)" :key="name" class="chip" @click="emit('update:selected', name)">{{ name }}</button>
          <span v-if="seedAuthors.length > SEED_CHIPS" class="chip more">+{{ seedAuthors.length - SEED_CHIPS }}</span>
        </div>
      </div>

      <ol class="timeline">
        <li v-for="item in storyChapters" :id="`recap-ch-${item.index}`" :key="item.index" :class="{ quiet: factsFor(item).quiet }">
          <span class="rail" aria-hidden="true"><span class="node"></span></span>
          <div class="ch-body">
            <div class="when">
              <span>{{ factsFor(item).time }}</span>
              <span class="rounds">{{ factsFor(item).label }}</span>
            </div>
            <h4>{{ item.title }}</h4>
            <p class="story" :class="{ fading: writing }">{{ item.story }}</p>
            <div class="stats">
              <span>{{ $t('analytics.recapStatPosts', { n: fmt(factsFor(item).posts) }) }}</span>
              <span>{{ $t('analytics.recapStatReplies', { n: fmt(factsFor(item).replies) }) }}</span>
              <span>{{ $t('analytics.recapStatReactions', { n: fmt(factsFor(item).approving + factsFor(item).disapproving) }) }}</span>
              <span v-if="factsFor(item).tone !== null" class="tone">
                <span class="tone-bar"><span :style="{ width: pct(factsFor(item).tone) }"></span></span>
                {{ $t('analytics.recapStatApproving', { pct: pct(factsFor(item).tone) }) }}
              </span>
              <span>{{ $t('analytics.recapStatPeople', { n: fmt(factsFor(item).people_active) }) }}</span>
            </div>

            <blockquote v-if="lead(item)" class="quote">
              <p :class="{ open: openQuote === item.index }" @click="openQuote = openQuote === item.index ? null : item.index">{{ lead(item).text }}</p>
              <footer>
                <button class="author" @click="emit('update:selected', lead(item).author)">{{ lead(item).author }}</button>
                <span>· {{ $t(`analytics.platforms.${lead(item).platform}`) }}</span>
                <span>· {{ $t('analytics.recapReactionsInStretch', { n: lead(item).reactions_in_chapter }) }}</span>
              </footer>
            </blockquote>

            <div v-if="factsFor(item).new_voices?.length" class="voices">
              <span class="voices-label">{{ $t('analytics.recapNewVoices', { n: factsFor(item).new_voice_count }) }}</span>
              <button
                v-for="v in factsFor(item).new_voices"
                :key="v.name"
                class="chip"
                @click="emit('update:selected', v.name)"
              >{{ v.name }}</button>
              <span v-if="factsFor(item).new_voice_count > factsFor(item).new_voices.length" class="chip more">
                +{{ factsFor(item).new_voice_count - factsFor(item).new_voices.length }}
              </span>
            </div>
          </div>
        </li>
      </ol>

      <div class="block ending">
        <h4>{{ $t('analytics.recapEnding') }}</h4>
        <p :class="{ fading: writing }">{{ story.ending }}</p>
        <ul v-if="story.takeaways?.length" class="takeaways">
          <li v-for="(t, i) in story.takeaways" :key="i">{{ t }}</li>
        </ul>
      </div>

      <p class="foot">{{ $t('analytics.recapFoot') }}</p>
    </template>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { CATEGORY_COLOR, fmt, pct } from './palette'

const props = defineProps({
  recap: { type: Object, default: null },
  writing: { type: Boolean, default: false },
  writeError: { type: String, default: '' }
})
const emit = defineEmits(['write', 'update:selected'])
const { t } = useI18n()

// Same colours as the rest of Analytics: posts, replies, approving, disapproving.
const SEGMENTS = [
  { key: 'posts', cat: 'post' },
  { key: 'replies', cat: 'reply' },
  { key: 'approving', cat: 'support' },
  { key: 'disapproving', cat: 'oppose' }
]

const openQuote = ref(null)

const facts = computed(() => props.recap?.facts || {})
const story = computed(() => props.recap?.story || {})
const chapters = computed(() => facts.value.chapters || [])
const SEED_CHIPS = 12
const seedAuthors = computed(() => {
  const o = facts.value.opening || {}
  return o.seed_authors || [...new Set((o.seed_posts || []).map(s => s.author))]
})
const finished = computed(() => !!facts.value.run?.finished)
const byIndex = computed(() => Object.fromEntries(chapters.value.map(c => [c.index, c])))
const storyChapters = computed(() => (story.value.chapters || []).filter(c => byIndex.value[c.index]))
const maxActivity = computed(() => Math.max(1, ...chapters.value.map(c => c.activity || 0)))

const factsFor = (item) => byIndex.value[item.index] || {}
const lead = (item) => factsFor(item).standout_posts?.[0] || null
const BAR_MAX_PX = 92
const barHeight = (ch) => `${ch.activity ? Math.max(4, Math.round((ch.activity / maxActivity.value) * BAR_MAX_PX)) : 0}px`
const shortTime = (ch) => (ch.time || '').replace(/^Day \d+, /, '')
const arcTitle = (ch) => [
  ch.time,
  t('analytics.recapStatPosts', { n: ch.posts }),
  t('analytics.recapStatReplies', { n: ch.replies }),
  `${ch.approving} ${t('analytics.recap_approving').toLowerCase()}`,
  `${ch.disapproving} ${t('analytics.recap_disapproving').toLowerCase()}`
].join(' · ')

const jump = (index) => {
  document.getElementById(`recap-ch-${index}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

const sourceClass = computed(() => {
  if (props.writing) return 'writing'
  return props.recap?.story_source === 'llm' ? 'llm' : finished.value ? 'quick' : 'live'
})
const sourceText = computed(() => {
  if (props.writing) return t('analytics.recapSourceWriting')
  if (props.recap?.story_source === 'llm') return t('analytics.recapSourceLlm')
  return finished.value ? t('analytics.recapSourceQuick') : t('analytics.recapSourceLive')
})
</script>

<style scoped>
.recap { border-left: 4px solid var(--hm-ink); }
.head-actions { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
.source {
  display: inline-flex; align-items: center; gap: 6px; font-family: var(--hm-font-mono); font-size: var(--hm-text-2xs);
  letter-spacing: 0.06em; text-transform: uppercase; color: var(--hm-ink-3); padding: 4px 10px;
  border-radius: var(--hm-radius-pill); background: var(--hm-surface-3);
}
.source-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--hm-ink-5); }
.source.llm .source-dot { background: #1baf7a; }
.source.live .source-dot, .source.writing .source-dot { background: #eda100; animation: pulse 1.2s ease-in-out infinite; }
@keyframes pulse { 50% { opacity: 0.3; } }
@media (prefers-reduced-motion: reduce) { .source-dot { animation: none !important; } .fading { transition: none; } }

.write-error { margin: 0 0 12px; padding: 8px 12px; border-radius: var(--hm-radius-md); background: var(--hm-danger-soft); color: var(--hm-danger); font-size: var(--hm-text-sm); }
.empty { margin: 0; font-size: var(--hm-text-sm); color: var(--hm-ink-3); }

.headline {
  margin: 4px 0 10px; font-family: var(--hm-font-display); font-size: var(--hm-text-xl); font-weight: 500;
  letter-spacing: var(--hm-tracking-display); line-height: var(--hm-leading-snug); color: var(--hm-ink); max-width: 62ch;
}
.summary { margin: 0 0 20px; font-size: var(--hm-text-base); line-height: var(--hm-leading-relaxed); color: var(--hm-ink-2); max-width: 75ch; }
.fading { opacity: 0.45; transition: opacity var(--hm-duration) var(--hm-ease); }

/* Arc */
.arc { margin: 0 0 24px; }
.arc-cols { display: flex; align-items: stretch; gap: 8px; height: 132px; border-bottom: 1px solid var(--hm-line); }
.arc-col {
  flex: 1 1 0; min-width: 0; display: flex; flex-direction: column; justify-content: flex-end; align-items: center; gap: 4px;
  background: none; border: none; padding: 0 0 6px; cursor: pointer; font: inherit; border-radius: var(--hm-radius-sm);
}
.arc-col:hover { background: var(--hm-surface-2); }
.arc-col:focus-visible { outline: 2px solid var(--hm-ink); outline-offset: 2px; }
.arc-total { font-size: 11px; font-weight: 600; color: var(--hm-ink); font-variant-numeric: tabular-nums; }
.arc-bar { width: min(56px, 70%); display: flex; flex-direction: column-reverse; gap: 1px; border-radius: 3px 3px 0 0; overflow: hidden; }
.arc-seg { flex-basis: 0; min-height: 2px; }
.arc-label { font-family: var(--hm-font-mono); font-size: 10px; color: var(--hm-ink-4); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%; }
.legend { margin-top: 8px; }

/* Blocks */
.block { margin: 0 0 20px; }
.block h4, .ch-body h4 { margin: 0 0 6px; font-family: var(--hm-font-display); font-size: var(--hm-text-md); font-weight: 500; letter-spacing: -0.01em; color: var(--hm-ink); }
.block p { margin: 0; font-size: var(--hm-text-sm); line-height: var(--hm-leading-relaxed); color: var(--hm-ink-2); max-width: 80ch; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.chip {
  font: inherit; font-size: 11px; padding: 3px 9px; border-radius: var(--hm-radius-pill); background: var(--hm-surface-3);
  border: 1px solid transparent; color: var(--hm-ink); cursor: pointer;
}
.chip:hover { border-color: var(--hm-line-strong); background: var(--hm-surface); }
.chip.more { cursor: default; color: var(--hm-ink-4); }

/* Timeline */
.timeline { list-style: none; margin: 0 0 20px; padding: 0; }
.timeline li { display: grid; grid-template-columns: 22px minmax(0, 1fr); gap: 12px; scroll-margin-top: 80px; }
.rail { position: relative; display: flex; justify-content: center; }
.rail::before { content: ''; position: absolute; top: 0; bottom: 0; width: 2px; background: var(--hm-line); }
.timeline li:first-child .rail::before { top: 8px; }
.timeline li:last-child .rail::before { bottom: auto; height: 8px; }
.node { position: relative; margin-top: 4px; width: 12px; height: 12px; border-radius: 50%; background: var(--hm-surface); border: 2px solid var(--hm-ink); }
.quiet .node { border-color: var(--hm-ink-5); }
.ch-body { padding: 0 0 22px; min-width: 0; }
.when { display: flex; gap: 10px; align-items: baseline; font-family: var(--hm-font-mono); font-size: var(--hm-text-2xs); letter-spacing: 0.04em; color: var(--hm-ink-3); margin-bottom: 4px; }
.when .rounds { color: var(--hm-ink-5); }
.story { margin: 0 0 8px; font-size: var(--hm-text-sm); line-height: var(--hm-leading-relaxed); color: var(--hm-ink-2); max-width: 80ch; }
.stats { display: flex; flex-wrap: wrap; gap: 4px 14px; font-size: 11px; color: var(--hm-ink-4); font-variant-numeric: tabular-nums; margin-bottom: 10px; }
.tone { display: inline-flex; align-items: center; gap: 6px; }
.tone-bar { display: inline-block; width: 44px; height: 6px; border-radius: 3px; background: #eb6834; overflow: hidden; }
.tone-bar span { display: block; height: 100%; background: #2a78d6; }

.quote { margin: 0 0 10px; padding: 8px 12px; border-left: 3px solid var(--hm-line-strong); background: var(--hm-surface-2); border-radius: 0 var(--hm-radius-sm) var(--hm-radius-sm) 0; max-width: 80ch; }
.quote p {
  margin: 0 0 6px; font-size: 13px; line-height: 1.5; color: var(--hm-ink); cursor: pointer;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
}
.quote p.open { display: block; -webkit-line-clamp: unset; }
.quote footer { display: flex; flex-wrap: wrap; gap: 4px; font-size: 11px; color: var(--hm-ink-4); }
.author { background: none; border: none; padding: 0; font: inherit; font-weight: 600; color: var(--hm-ink); cursor: pointer; }
.author:hover { text-decoration: underline; }

.voices { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.voices-label { font-size: 11px; color: var(--hm-ink-4); margin-right: 2px; }

.ending { padding: 14px 16px; background: var(--hm-surface-2); border-radius: var(--hm-radius-md); }
.takeaways { margin: 10px 0 0; padding-left: 18px; font-size: var(--hm-text-sm); line-height: var(--hm-leading-relaxed); color: var(--hm-ink); }
.foot { margin: 0; font-size: 11px; line-height: 1.5; color: var(--hm-ink-4); max-width: 100ch; }

@media (max-width: 700px) {
  .card-head { flex-direction: column; }
  .arc-label { display: none; }
}
</style>

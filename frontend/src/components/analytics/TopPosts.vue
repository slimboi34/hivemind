<template>
  <section class="card">
    <header class="card-head">
      <div>
        <h3>{{ $t('analytics.postsTitle') }}</h3>
        <p class="sub">{{ $t('analytics.postsSubtitle') }}</p>
      </div>
    </header>
    <ol v-if="posts.length" class="posts">
      <li v-for="(p, i) in posts" :key="`${p.platform}-${p.author}-${i}`">
        <div class="meta">
          <button class="author" @click="emit('update:selected', p.author)">{{ p.author }}</button>
          <span class="dot">·</span>
          <span>{{ $t(`analytics.platforms.${p.platform}`) }}</span>
          <span class="dot">·</span>
          <span>{{ $t('analytics.round') }} {{ p.round }}</span>
          <span class="score">{{ fmt(p.engagement) }}</span>
        </div>
        <p class="content" :class="{ open: openIdx === i }" @click="openIdx = openIdx === i ? null : i">{{ p.content }}</p>
        <div class="counts">
          <span v-for="c in COUNTS" v-show="p[c.key] > 0" :key="c.key">
            <span class="sw" :style="{ background: CATEGORY_COLOR[c.cat] }"></span>{{ fmt(p[c.key]) }} {{ $t(`analytics.${c.key}`) }}
          </span>
        </div>
      </li>
    </ol>
    <p v-else class="hint">{{ $t('analytics.noPosts') }}</p>
  </section>
</template>

<script setup>
import { ref } from 'vue'
import { CATEGORY_COLOR, fmt } from './palette'

defineProps({ posts: { type: Array, default: () => [] } })
const emit = defineEmits(['update:selected'])
const openIdx = ref(null)

const COUNTS = [
  { key: 'likes', cat: 'support' },
  { key: 'reposts', cat: 'support' },
  { key: 'quotes', cat: 'support' },
  { key: 'comments', cat: 'reply' },
  { key: 'dislikes', cat: 'oppose' }
]
</script>

<style scoped>
.posts { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; }
.posts li { padding: 12px 0; border-bottom: 1px solid #f2f2f0; }
.posts li:last-child { border-bottom: none; }
.meta { display: flex; align-items: center; gap: 6px; font-size: 11px; color: #898781; }
.author { background: none; border: none; padding: 0; font: inherit; font-size: 12px; font-weight: 600; color: #0b0b0b; cursor: pointer; }
.author:hover { text-decoration: underline; }
.score { margin-left: auto; font-size: 13px; font-weight: 600; color: #0b0b0b; font-variant-numeric: tabular-nums; }
.content {
  margin: 6px 0 8px; font-size: 13px; line-height: 1.5; color: #222; cursor: pointer;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; white-space: pre-wrap;
}
.content.open { -webkit-line-clamp: unset; display: block; }
.counts { display: flex; gap: 12px; flex-wrap: wrap; font-size: 11px; color: #52514e; font-variant-numeric: tabular-nums; }
.counts .sw { margin-right: 4px; }
.hint { color: #898781; font-size: 13px; margin: 0; }
</style>

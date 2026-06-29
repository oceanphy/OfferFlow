<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { marked } from 'marked'
import { fetchReport } from '../api/client'

const route = useRoute()
const report = ref<Record<string, unknown> | null>(null)
const error = ref('')
const loading = ref(true)

onMounted(async () => {
  const id = route.params.id as string
  try {
    report.value = await fetchReport(id)
  } catch (e) {
    error.value = `加载失败: ${(e as Error).message}`
  } finally {
    loading.value = false
  }
})

const reportHtml = computed(() => {
  const data = report.value as Record<string, any> | null
  const md = data?.report?.markdown
  return md ? marked(md) : ''
})
</script>

<template>
  <div class="report-page">
    <div v-if="loading" class="loading">
      <p>加载诊断报告...</p>
    </div>

    <div v-else-if="error" class="error">
      <p>{{ error }}</p>
    </div>

    <div v-else-if="report" class="report-content">
      <div v-html="reportHtml" class="markdown-body"></div>
    </div>
  </div>
</template>

<style scoped>
.report-page {
  max-width: 800px;
  margin: 0 auto;
  padding: 40px 20px;
}

.loading, .error {
  text-align: center;
  padding: 60px;
  color: #718096;
}

.error {
  color: #e53e3e;
}

.markdown-body {
  color: #2d3748;
  line-height: 1.8;
}

.markdown-body :deep(h1) {
  font-size: 2rem;
  color: #1a1a2e;
  border-bottom: 2px solid #e2e8f0;
  padding-bottom: 8px;
  margin-bottom: 24px;
}

.markdown-body :deep(h2) {
  font-size: 1.4rem;
  color: #2d3748;
  margin-top: 32px;
  margin-bottom: 16px;
}

.markdown-body :deep(h3) {
  font-size: 1.1rem;
  color: #4a5568;
  margin-top: 24px;
  margin-bottom: 8px;
}

.markdown-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 16px 0;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid #e2e8f0;
  padding: 10px 14px;
  text-align: left;
}

.markdown-body :deep(th) {
  background: #f7fafc;
  font-weight: 600;
}

.markdown-body :deep(blockquote) {
  border-left: 4px solid #4a6cf7;
  padding: 8px 16px;
  margin: 16px 0;
  background: #f7fafc;
  color: #4a5568;
}

.markdown-body :deep(hr) {
  border: none;
  border-top: 1px solid #e2e8f0;
  margin: 24px 0;
}

.markdown-body :deep(strong) {
  color: #1a1a2e;
}
</style>

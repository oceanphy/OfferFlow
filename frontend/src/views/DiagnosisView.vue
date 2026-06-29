<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { diagnoseTranscript } from '../api/client'

const router = useRouter()
const route = useRoute()

const status = ref('正在连接...')
const progress = ref({ round: 0, total: 0 })
const logs = ref<{ event: string; data: Record<string, unknown> }[]>([])
const reportId = ref('')
const error = ref('')

onMounted(async () => {
  const transcript = (route.query.transcript as string) || ''
  if (!transcript) {
    router.push({ name: 'upload' })
    return
  }

  try {
    for await (const { event, data } of diagnoseTranscript(transcript)) {
      logs.value.push({ event, data })

      switch (event) {
        case 'splitting':
          status.value = data.message as string
          break
        case 'split_complete':
          status.value = `已拆分 ${data.rounds} 个面试回合`
          break
        case 'diagnosing':
          progress.value = {
            round: (data.round as number) || 0,
            total: (data.total as number) || 0,
          }
          status.value = data.message as string
          break
        case 'generating_report':
          status.value = '正在生成诊断报告...'
          break
        case 'complete':
          status.value = '诊断完成'
          break
        case 'result':
          reportId.value = data.report_id as string
          break
        case 'error':
          error.value = (data.error as string) || '诊断失败'
          status.value = '诊断失败'
          break
      }
    }

    if (reportId.value) {
      setTimeout(() => {
        router.push({ name: 'report', params: { id: reportId.value } })
      }, 500)
    }
  } catch (e) {
    error.value = `连接失败: ${(e as Error).message}`
    status.value = '连接失败'
  }
})
</script>

<template>
  <div class="diagnosis-page">
    <h2>诊断进行中</h2>

    <div class="progress-card">
      <div class="status">{{ status }}</div>

      <div v-if="progress.total > 0" class="progress-bar-track">
        <div
          class="progress-bar-fill"
          :style="{ width: `${(progress.round / progress.total) * 100}%` }"
        ></div>
      </div>

      <div v-if="progress.total > 0" class="progress-text">
        {{ progress.round }} / {{ progress.total }} 回合
      </div>

      <div v-if="error" class="error">{{ error }}</div>
    </div>

    <div v-if="logs.length > 0" class="log-area">
      <h3>诊断日志</h3>
      <div v-for="(log, i) in logs" :key="i" class="log-entry">
        <span class="log-event">{{ log.event }}</span>
        <span class="log-data">{{ JSON.stringify(log.data) }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.diagnosis-page {
  max-width: 600px;
  margin: 0 auto;
  padding: 60px 20px;
}

h2 {
  text-align: center;
  color: #1a1a2e;
  margin-bottom: 24px;
}

.progress-card {
  background: #f7fafc;
  padding: 32px;
  border-radius: 12px;
  text-align: center;
}

.status {
  font-size: 16px;
  color: #4a5568;
  margin-bottom: 20px;
}

.progress-bar-track {
  height: 8px;
  background: #e2e8f0;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 8px;
}

.progress-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #4a6cf7, #6d8afb);
  border-radius: 4px;
  transition: width 0.3s ease;
}

.progress-text {
  font-size: 14px;
  color: #718096;
}

.error {
  color: #e53e3e;
  margin-top: 12px;
}

.log-area {
  margin-top: 24px;
  background: #1a1a2e;
  color: #a0aec0;
  padding: 16px;
  border-radius: 8px;
  font-size: 12px;
  font-family: 'Courier New', monospace;
  max-height: 300px;
  overflow-y: auto;
}

.log-area h3 {
  color: #e2e8f0;
  margin-bottom: 8px;
  font-size: 13px;
}

.log-entry {
  padding: 2px 0;
}

.log-event {
  color: #68d391;
  margin-right: 8px;
}

.log-data {
  color: #a0aec0;
}
</style>

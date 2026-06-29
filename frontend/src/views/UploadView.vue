<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const transcript = ref('')
const error = ref('')
const loading = ref(false)

async function submit() {
  if (!transcript.value.trim()) {
    error.value = '请输入面试文字稿'
    return
  }
  error.value = ''
  loading.value = true
  router.push({
    name: 'diagnose',
    query: { transcript: transcript.value },
  })
}
</script>

<template>
  <div class="upload-page">
    <div class="hero">
      <h1>OfferFlow</h1>
      <p class="subtitle">面试诊断引擎 — 上传文字稿，获取结构化改进建议</p>
    </div>

    <div class="upload-area">
      <textarea
        v-model="transcript"
        placeholder="粘贴面试文字稿...
例如：
面试官：你的Agent项目和Cloud Code这类主流Agent的主要差异是什么？
候选人：我的项目主要差异在于..."
        rows="12"
      ></textarea>

      <p v-if="error" class="error">{{ error }}</p>

      <button
        class="btn-primary"
        :disabled="loading"
        @click="submit"
      >
        {{ loading ? '诊断中...' : '开始诊断' }}
      </button>
    </div>

    <div class="tips">
      <h3>使用说明</h3>
      <ul>
        <li>支持面试官/候选人标记格式的对话稿</li>
        <li>系统会自动拆分为多个面试回合逐题诊断</li>
        <li>诊断结果包含内容评分、表达评分、差距分析和改进建议</li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.upload-page {
  max-width: 720px;
  margin: 0 auto;
  padding: 60px 20px 40px;
}

.hero {
  text-align: center;
  margin-bottom: 32px;
}

.hero h1 {
  font-size: 2rem;
  font-weight: 700;
  color: #1a1a2e;
  margin-bottom: 8px;
}

.subtitle {
  color: #666;
  font-size: 1rem;
}

.upload-area {
  margin-bottom: 40px;
}

textarea {
  width: 100%;
  padding: 16px;
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.6;
  resize: vertical;
  font-family: inherit;
  transition: border-color 0.2s;
}

textarea:focus {
  outline: none;
  border-color: #4a6cf7;
}

.error {
  color: #e53e3e;
  font-size: 14px;
  margin-top: 8px;
}

.btn-primary {
  width: 100%;
  padding: 14px;
  background: #4a6cf7;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  margin-top: 12px;
  transition: background 0.2s;
}

.btn-primary:hover {
  background: #3b5de7;
}

.btn-primary:disabled {
  background: #a0aec0;
  cursor: not-allowed;
}

.tips {
  background: #f7fafc;
  padding: 24px;
  border-radius: 8px;
}

.tips h3 {
  font-size: 14px;
  color: #4a5568;
  margin-bottom: 8px;
}

.tips ul {
  font-size: 13px;
  color: #718096;
  padding-left: 20px;
}

.tips li {
  margin-bottom: 4px;
}
</style>

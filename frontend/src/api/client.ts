const API_BASE = import.meta.env.VITE_API_BASE || ''

export interface ProgressEvent {
  event: string
  data: Record<string, unknown>
}

export async function* diagnoseTranscript(
  transcript: string
): AsyncGenerator<ProgressEvent> {
  const response = await fetch(`${API_BASE}/api/diagnose`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ transcript }),
  })

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`)
  }

  const reader = response.body?.getReader()
  if (!reader) throw new Error('No response body')

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    let currentEvent = ''
    for (const line of lines) {
      if (line.startsWith('event: ')) {
        currentEvent = line.slice(7)
      } else if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6))
        yield { event: currentEvent, data }
      }
    }
  }
}

export async function fetchReport(
  reportId: string
): Promise<Record<string, unknown>> {
  const response = await fetch(`${API_BASE}/api/report/${reportId}`)
  if (!response.ok) {
    throw new Error(`Report not found: ${reportId}`)
  }
  return response.json()
}

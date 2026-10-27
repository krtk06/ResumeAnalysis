const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')

export class ApiError extends Error {
  constructor(message, { status = 0, requestId = null, retryAfter = null, detail = null } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.requestId = requestId
    this.retryAfter = retryAfter
    this.detail = detail
  }
}

function configError() {
  if (API_URL.includes('<') || API_URL.includes('your-backend')) {
    return new ApiError(
      'The analysis API is not configured for this deployment. Set VITE_API_URL in Vercel and redeploy.',
      { status: 0, detail: 'missing_api_url' }
    )
  }
  return null
}

async function parseError(response) {
  let payload = null
  try {
    payload = await response.json()
  } catch {
    payload = null
  }
  let detail = payload?.detail
  if (Array.isArray(detail)) {
    detail = detail.map((item) => item.msg || 'Invalid request').join('; ')
  }
  return new ApiError(detail || `Request failed (${response.status})`, {
    status: response.status,
    requestId: payload?.request_id || response.headers.get('x-request-id'),
    retryAfter: response.headers.get('retry-after'),
    detail,
  })
}

async function request(path, options = {}, timeoutMs = 60_000) {
  const missingConfig = configError()
  if (missingConfig) throw missingConfig

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const response = await fetch(`${API_URL}${path}`, { ...options, signal: controller.signal })
    if (!response.ok) throw await parseError(response)
    return await response.json()
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (error.name === 'AbortError') {
      throw new ApiError('The analysis timed out. The demo API may be waking up; try again.', {
        status: 0,
        detail: 'timeout',
      })
    }
    throw new ApiError('Could not reach the analysis API. Check your connection and try again.', {
      status: 0,
      detail: 'network',
    })
  } finally {
    clearTimeout(timer)
  }
}

export async function analyzeResume({ file, targetRole, jobDescription = '', consent = false }) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('target_role', targetRole)
  if (jobDescription.trim()) formData.append('job_description', jobDescription.trim())
  formData.append('consent', consent ? 'true' : 'false')

  return request('/api/analyze', {
    method: 'POST',
    body: formData,
  })
}

export async function getRoles() {
  return request('/api/roles')
}

export async function getConfig() {
  return request('/api/config')
}

export async function healthCheck() {
  return request('/api/health', {}, 5_000)
}

export async function fetchSample(path) {
  const response = await fetch(path)
  if (!response.ok) throw new Error('Sample file is unavailable.')
  return response.blob()
}

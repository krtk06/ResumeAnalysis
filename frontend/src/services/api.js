const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export async function analyzeResume(file, targetRole) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('target_role', targetRole)

  const response = await fetch(`${API_URL}/api/analyze`, {
    method: 'POST',
    body: formData
  })

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Analysis failed')
  }

  return response.json()
}

export async function getRoles() {
  const response = await fetch(`${API_URL}/api/roles`)
  return response.json()
}

export async function healthCheck() {
  const response = await fetch(`${API_URL}/api/health`)
  return response.json()
}
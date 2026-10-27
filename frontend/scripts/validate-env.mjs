const raw = (process.env.VITE_API_URL || '').trim()
const isVercel = process.env.VERCEL === '1' || Boolean(process.env.VERCEL_ENV)
const isProduction = process.env.NODE_ENV === 'production' || isVercel

function fail(message) {
  console.error(`\n[build] ${message}\n`)
  process.exit(1)
}

if (!raw) {
  if (isVercel) {
    fail('VITE_API_URL is missing. Set it in Vercel Project Settings and redeploy.')
  }
  console.warn('[build] VITE_API_URL is not set; the app will use http://localhost:8000.')
  process.exit(0)
}

if (raw.includes('<') || raw.includes('your-backend')) {
  fail(`VITE_API_URL still contains a placeholder: ${raw}`)
}

try {
  const parsed = new URL(raw)
  if (!['http:', 'https:'].includes(parsed.protocol)) {
    fail(`VITE_API_URL must be http(s), got ${parsed.protocol}`)
  }
  if (isProduction && parsed.protocol !== 'https:') {
    fail(`VITE_API_URL must use HTTPS in production, got ${raw}`)
  }
} catch {
  fail(`VITE_API_URL is not a valid URL: ${raw}`)
}

console.log(`[build] API URL: ${raw}`)

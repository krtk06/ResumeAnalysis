import { useEffect, useRef, useState } from 'react'
import UploadZone from './components/UploadZone'
import RoleSelector from './components/RoleSelector'
import ProcessingState from './components/ProcessingState'
import ResultsDashboard from './components/ResultsDashboard'
import { analyzeResume, fetchSample, getConfig, getRoles } from './services/api'

const FALLBACK_ROLES = [
  'Software Engineer',
  'Frontend Developer',
  'Backend Developer',
  'Full Stack Developer',
  'Data Scientist',
  'Machine Learning Engineer',
  'DevOps Engineer',
  'Product Manager',
  'UI/UX Designer',
  'Data Analyst',
]

function ThemeToggle({ theme, onToggle }) {
  const dark = theme === 'dark'
  const label = dark ? 'Switch to light theme' : 'Switch to dark theme'

  return (
    <button
      type="button"
      onClick={onToggle}
      aria-label={label}
      title={label}
      aria-pressed={dark}
      className="flex h-9 w-9 items-center justify-center border border-rule text-ink-soft transition-colors duration-150 hover:border-ink hover:text-ink"
    >
      {dark ? (
        <svg aria-hidden="true" className="h-4 w-4" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
          <circle cx="8" cy="8" r="3.25" />
          <path strokeLinecap="square" d="M8 0.75v2M8 13.25v2M0.75 8h2M13.25 8h2M2.9 2.9l1.4 1.4M11.7 11.7l1.4 1.4M13.1 2.9l-1.4 1.4M4.3 11.7l-1.4 1.4" />
        </svg>
      ) : (
        <svg aria-hidden="true" className="h-4 w-4" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path strokeLinecap="square" d="M13.5 9.5A5.5 5.5 0 016.5 2.5a5.5 5.5 0 107 7z" />
        </svg>
      )}
    </button>
  )
}

function Masthead({ file, targetRole, hasJd, theme, onThemeToggle }) {
  const date = new Date().toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
  })

  return (
    <header className="border-b border-ink">
      <div className="flex flex-wrap items-end justify-between gap-x-8 gap-y-3 pb-4">
        <h1 className="text-2xl md:text-3xl font-black uppercase tracking-normal [font-stretch:75%]">
          Resume Analyzer
        </h1>
        <div className="flex items-center gap-4">
          <p className="font-spec text-xs uppercase tracking-[0.14em] text-ink-soft">
            Proof sheet · evidence-backed match
          </p>
          <ThemeToggle theme={theme} onToggle={onThemeToggle} />
        </div>
      </div>
      <dl className="grid grid-cols-2 gap-x-6 border-t border-rule pt-3 font-spec text-xs sm:grid-cols-4">
        <div className="min-w-0">
          <dt className="uppercase tracking-[0.14em] text-ink-faint">File</dt>
          <dd className="truncate mt-0.5 text-ink">{file ? file.name : '—'}</dd>
        </div>
        <div>
          <dt className="uppercase tracking-[0.14em] text-ink-faint">Format</dt>
          <dd className="mt-0.5 text-ink">
            {file ? (file.name.toLowerCase().endsWith('.pdf') ? 'PDF' : 'DOCX') : '—'}
          </dd>
        </div>
        <div className="min-w-0">
          <dt className="uppercase tracking-[0.14em] text-ink-faint">Target role</dt>
          <dd className="truncate mt-0.5 text-ink">{targetRole || '—'}</dd>
        </div>
        <div>
          <dt className="uppercase tracking-[0.14em] text-ink-faint">{hasJd ? 'Brief + date' : 'Date'}</dt>
          <dd className="mt-0.5 text-ink">{hasJd ? `Attached · ${date}` : date}</dd>
        </div>
      </dl>
    </header>
  )
}

function errorCopy(error) {
  if (!error) return null
  if (error.status === 0) {
    return {
      heading: 'Press offline',
      note: 'The analysis API could not be reached. The demo backend may be waking up or offline.',
      action: 'Try again',
    }
  }
  if (error.status === 413) {
    return {
      heading: 'File over the press limit',
      note: 'The maximum upload is 10 MB. Compress the PDF or export a lighter DOCX.',
      action: 'Choose another file',
    }
  }
  if (error.status === 415) {
    return {
      heading: 'Unsupported sheet',
      note: 'Only text-based PDF and DOCX resumes are accepted. Legacy .doc files are not supported.',
      action: 'Choose another file',
    }
  }
  if (error.status === 422) {
    return {
      heading: 'Could not read this sheet',
      note: 'The file may be a scanned image, a non-resume document, or missing extractable text.',
      action: 'Choose another file',
    }
  }
  if (error.status === 429) {
    return {
      heading: 'Too many proofs',
      note: `This network has hit the demo limit.${error.retryAfter ? ` Retry in ${error.retryAfter} seconds.` : ' Try again later.'}`,
      action: 'Retry later',
    }
  }
  if (error.status === 503) {
    return {
      heading: 'Press warming up',
      note: 'The models are still loading. Wait a moment and try again.',
      action: 'Try again',
    }
  }
  return {
    heading: 'Press jammed',
    note: 'The analysis did not complete. The request ID below helps trace it.',
    action: 'Try again',
  }
}

function App() {
  const [file, setFile] = useState(null)
  const [targetRole, setTargetRole] = useState('')
  const [jobDescription, setJobDescription] = useState('')
  const [consent, setConsent] = useState(false)
  const [isProcessing, setIsProcessing] = useState(false)
  const [results, setResults] = useState(null)
  const [error, setError] = useState(null)
  const [config, setConfig] = useState(null)
  const [roles, setRoles] = useState(FALLBACK_ROLES)
  const [sampleNotice, setSampleNotice] = useState(null)
  const [theme, setTheme] = useState(() =>
    typeof document !== 'undefined' && document.documentElement.classList.contains('dark') ? 'dark' : 'light'
  )
  const resultsRef = useRef(null)
  const requestStartRef = useRef(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([getConfig().catch(() => null), getRoles().catch(() => null)]).then(([nextConfig, nextRoles]) => {
      if (cancelled) return
      if (nextConfig) setConfig(nextConfig)
      if (nextRoles?.roles?.length) setRoles(nextRoles.roles)
    })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (results) resultsRef.current?.focus()
  }, [results])

  const toggleTheme = () => {
    const next = theme === 'dark' ? 'light' : 'dark'
    document.documentElement.classList.toggle('dark', next === 'dark')
    try {
      localStorage.setItem('ra-theme', next)
    } catch (error) {
      console.warn('Theme persistence failed (storage unavailable):', error)
    }
    setTheme(next)
  }

  const maxUploadMb = config?.max_upload_mb || 10
  const maxJdChars = config?.max_jd_chars || 10000
  const jdAttached = jobDescription.trim().length > 0

  const handleFile = (nextFile) => {
    setFile(nextFile)
    setError(null)
    setResults(null)
    setSampleNotice(null)
  }

  const handleAnalyze = async () => {
    if (!file || !targetRole) {
      setError(new Error('Add a resume and pick a target role before running the analysis.'))
      return
    }

    setError(null)
    setResults(null)
    setIsProcessing(true)
    requestStartRef.current = Date.now()

    try {
      const data = await analyzeResume({
        file,
        targetRole,
        jobDescription,
        consent,
      })
      setResults(data)
    } catch (err) {
      setError(err)
    } finally {
      setIsProcessing(false)
    }
  }

  const handleReset = () => {
    setFile(null)
    setTargetRole('')
    setJobDescription('')
    setConsent(false)
    setResults(null)
    setError(null)
    setSampleNotice(null)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const loadSampleResume = async () => {
    setSampleNotice(null)
    try {
      const blob = await fetchSample('/samples/sample-resume.pdf')
      const sample = new File([blob], 'sample-resume.pdf', { type: 'application/pdf' })
      handleFile(sample)
      if (!targetRole) setTargetRole('Software Engineer')
      setSampleNotice('Sample resume loaded. Pick a role, or load the sample brief too.')
    } catch {
      setSampleNotice('The sample resume could not be loaded.')
    }
  }

  const loadSampleBrief = async () => {
    try {
      const response = await fetch('/samples/sample-jd.txt')
      if (!response.ok) throw new Error('missing sample brief')
      const text = await response.text()
      setJobDescription(text.slice(0, maxJdChars))
      if (!targetRole) setTargetRole('Software Engineer')
      setSampleNotice('Sample brief loaded. The evidence panel will cite its requirements.')
    } catch {
      setSampleNotice('The sample brief could not be loaded.')
    }
  }

  const errorState = errorCopy(error)
  const showConsent = Boolean(config?.llm_enabled)
  const busy = isProcessing

  return (
    <div className="min-h-screen bg-stock p-4 md:p-10">
      <div className="mx-auto max-w-3xl">
        {results && !isProcessing ? (
          <>
            <div className="mb-6 flex items-center justify-between">
              <button
                onClick={handleReset}
                className="font-spec text-xs uppercase tracking-[0.14em] text-ink-soft underline decoration-rule underline-offset-4 hover:text-proof hover:decoration-proof transition-colors"
              >
                ← New proof sheet
              </button>
              <ThemeToggle theme={theme} onToggle={toggleTheme} />
            </div>
            <div ref={resultsRef} tabIndex={-1} style={{ outline: 'none' }} className="outline-none" aria-live="polite">
              <ResultsDashboard results={results} config={config} />
            </div>
          </>
        ) : (
          <>
            <Masthead
              file={file}
              targetRole={targetRole}
              hasJd={jdAttached}
              theme={theme}
              onThemeToggle={toggleTheme}
            />

            {errorState && (
              <div role="alert" className="mt-6 border-[3px] border-proof bg-stock px-5 py-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <p className="inline-flex items-center gap-2 border border-proof px-2 py-1 font-spec text-[10px] font-bold uppercase tracking-[0.16em] text-proof">
                    <span aria-hidden="true" className="h-1.5 w-1.5 bg-proof" />
                    Proof rejected
                  </p>
                  {error?.requestId && (
                    <span className="font-spec text-[10px] uppercase tracking-[0.14em] text-ink-faint">
                      Request {error.requestId}
                    </span>
                  )}
                </div>
                <p className="mt-4 text-[11px] font-bold uppercase tracking-[0.18em] text-proof [font-stretch:85%]">
                  {errorState.heading}
                </p>
                <p className="mt-2 max-w-prose text-base font-medium leading-relaxed text-ink">
                  {error?.message || errorState.note}
                </p>
                <p className="mt-3 max-w-prose border-t border-rule pt-3 font-spec text-xs leading-relaxed text-ink-soft">
                  {errorState.note}
                </p>
                {file && (
                  <button
                    type="button"
                    onClick={handleAnalyze}
                    className="mt-4 border border-ink px-4 py-2 font-spec text-[10px] uppercase tracking-[0.14em] text-ink transition-colors hover:bg-ink hover:text-stock"
                  >
                    {errorState.action}
                  </button>
                )}
              </div>
            )}

            {isProcessing ? (
              <div className="max-w-xl mx-auto" aria-busy="true">
                <ProcessingState startedAt={requestStartRef.current} />
              </div>
            ) : (
              <div className="space-y-10 pt-8">
                <section>
                  <h2 className="mb-4 flex items-baseline gap-3 border-b border-rule pb-2 text-lg font-extrabold uppercase tracking-normal [font-stretch:80%]">
                    Document intake
                  </h2>
                  <UploadZone
                    onFileSelect={handleFile}
                    selectedFile={file}
                    maxSizeMb={maxUploadMb}
                    onSample={loadSampleResume}
                  />
                  {sampleNotice && (
                    <p role="status" className="mt-3 font-spec text-xs text-ink-soft">
                      {sampleNotice}
                    </p>
                  )}
                </section>

                <section>
                  <h2 className="mb-4 flex items-baseline gap-3 border-b border-rule pb-2 text-lg font-extrabold uppercase tracking-normal [font-stretch:80%]">
                    Target role
                  </h2>
                  <RoleSelector value={targetRole} onChange={setTargetRole} roles={roles} />
                </section>

                <section>
                  <h2 className="mb-4 flex flex-wrap items-baseline justify-between gap-2 border-b border-rule pb-2 text-lg font-extrabold uppercase tracking-normal [font-stretch:80%]">
                    Job brief
                    <span className="font-spec text-[10px] font-normal uppercase tracking-[0.14em] text-ink-faint">
                      Optional
                    </span>
                  </h2>
                  <div className="space-y-2">
                    <label htmlFor="job-description" className="sr-only">
                      Job description
                    </label>
                    <textarea
                      id="job-description"
                      value={jobDescription}
                      onChange={(event) => setJobDescription(event.target.value.slice(0, maxJdChars))}
                      rows={5}
                      placeholder="Paste a job description to score against its actual requirements. Leave blank to use the role template."
                      className="w-full resize-y border-0 border-b border-rule bg-transparent px-1 py-3 text-sm leading-relaxed text-ink placeholder:text-ink-faint focus:border-ink focus:outline-none"
                    />
                    <div className="flex flex-wrap items-center justify-between gap-2 font-spec text-[10px] uppercase tracking-[0.12em] text-ink-faint">
                      <button
                        type="button"
                        onClick={loadSampleBrief}
                        className="underline decoration-rule underline-offset-4 hover:text-proof hover:decoration-proof"
                      >
                        Load sample brief
                      </button>
                      <span className="tabular-nums">
                        {jobDescription.length.toLocaleString()} / {maxJdChars.toLocaleString()}
                      </span>
                    </div>
                  </div>
                </section>

                {showConsent && (
                  <section className="border border-rule px-4 py-4">
                    <label className="flex items-start gap-3 text-sm leading-relaxed text-ink">
                      <input
                        type="checkbox"
                        checked={consent}
                        onChange={(event) => setConsent(event.target.checked)}
                        className="mt-1 h-4 w-4 accent-[rgb(var(--proof))]"
                      />
                      <span>
                        Send the redacted resume text to OpenCode Go for an AI review.
                        <span className="mt-1 block font-spec text-[10px] uppercase tracking-[0.12em] text-ink-faint">
                          Beam Free · no training · 30-day retention · optional
                        </span>
                      </span>
                    </label>
                    <p className="mt-3 border-t border-rule pt-3 font-spec text-[10px] leading-relaxed text-ink-soft">
                      Leave unchecked for local scoring. Read the{' '}
                      <a
                        href={config?.privacy_url || '/privacy.html'}
                        className="underline decoration-rule underline-offset-2 hover:text-proof"
                      >
                        privacy note
                      </a>
                      .
                    </p>
                  </section>
                )}

                <button
                  onClick={handleAnalyze}
                  disabled={!file || !targetRole || busy}
                  className="press-button group flex w-full items-center justify-center gap-3 border-2 border-ink bg-ink py-4 text-lg font-extrabold uppercase tracking-wide [font-stretch:85%] text-stock transition-all duration-300 enabled:hover:-translate-y-1 enabled:hover:bg-transparent enabled:hover:text-ink enabled:active:translate-y-0 disabled:cursor-not-allowed disabled:border-rule disabled:bg-transparent disabled:text-ink-faint"
                >
                  Run analysis
                  <svg aria-hidden="true" className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path strokeLinecap="square" d="M1.5 8h12M9 3.5L13.5 8 9 12.5" />
                  </svg>
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

export default App

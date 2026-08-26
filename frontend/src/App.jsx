import { useState } from 'react'
import UploadZone from './components/UploadZone'
import RoleSelector from './components/RoleSelector'
import ProcessingState from './components/ProcessingState'
import ResultsDashboard from './components/ResultsDashboard'

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

function Masthead({ file, targetRole, theme, onThemeToggle }) {
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
            Proof sheet · pre-press document check
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
          <dd className="mt-0.5 text-ink">{file ? (file.name.toLowerCase().endsWith('.pdf') ? 'PDF' : 'DOCX') : '—'}</dd>
        </div>
        <div className="min-w-0">
          <dt className="uppercase tracking-[0.14em] text-ink-faint">Target role</dt>
          <dd className="truncate mt-0.5 text-ink">{targetRole || '—'}</dd>
        </div>
        <div>
          <dt className="uppercase tracking-[0.14em] text-ink-faint">Date</dt>
          <dd className="mt-0.5 text-ink">{date}</dd>
        </div>
      </dl>
    </header>
  )
}

function App() {
  const [file, setFile] = useState(null)
  const [targetRole, setTargetRole] = useState('')
  const [isProcessing, setIsProcessing] = useState(false)
  const [results, setResults] = useState(null)
  const [error, setError] = useState(null)
  const [theme, setTheme] = useState(() =>
    typeof document !== 'undefined' && document.documentElement.classList.contains('dark') ? 'dark' : 'light'
  )

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

  const handleAnalyze = async () => {
    if (!file || !targetRole) {
      setError('Add a resume and pick a target role before running the analysis.')
      return
    }

    setError(null)
    setIsProcessing(true)

    const formData = new FormData()
    formData.append('file', file)
    formData.append('target_role', targetRole)

    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
      const response = await fetch(`${apiUrl}/api/analyze`, {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Analysis failed')
      }

      const data = await response.json()

      setTimeout(() => {
        setResults(data)
        setIsProcessing(false)
      }, 2000)
    } catch (err) {
      setError(err.message || 'Failed to analyze resume')
      setIsProcessing(false)
    }
  }

  const handleReset = () => {
    setFile(null)
    setTargetRole('')
    setResults(null)
    setError(null)
  }

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
            <ResultsDashboard results={results} />
          </>
        ) : (
          <>
            <Masthead file={file} targetRole={targetRole} theme={theme} onThemeToggle={toggleTheme} />

            {error && (
              <div role="alert" className="mt-6 border-[3px] border-proof bg-stock px-5 py-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <p className="inline-flex items-center gap-2 border border-proof px-2 py-1 font-spec text-[10px] font-bold uppercase tracking-[0.16em] text-proof">
                    <span aria-hidden="true" className="h-1.5 w-1.5 bg-proof" />
                    Proof rejected
                  </p>
                  <span className="font-spec text-[10px] uppercase tracking-[0.14em] text-ink-faint">Not a resume</span>
                </div>
                <p className="mt-4 text-[11px] font-bold uppercase tracking-[0.18em] text-proof [font-stretch:85%]">Rejected</p>
                <p className="mt-2 max-w-prose text-base font-medium leading-relaxed text-ink">{error}</p>
                <p className="mt-3 max-w-prose border-t border-rule pt-3 font-spec text-xs leading-relaxed text-ink-soft">
                  This press only checks candidate sheets. Upload a file with experience, education, and skills, then run the check again.
                </p>
              </div>
            )}

            {isProcessing ? (
              <div className="max-w-xl mx-auto">
                <ProcessingState />
              </div>
            ) : (
              <div className="space-y-10 pt-8">
                <section>
                  <h2 className="mb-4 flex items-baseline gap-3 border-b border-rule pb-2 text-lg font-extrabold uppercase tracking-normal [font-stretch:80%]">
                    Document intake
                  </h2>
                  <UploadZone onFileSelect={setFile} selectedFile={file} />
                </section>

                <section>
                  <h2 className="mb-4 flex items-baseline gap-3 border-b border-rule pb-2 text-lg font-extrabold uppercase tracking-normal [font-stretch:80%]">
                    Target role
                  </h2>
                  <RoleSelector value={targetRole} onChange={setTargetRole} />
                </section>

                <button
                  onClick={handleAnalyze}
                  disabled={!file || !targetRole}
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

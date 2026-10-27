import { useEffect, useState } from 'react'

const PROCESSING_STAGES = [
  { text: 'Parsing document', until: 1200 },
  { text: 'Extracting entities', until: 2600 },
  { text: 'Reading evidence', until: 4600 },
  { text: 'Measuring semantic similarity', until: 7000 },
  { text: 'Setting the verdict', until: 12000 },
]

const TOTAL_MS = PROCESSING_STAGES[PROCESSING_STAGES.length - 1].until

function ProcessingState({ startedAt }) {
  const [elapsed, setElapsed] = useState(() =>
    startedAt ? Math.max(0, Date.now() - startedAt) : 0
  )

  useEffect(() => {
    const start = startedAt || Date.now()
    const interval = setInterval(() => {
      setElapsed(Math.max(0, Date.now() - start))
    }, 100)
    return () => clearInterval(interval)
  }, [startedAt])

  const progress = Math.min((elapsed / TOTAL_MS) * 100, 92)
  const currentStage = PROCESSING_STAGES.findIndex((stage) => elapsed < stage.until)
  const activeStage = currentStage === -1 ? PROCESSING_STAGES.length - 1 : currentStage

  return (
    <div className="pt-10" aria-live="polite">
      <h2 className="mb-2 border-b border-ink pb-3 text-xl font-extrabold uppercase tracking-normal [font-stretch:80%]">
        On press
      </h2>
      <p className="mb-5 font-spec text-[10px] uppercase tracking-[0.14em] text-ink-faint">
        The sheet stays at 92% until the verdict returns.
      </p>

      <ol className="border-t border-rule">
        {PROCESSING_STAGES.map((stage, index) => {
          const done = index < activeStage || elapsed >= TOTAL_MS
          const active = index === activeStage && elapsed < TOTAL_MS

          return (
            <li
              key={stage.text}
              className={`
                grid grid-cols-[2.5rem_1fr] items-center gap-x-4 border-b border-rule px-2 py-4 transition-colors duration-300
                ${active ? 'bg-ink text-stock loading-stage' : done ? 'text-ink' : 'text-ink-faint'}
              `}
            >
              <span className="font-spec text-xs tabular-nums">
                {String(index + 1).padStart(2, '0')}
              </span>
              <span className="flex items-center justify-between gap-4">
                <span className={`font-medium ${active ? 'font-bold uppercase tracking-wide [font-stretch:85%]' : ''}`}>
                  {stage.text}
                  {done && (
                    <svg aria-hidden="true" className="ml-3 inline h-3 w-3 text-proof" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
                      <path strokeLinecap="square" d="M2.5 8.5l4 4 7-8" />
                    </svg>
                  )}
                </span>
                <span className="flex items-center gap-2 font-spec text-[10px] uppercase tracking-[0.14em]">
                  {active && <span aria-hidden="true" className="loading-signal" />}
                  {active ? 'running' : done ? 'done' : 'queued'}
                </span>
              </span>
            </li>
          )
        })}
      </ol>

      <div className="mt-8">
        <div
          className="h-[3px] w-full bg-rule"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(progress)}
          aria-label="Analysis progress"
        >
          <div
            className="h-full bg-proof transition-all duration-300 ease-out"
            style={{ width: `${progress}%` }}
          />
        </div>
        <p className="mt-2 text-right font-spec text-xs tabular-nums text-ink-soft">
          {Math.round(progress)}%
        </p>
      </div>
    </div>
  )
}

export default ProcessingState

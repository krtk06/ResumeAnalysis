import { useState, useEffect } from 'react'

const PROCESSING_STAGES = [
  { text: 'Parsing document', duration: 800 },
  { text: 'Extracting entities', duration: 1000 },
  { text: 'Analyzing skills', duration: 1200 },
  { text: 'Measuring semantic similarity', duration: 1400 },
  { text: 'Setting the verdict', duration: 600 }
]

function ProcessingState() {
  const [currentStage, setCurrentStage] = useState(0)
  const [progress, setProgress] = useState(0)

  useEffect(() => {
    let stageIndex = 0
    const startTime = Date.now()

    const interval = setInterval(() => {
      const elapsed = Date.now() - startTime
      const totalDuration = PROCESSING_STAGES.reduce((sum, s) => sum + s.duration, 0)
      const newProgress = Math.min((elapsed / totalDuration) * 100, 100)
      setProgress(newProgress)

      let accumulated = 0
      for (let i = 0; i < PROCESSING_STAGES.length; i++) {
        if (elapsed < accumulated + PROCESSING_STAGES[i].duration) {
          stageIndex = i
          break
        }
        accumulated += PROCESSING_STAGES[i].duration
      }

      setCurrentStage(stageIndex)

      if (newProgress >= 100) {
        clearInterval(interval)
      }
    }, 100)

    return () => clearInterval(interval)
  }, [])

  return (
    <div className="pt-10">
      <h2 className="mb-6 border-b border-ink pb-3 text-xl font-extrabold uppercase tracking-normal [font-stretch:80%]">
        On press
      </h2>

      <ol className="border-t border-rule">
        {PROCESSING_STAGES.map((stage, index) => {
          const done = index < currentStage || progress >= 100
          const active = index === currentStage && progress < 100

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
        <div className="h-[3px] w-full bg-rule">
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

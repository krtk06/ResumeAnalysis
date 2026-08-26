function ResultsDashboard({ results }) {
  const { score, matched_role, alternative_roles, improvements, extracted_entities } = results

  const getScoreLabel = (value) => {
    if (value >= 8) return 'Excellent match'
    if (value >= 6) return 'Good match'
    if (value >= 4) return 'Moderate match'
    return 'Needs work'
  }

  return (
    <div className="space-y-12">
      <section className="flex flex-col items-center gap-6 py-6 sm:flex-row sm:justify-between">
        <div className="stamp-in select-none border-[3px] border-proof px-8 py-5 text-center text-proof">
          <p className="text-sm font-bold uppercase tracking-[0.2em] [font-stretch:80%]">
            Match score
          </p>
          <p className="mt-1 font-black leading-none tabular-nums [font-stretch:75%]">
            <span className="text-7xl">{score}</span>
            <span className="ml-1 align-top text-2xl font-bold">/10</span>
          </p>
          <p className="mt-2 font-spec text-xs uppercase tracking-[0.14em]">
            {getScoreLabel(score)} · {matched_role}
          </p>
        </div>
        <div className="max-w-xs border-l border-rule pl-5 text-sm leading-relaxed text-ink-soft sm:text-right sm:border-l-0 sm:border-r sm:pl-0 sm:pr-5">
          The verdict is set from semantic similarity and keyword coverage against
          the {matched_role} role. Corrections below are ranked by priority.
        </div>
      </section>

      <section>
        <h2 className="mb-4 flex items-baseline justify-between border-b border-ink pb-2 text-lg font-extrabold uppercase tracking-normal [font-stretch:80%]">
          Alternative roles
        </h2>
        <ol className="border-t border-rule">
          {alternative_roles.map((alt, index) => (
            <li
              key={alt.role}
              className="grid grid-cols-[2.5rem_1fr_auto] items-center gap-x-4 border-b border-rule px-2 py-4 hover:bg-stock-deep transition-colors"
            >
              <span className="font-spec text-xs tabular-nums text-ink-faint">
                {String(index + 1).padStart(2, '0')}
              </span>
              <span className="min-w-0 truncate font-medium">{alt.role}</span>
              <span className="flex items-center gap-3">
                <span className="hidden h-1 w-24 bg-rule/70 sm:block" aria-hidden="true">
                  <span
                    className="block h-full bg-proof"
                    style={{ width: `${Math.round(alt.match * 100)}%` }}
                  />
                </span>
                <span className="w-10 text-right font-spec text-xs tabular-nums text-ink">
                  {Math.round(alt.match * 100)}%
                </span>
              </span>
            </li>
          ))}
        </ol>
      </section>

      <section>
        <h2 className="mb-4 border-b border-ink pb-2 text-lg font-extrabold uppercase tracking-normal [font-stretch:80%]">
          Corrections
        </h2>
        <ol className="border-t border-rule">
          {improvements.map((item, index) => (
            <li
              key={index}
              className="grid grid-cols-[2.5rem_1fr_auto] items-baseline gap-x-4 border-b border-rule px-2 py-4"
            >
              <span className="font-spec text-xs tabular-nums text-ink-faint self-center">
                {String(index + 1).padStart(2, '0')}
              </span>
              <p className={`text-base ${item.priority === 'high' ? 'font-semibold underline decoration-proof decoration-2 underline-offset-4' : ''}`}>
                {item.area}
              </p>
              <span
                className={`
                  shrink-0 self-center px-2 py-0.5 font-spec text-[10px] uppercase tracking-[0.14em]
                  ${item.priority === 'high'
                    ? 'bg-proof text-stock'
                    : 'border border-rule text-ink-faint'}
                `}
              >
                {item.priority}
              </span>
            </li>
          ))}
        </ol>
      </section>

      {extracted_entities && extracted_entities.skills && extracted_entities.skills.length > 0 && (
        <section>
          <h2 className="mb-4 border-b border-ink pb-2 text-lg font-extrabold uppercase tracking-normal [font-stretch:80%]">
            Skills read off the sheet
          </h2>
          <ul className="flex flex-wrap gap-x-3 gap-y-2">
            {extracted_entities.skills.map((skill) => (
              <li
                key={skill}
                className="border border-rule bg-transparent px-2.5 py-1 text-sm text-ink"
              >
                {skill}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}

export default ResultsDashboard

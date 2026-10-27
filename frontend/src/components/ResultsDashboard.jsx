function ResultsDashboard({ results, config }) {
  const {
    score,
    band,
    matched_role,
    alternative_roles = [],
    improvements = [],
    extracted_entities = {},
    rubric,
    evidence = [],
    missing_requirements = [],
    next_band_actions = [],
    scoring_source,
    llm_model,
    embedding_model,
    jd_used,
    privacy,
  } = results

  const skills = extracted_entities.skills || []
  const education = extracted_entities.education || []
  const experienceYears = extracted_entities.experience_years || 0
  const sourceLabel =
    scoring_source === 'opencode_go'
      ? `AI review${llm_model ? ` · ${llm_model}` : ''}`
      : scoring_source === 'local_consent'
        ? 'Local scoring · AI review off'
        : scoring_source === 'local_quota'
          ? 'Local scoring · AI quota guard'
          : scoring_source === 'local_fallback'
            ? 'Local scoring · AI unavailable'
            : 'Local scoring'

  const calibrationLabel =
    rubric?.calibration_version && rubric.calibration_version !== 'identity'
      ? rubric.calibration_version
      : 'uncalibrated'

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
            {band} · {matched_role}
          </p>
        </div>
        <div className="max-w-xs border-l border-rule pl-5 text-sm leading-relaxed text-ink-soft sm:text-right sm:border-l-0 sm:border-r sm:pl-0 sm:pr-5">
          <p>{sourceLabel}.</p>
          <p className="mt-2 font-spec text-[10px] uppercase tracking-[0.12em] text-ink-faint">
            {jd_used ? 'Scored against the attached brief' : 'Scored against the role template'}
            {' · '}
            {embedding_model || 'local embeddings'}
          </p>
          {privacy?.external_llm_used && (
            <p className="mt-2 font-spec text-[10px] leading-relaxed text-ink-faint">
              Redacted text was sent to OpenCode Go with consent. No upload is stored.
            </p>
          )}
        </div>
      </section>

      {rubric && (
        <section>
          <h2 className="mb-4 flex items-baseline justify-between gap-3 border-b border-ink pb-2 text-lg font-extrabold uppercase tracking-normal [font-stretch:80%]">
            How the verdict was built
            <span className="font-spec text-[10px] font-normal uppercase tracking-[0.12em] text-ink-faint">
              {calibrationLabel}
            </span>
          </h2>
          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {[
              ['Semantic', rubric.semantic, `${Math.round(rubric.semantic * 100)}%`],
              ['Requirement coverage', rubric.coverage, `${Math.round(rubric.coverage * 100)}%`],
              ['Raw score', rubric.raw_score / 10, rubric.raw_score.toFixed(1)],
              ['Calibrated', rubric.calibrated_score / 10, rubric.calibrated_score.toFixed(1)],
            ].map(([label, value, display]) => (
              <div key={label} className="border-t border-rule pt-2">
                <dt className="font-spec text-[10px] uppercase tracking-[0.12em] text-ink-faint">
                  {label}
                </dt>
                <dd className="mt-1 font-spec text-lg font-bold tabular-nums text-ink">{display}</dd>
                <div className="mt-2 h-[3px] w-full bg-rule/60" aria-hidden="true">
                  <div className="h-full bg-proof" style={{ width: `${Math.round(value * 100)}%` }} />
                </div>
              </div>
            ))}
          </dl>
          <p className="mt-4 border-t border-rule pt-3 font-spec text-[10px] leading-relaxed text-ink-soft">
            The raw score weights semantic similarity at 60% and weighted requirement coverage at
            40%. Calibration is applied only when a fitted calibration file is present; the
            current build does not invent a multiplier.
          </p>
        </section>
      )}

      {evidence.length > 0 && (
        <section>
          <h2 className="mb-4 flex items-baseline justify-between border-b border-ink pb-2 text-lg font-extrabold uppercase tracking-normal [font-stretch:80%]">
            Evidence on the sheet
            <span className="font-spec text-[10px] font-normal uppercase tracking-[0.12em] text-ink-faint">
              {evidence.length} cited
            </span>
          </h2>
          <ol className="border-t border-rule">
            {evidence.map((item, index) => (
              <li
                key={`${item.requirement}-${item.line}-${index}`}
                className="grid grid-cols-[2.5rem_1fr] gap-x-4 border-b border-rule px-2 py-4"
              >
                <span className="font-spec text-xs tabular-nums text-ink-faint">
                  {String(index + 1).padStart(2, '0')}
                </span>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <p className="text-sm font-semibold text-ink">{item.requirement}</p>
                    <span className="font-spec text-[10px] uppercase tracking-[0.12em] text-ink-faint">
                      line {item.line}
                      {item.source === 'llm_verified' ? ' · AI-verified' : ''}
                    </span>
                  </div>
                  <blockquote className="mt-2 border-l-2 border-proof pl-3 text-sm leading-relaxed text-ink-soft">
                    “{item.quote}”
                  </blockquote>
                </div>
              </li>
            ))}
          </ol>
        </section>
      )}

      {missing_requirements.length > 0 && (
        <section>
          <h2 className="mb-4 flex items-baseline justify-between border-b border-ink pb-2 text-lg font-extrabold uppercase tracking-normal [font-stretch:80%]">
            Gaps on the sheet
            <span className="font-spec text-[10px] font-normal uppercase tracking-[0.12em] text-ink-faint">
              {missing_requirements.length} open
            </span>
          </h2>
          <ol className="border-t border-rule">
            {missing_requirements.map((item, index) => (
              <li
                key={`${item.requirement}-${index}`}
                className="grid grid-cols-[2.5rem_1fr_auto] items-baseline gap-x-4 border-b border-rule px-2 py-4"
              >
                <span className="font-spec text-xs tabular-nums text-ink-faint self-center">
                  {String(index + 1).padStart(2, '0')}
                </span>
                <div className="min-w-0">
                  <p className="text-base font-medium">{item.requirement}</p>
                  <p className="mt-1 font-spec text-[10px] text-ink-faint">{item.why}</p>
                </div>
                <span
                  className={`
                    shrink-0 self-center px-2 py-0.5 font-spec text-[10px] uppercase tracking-[0.14em]
                    ${item.must_have ? 'bg-proof text-stock' : 'border border-rule text-ink-faint'}
                  `}
                >
                  {item.must_have ? 'must-have' : `weight ${item.weight}`}
                </span>
              </li>
            ))}
          </ol>
        </section>
      )}

      {next_band_actions.length > 0 && (
        <section>
          <h2 className="mb-4 border-b border-ink pb-2 text-lg font-extrabold uppercase tracking-normal [font-stretch:80%]">
            What would move this to an 8
          </h2>
          <ol className="border-t border-rule">
            {next_band_actions.map((item, index) => (
              <li
                key={`${item.target_requirement}-${index}`}
                className="grid grid-cols-[2.5rem_1fr_auto] items-baseline gap-x-4 border-b border-rule px-2 py-4"
              >
                <span className="font-spec text-xs tabular-nums text-ink-faint self-center">
                  {String(index + 1).padStart(2, '0')}
                </span>
                <p className="text-base leading-relaxed">{item.action}</p>
                <span className="shrink-0 self-center border border-rule px-2 py-0.5 font-spec text-[10px] uppercase tracking-[0.12em] text-ink-faint">
                  +{item.expected_gain.toFixed(1)} potential
                </span>
              </li>
            ))}
          </ol>
        </section>
      )}

      <section>
        <h2 className="mb-4 flex items-baseline justify-between border-b border-ink pb-2 text-lg font-extrabold uppercase tracking-normal [font-stretch:80%]">
          Alternative roles
          <span className="font-spec text-[10px] font-normal uppercase tracking-[0.12em] text-ink-faint">
            semantic similarity
          </span>
        </h2>
        {alternative_roles.length === 0 ? (
          <p className="border-t border-rule px-2 py-4 text-sm text-ink-soft">
            No close alternative roles found for this sheet.
          </p>
        ) : (
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
        )}
        <p className="mt-2 font-spec text-[10px] leading-relaxed text-ink-faint">
          These are cosine similarities against role descriptions, not probabilities or hiring
          predictions.
        </p>
      </section>

      <section>
        <h2 className="mb-4 border-b border-ink pb-2 text-lg font-extrabold uppercase tracking-normal [font-stretch:80%]">
          Corrections
        </h2>
        {improvements.length === 0 ? (
          <p className="border-t border-rule px-2 py-4 text-sm text-ink-soft">
            No corrections were returned for this sheet.
          </p>
        ) : (
          <ol className="border-t border-rule">
            {improvements.map((item, index) => (
              <li
                key={`${item.area}-${index}`}
                className="grid grid-cols-[2.5rem_1fr_auto] items-baseline gap-x-4 border-b border-rule px-2 py-4"
              >
                <span className="font-spec text-xs tabular-nums text-ink-faint self-center">
                  {String(index + 1).padStart(2, '0')}
                </span>
                <div>
                  <p className={`text-base ${item.priority === 'high' ? 'font-semibold underline decoration-proof decoration-2 underline-offset-4' : ''}`}>
                    {item.area}
                  </p>
                  {item.action && (
                    <p className="mt-1 text-sm leading-relaxed text-ink-soft">{item.action}</p>
                  )}
                </div>
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
        )}
      </section>

      {(skills.length > 0 || education.length > 0 || experienceYears > 0) && (
        <section>
          <h2 className="mb-4 border-b border-ink pb-2 text-lg font-extrabold uppercase tracking-normal [font-stretch:80%]">
            Read off the sheet
          </h2>
          <dl className="grid gap-4 border-t border-rule pt-4 sm:grid-cols-2">
            <div>
              <dt className="font-spec text-[10px] uppercase tracking-[0.12em] text-ink-faint">
                Experience
              </dt>
              <dd className="mt-1 text-base font-medium">
                {experienceYears > 0 ? `${experienceYears} years` : 'Not stated'}
              </dd>
            </div>
            <div>
              <dt className="font-spec text-[10px] uppercase tracking-[0.12em] text-ink-faint">
                Education
              </dt>
              <dd className="mt-1 text-sm leading-relaxed">
                {education.length > 0 ? education.join(' · ') : 'Not stated'}
              </dd>
            </div>
          </dl>
          {skills.length > 0 && (
            <ul className="mt-5 flex flex-wrap gap-x-3 gap-y-2">
              {skills.map((skill) => (
                <li
                  key={skill}
                  className="border border-rule bg-transparent px-2.5 py-1 text-sm text-ink"
                >
                  {skill}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      <footer className="border-t border-rule pt-4 font-spec text-[10px] uppercase tracking-[0.12em] text-ink-faint">
        {config?.version ? `v${config.version} · ` : ''}
        {privacy?.retention_note || 'Processed in memory; no upload is stored.'}
        {' · '}
        <a href={config?.privacy_url || '/privacy.html'} className="underline decoration-rule underline-offset-2 hover:text-proof">
          privacy
        </a>
      </footer>
    </div>
  )
}

export default ResultsDashboard

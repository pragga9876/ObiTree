export default function ReasoningPanel({ graph, stats }) {
  const reasoning = graph?.reasoning || {};
  const nodesById = new Map((graph?.nodes || []).map((node) => [node.id, node]));
  const nameOf = (id) => nodesById.get(id)?.name || id;

  const confidence = reasoning.confidence ?? 0;
  const corroborated = reasoning.corroborated || [];
  const singleSource = reasoning.single_source || [];
  const conflicts = reasoning.conflicts || [];
  const dateConflicts = reasoning.date_conflicts || [];
  const totalConflicts = conflicts.length + dateConflicts.length;

  return (
    <section className="reasoning-panel">
      <div className="reasoning-head">
        <div>
          <span className="kicker">Why this tree</span>
          <h3>Editor&rsquo;s reasoning</h3>
        </div>
        <div
          className="confidence-seal"
          style={{ "--score": `${Math.max(0, Math.min(360, confidence * 3.6))}deg` }}
          title={`${confidence}% relationship confidence`}
        >
          <div className="confidence-seal-inner">
            <strong>{confidence}</strong>
            <span>confidence</span>
          </div>
        </div>
      </div>

      <p className="reasoning-summary">{reasoning.summary}</p>

      <div className="reasoning-tallies">
        <div>
          <span className="tally-mark tally-ok">✓</span>
          <strong>{stats?.corroborated ?? 0}</strong>
          <span>corroborated</span>
        </div>
        <div>
          <span className="tally-mark tally-single">≈</span>
          <strong>{singleSource.length}</strong>
          <span>single source</span>
        </div>
        <div>
          <span className="tally-mark tally-conflict">!</span>
          <strong>{totalConflicts}</strong>
          <span>to review</span>
        </div>
      </div>

      {totalConflicts > 0 && (
        <div className="reasoning-block reasoning-block-conflict">
          <h4>Readings that disagree</h4>
          <ul className="reason-list">
            {conflicts.map((edge) => (
              <li key={edge.id}>
                <span className="reason-mark">!</span>
                <div>
                  <strong>
                    {nameOf(edge.source)} · {edge.label} · {nameOf(edge.target)}
                  </strong>
                  <p>{edge.reasoning}</p>
                </div>
              </li>
            ))}
            {dateConflicts.map((conflict) => (
              <li key={`date-${conflict.subject}`}>
                <span className="reason-mark">!</span>
                <div>
                  <strong>{conflict.subject} · event date</strong>
                  <p>
                    {conflict.reasoning} Dates found: {conflict.dates.join(", ")}.
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {corroborated.length > 0 && (
        <div className="reasoning-block">
          <h4>Corroborated across clippings</h4>
          <ul className="reason-list">
            {corroborated.slice(0, 5).map((edge) => (
              <li key={edge.id}>
                <span className="reason-mark reason-mark-ok">✓</span>
                <div>
                  <strong>
                    {nameOf(edge.source)} · {edge.label} · {nameOf(edge.target)}
                  </strong>
                  <p>{edge.reasoning}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {corroborated.length === 0 && singleSource.length > 0 && (
        <div className="reasoning-block">
          <h4>Awaiting a second witness</h4>
          <p className="reasoning-hint">
            Every branch below is supported by one clipping. A second, independent clipping can
            corroborate it without overwriting the first.
          </p>
        </div>
      )}

      <div className="reasoning-block reasoning-method">
        <h4>Method</h4>
        <ol>
          {(reasoning.method || []).map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      </div>
    </section>
  );
}

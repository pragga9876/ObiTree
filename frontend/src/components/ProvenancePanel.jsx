import { formatAddress, explorerTxUrl } from "../lib/solana";

function statusLabel(status) {
  if (status === "VERIFIED") return "Sealed on Devnet";
  if (status === "FAILED") return "Attestation failed";
  return "Awaiting seal";
}

function StatusStamp({ status }) {
  const cls =
    status === "VERIFIED" ? "stamp" : status === "FAILED" ? "stamp stamp-failed" : "stamp stamp-pending";
  return <span className={cls}>{statusLabel(status)}</span>;
}

function SourceCard({ source, onOpenDocument, relation }) {
  const txUrl = explorerTxUrl(source.tx_signature);
  return (
    <li className="source-card">
      <div className="source-card-head">
        <span className="source-filename">{source.filename || "Clipping"}</span>
        <StatusStamp status={source.verification_status} />
      </div>
      {relation && <p className="source-relation">{relation}</p>}
      {source.evidence && (
        <blockquote className="source-evidence">&ldquo;{source.evidence}&rdquo;</blockquote>
      )}
      <div className="source-meta">
        <span className="mono">{formatAddress(source.wallet || "", 5)}</span>
        <span className="mono">rec {source.record_hash?.slice(0, 8) || "—"}</span>
      </div>
      <div className="source-actions">
        {onOpenDocument && source.document_id && (
          <button
            type="button"
            className="btn-link"
            onClick={() => onOpenDocument(source.document_id)}
          >
            Read this clipping
          </button>
        )}
        {txUrl && (
          <a className="source-link" href={txUrl} target="_blank" rel="noreferrer">
            View seal ↗
          </a>
        )}
      </div>
    </li>
  );
}

export default function ProvenancePanel({ graph, selection, onOpenDocument }) {
  const nodes = graph?.nodes || [];
  const edges = graph?.edges || [];
  const node = selection?.type === "node" ? nodes.find((item) => item.id === selection.id) : null;
  const edge = selection?.type === "edge" ? edges.find((item) => item.id === selection.id) : null;
  const nodeName = (id) => nodes.find((item) => item.id === id)?.name || id;

  if (!node && !edge) {
    return (
      <section className="provenance-panel">
        <div className="provenance-head">
          <span className="kicker">Provenance</span>
          <h3>Every line has a source</h3>
        </div>
        <p className="provenance-intro">
          Select a seal or a chain link in the family ledger. Orbitree will show the verbatim
          line, the clipping it came from, the contributing wallet and the Solana signature that
          sealed it.
        </p>
        <div className="provenance-empty-mark" aria-hidden="true">
          <span>❦</span>
        </div>
        <dl className="provenance-mini">
          <div>
            <dt>Names in ledger</dt>
            <dd>{nodes.length}</dd>
          </div>
          <div>
            <dt>Evidence links</dt>
            <dd>{edges.length}</dd>
          </div>
          <div>
            <dt>Clippings</dt>
            <dd>{graph?.stats?.clippings ?? 0}</dd>
          </div>
        </dl>
      </section>
    );
  }

  if (node) {
    const connected = edges.filter(
      (item) => item.source === node.id || item.target === node.id
    );
    const sourceMap = new Map();
    for (const item of connected) {
      const relation =
        item.source === node.id
          ? `${item.label} of ${nodeName(item.target)}`
          : `${nodeName(item.source)}'s ${item.label}`;
      for (const source of item.sources || []) {
        const key = `${source.document_id}-${source.evidence}`;
        if (!sourceMap.has(key)) sourceMap.set(key, { ...source, relation });
      }
    }
    const events = (graph.events || []).filter((event) => event.subject_id === node.id);

    return (
      <section className="provenance-panel">
        <div className="provenance-head">
          <span className="kicker">Person in the ledger</span>
          <h3>{node.name}</h3>
        </div>
        <div className="provenance-tags">
          {node.is_root && <span className="tag tag-oxblood">The deceased</span>}
          {(node.roles || []).map((role) => (
            <span key={role} className="tag">
              {role}
            </span>
          ))}
          {node.attested ? (
            <span className="tag tag-green">Sealed</span>
          ) : (
            <span className="tag tag-warning">Unsealed</span>
          )}
        </div>
        <p className="provenance-intro">
          Named in {node.source_count} clipping{node.source_count === 1 ? "" : "s"} and connected
          by {connected.length} evidence link{connected.length === 1 ? "" : "s"}.
        </p>

        {events.length > 0 && (
          <div className="provenance-events">
            <h4>Notices</h4>
            {events.map((event) => (
              <div key={event.subject_id} className="provenance-event">
                {event.events.map((item) => (
                  <div key={`${item.event}-${item.date}-${item.venue}`}>
                    <strong>{item.event || "Memorial notice"}</strong>
                    <span>
                      {[item.date, item.venue, item.address]
                        .filter((part) => part && part !== "Unknown")
                        .join(" · ")}
                    </span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}

        <h4 className="provenance-subhead">
          Source lines <span>{sourceMap.size}</span>
        </h4>
        {sourceMap.size > 0 ? (
          <ul className="source-list">
            {[...sourceMap.values()].map((source, index) => (
              <SourceCard
                key={`${source.document_id}-${index}`}
                source={source}
                relation={source.relation}
                onOpenDocument={onOpenDocument}
              />
            ))}
          </ul>
        ) : (
          <p className="provenance-intro">
            This name appears in the notices but no family relationship was attached to it.
          </p>
        )}
      </section>
    );
  }

  return (
    <section className="provenance-panel">
      <div className="provenance-head">
        <span className="kicker">Evidence link</span>
        <h3>
          {nodeName(edge.source)} <span className="provenance-arrow">—</span>{" "}
          {nodeName(edge.target)}
        </h3>
      </div>
      <div className="provenance-tags">
        <span className="tag tag-brass">{edge.label}</span>
        <span
          className={`tag ${
            edge.status === "conflict"
              ? "tag-oxblood"
              : edge.status === "corroborated"
              ? "tag-green"
              : "tag-warning"
          }`}
        >
          {edge.status === "corroborated"
            ? `${edge.corroboration} independent sources`
            : edge.status === "conflict"
            ? "conflicting readings"
            : "single source"}
        </span>
        {edge.attested && <span className="tag tag-green">Sealed</span>}
      </div>
      <p className="provenance-intro">{edge.reasoning}</p>
      <h4 className="provenance-subhead">
        Evidence <span>{edge.sources?.length || 0}</span>
      </h4>
      <ul className="source-list">
        {(edge.sources || []).map((source, index) => (
          <SourceCard
            key={`${source.document_id}-${index}`}
            source={source}
            relation={`${edge.label} of ${nodeName(edge.target)}`}
            onOpenDocument={onOpenDocument}
          />
        ))}
      </ul>
    </section>
  );
}

import { useCallback, useEffect, useMemo, useState } from "react";
import FamilyTree from "../components/FamilyTree";
import ReasoningPanel from "../components/ReasoningPanel";
import ProvenancePanel from "../components/ProvenancePanel";
import LedgerChain from "../components/LedgerChain";
import ClippingCard from "../components/ClippingCard";
import UploadClipping from "../components/UploadClipping";
import { getProject } from "../lib/api";
import { explorerAddressUrl, formatAddress } from "../lib/solana";

function formatFiled(value) {
  if (!value) return "Undated";
  const parsed = new Date(String(value).replace(" ", "T"));
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

export default function ProjectPage({ projectId, focusDocumentId, onHome }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [reloadToken, setReloadToken] = useState(0);
  const [tab, setTab] = useState("chronicle");
  const [selection, setSelection] = useState(null);
  const [attestDocId, setAttestDocId] = useState(null);
  const [shareCopied, setShareCopied] = useState(false);
  const [toast, setToast] = useState(null);

  const reload = useCallback(() => setReloadToken((token) => token + 1), []);

  useEffect(() => {
    let mounted = true;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    getProject(projectId)
      .then((payload) => {
        if (!mounted) return;
        setData(payload);
        setError(null);
      })
      .catch((err) => {
        if (mounted) setError(err.message);
      })
      .finally(() => mounted && setLoading(false));
    return () => {
      mounted = false;
    };
  }, [projectId, reloadToken]);

  useEffect(() => {
    if (!focusDocumentId) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTab("clippings");
    setAttestDocId(focusDocumentId);
    window.setTimeout(() => {
      document
        .getElementById(`clipping-${focusDocumentId}`)
        ?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 500);
  }, [focusDocumentId, data]);

  const shareUrl = useMemo(
    () => `${window.location.origin}${window.location.pathname}#/memorial/${projectId}`,
    [projectId]
  );

  const contributors = useMemo(() => {
    const map = new Map();
    for (const doc of data?.documents || []) {
      const attests = (doc.attestations || []).filter((item) => item.verified);
      const wallets = new Set(attests.map((item) => item.wallet));
      if (doc.uploader_wallet) wallets.add(doc.uploader_wallet);
      for (const wallet of wallets) {
        const entry = map.get(wallet) || { wallet, uploads: 0, attestations: 0 };
        if (doc.uploader_wallet === wallet) entry.uploads += 1;
        entry.attestations += attests.filter((item) => item.wallet === wallet).length;
        map.set(wallet, entry);
      }
    }
    return [...map.values()].sort(
      (a, b) => b.attestations - a.attestations || b.uploads - a.uploads
    );
  }, [data]);

  const showToast = (text) => {
    setToast(text);
    window.setTimeout(() => setToast(null), 2400);
  };

  const copyShare = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setShareCopied(true);
      showToast("Share link copied.");
      window.setTimeout(() => setShareCopied(false), 2000);
    } catch {
      showToast("Copy failed. Select the link and copy it manually.");
    }
  };

  const goContribute = () => {
    setTab("clippings");
    window.setTimeout(() => {
      document.getElementById("contribute")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 120);
  };

  const openDocument = (documentId) => {
    setTab("clippings");
    setAttestDocId(null);
    window.setTimeout(() => {
      document
        .getElementById(`clipping-${documentId}`)
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 150);
  };

  const handleUploaded = (upload) => {
    setAttestDocId(upload.document_id);
    setTab("clippings");
    reload();
    showToast("Record extracted. Scroll to inspect the scan and the JSON.");
    window.setTimeout(() => {
      document
        .getElementById(`clipping-${upload.document_id}`)
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 700);
  };

  const handleSealed = () => {
    reload();
    showToast("Witness attestation recorded.");
  };

  if (loading && !data) {
    return (
      <main className="project-page">
        <div className="page-loading">
          <p>Opening the family record…</p>
        </div>
      </main>
    );
  }

  if (error && !data) {
    return (
      <main className="project-page">
        <div className="project-error">
          <h1>This record could not be found.</h1>
          <p>{error}</p>
          <button type="button" className="btn btn-ink" onClick={onHome}>
            Return home
          </button>
        </div>
      </main>
    );
  }

  const project = data.project;
  const graph = data.graph;
  const stats = data.stats;
  const documents = data.documents || [];
  const activeSelection =
    selection || (graph?.root_id ? { type: "node", id: graph.root_id } : null);

  return (
    <main className="project-page">
      <header className="project-header">
        <div className="project-header-main">
          <p className="project-kicker">Family record · opened {formatFiled(project.created_at)}</p>
          <h1>{project.title}</h1>
          <p className="project-subject">In memory of {project.subject_name}</p>
          <p className="project-description">{project.description}</p>
        </div>

        <div className="project-actions">
          <button type="button" className="btn btn-ink" onClick={goContribute}>
            Add a clipping
          </button>
          <button type="button" className="btn btn-ghost" onClick={copyShare}>
            {shareCopied ? "Link copied ✓" : "Copy share link"}
          </button>
        </div>
      </header>

      <div className="project-stats">
        <div className="project-stat">
          <strong>{stats.clippings}</strong>
          <span>Clippings</span>
        </div>
        <div className="project-stat">
          <strong>{stats.contributors}</strong>
          <span>Contributors</span>
        </div>
        <div className="project-stat">
          <strong>{stats.attestations}</strong>
          <span>Attestations</span>
        </div>
        <div className="project-stat">
          <strong>{stats.sealed_documents ?? stats.attestations}</strong>
          <span>Sealed records</span>
        </div>
        <div className="project-stat">
          <strong>{stats.relationships}</strong>
          <span>Relationships</span>
        </div>
        <div className="project-stat project-stat-confidence">
          <strong>{stats.confidence}%</strong>
          <span>Confidence</span>
        </div>
      </div>

      <section className="record-share">
        <div className="record-share-copy">
          <h3>Share this record with the second witness</h3>
          <p>
            Contributor two opens this link with a different wallet and attests the same canonical
            record hash. Both transactions stay public.
          </p>
          <code>{shareUrl}</code>
        </div>
        <button type="button" className="btn btn-cream" onClick={copyShare}>
          {shareCopied ? "Copied ✓" : "Copy link"}
        </button>
      </section>

      <section className="contributors-panel">
        <div className="contributors-head">
          <div>
            <h3>Contributors</h3>
            <p>Every wallet below acted independently.</p>
          </div>
          <span className="contributors-count">{contributors.length} wallets</span>
        </div>
        {contributors.length > 0 ? (
          <div className="contributors-list">
            {contributors.map((contributor) => (
              <div key={contributor.wallet} className="contributor-item">
                <div className="contributor-wallet">
                  <span className="dot" />
                  <strong>{formatAddress(contributor.wallet, 6)}</strong>
                </div>
                <span className="contributor-activity">
                  {contributor.uploads} upload{contributor.uploads === 1 ? "" : "s"} ·{" "}
                  {contributor.attestations} attestation
                  {contributor.attestations === 1 ? "" : "s"}
                </span>
                {explorerAddressUrl(contributor.wallet) && (
                  <a
                    className="btn-link"
                    href={explorerAddressUrl(contributor.wallet)}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Solana Explorer ↗
                  </a>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="contributors-empty">
            No wallet has contributed yet. Connect a wallet when you are ready to attest.
          </p>
        )}
      </section>

      <div className="project-tabs" role="tablist" aria-label="Record sections">
        <button
          type="button"
          role="tab"
          aria-selected={tab === "chronicle"}
          className={`project-tab ${tab === "chronicle" ? "is-active" : ""}`}
          onClick={() => setTab("chronicle")}
        >
          Family Tree
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "clippings"}
          className={`project-tab ${tab === "clippings" ? "is-active" : ""}`}
          onClick={() => setTab("clippings")}
        >
          Records &amp; Attestations <span>{documents.length}</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "ledger"}
          className={`project-tab ${tab === "ledger" ? "is-active" : ""}`}
          onClick={() => setTab("ledger")}
        >
          Chain Ledger <span>{data.ledger?.length || 0}</span>
        </button>
      </div>

      {tab === "chronicle" && (
        <div className="chronicle-stack">
          <FamilyTree graph={graph} selection={activeSelection} onSelect={setSelection} />

          {graph.events?.length > 0 && (
            <section className="notices-section">
              <h3>Where and when the family gathered</h3>
              <div className="notice-grid">
                {graph.events.map((group) => (
                  <article key={group.subject_id} className="notice-card">
                    <h4>{group.subject}</h4>
                    {group.events.map((event) => (
                      <div
                        key={`${event.event}-${event.date}-${event.venue}`}
                        className="notice-item"
                      >
                        <strong>{event.event || "Memorial notice"}</strong>
                        <span>
                          {[event.date, event.venue, event.address]
                            .filter((part) => part && part !== "Unknown")
                            .join(" · ") || "Details not printed"}
                        </span>
                        <em>
                          {event.sources.length} source{event.sources.length === 1 ? "" : "s"}
                        </em>
                      </div>
                    ))}
                  </article>
                ))}
              </div>
            </section>
          )}

          <div className="chronicle-insights">
            <ReasoningPanel graph={graph} stats={stats} />
            <ProvenancePanel
              graph={graph}
              selection={activeSelection}
              onOpenDocument={openDocument}
            />
          </div>
        </div>
      )}

      {tab === "clippings" && (
        <div className="clippings-section">
          <section className="contribute-panel" id="contribute">
            <UploadClipping
              projectId={project.id}
              onSuccess={handleUploaded}
              title="Upload another clipping"
              subtitle="A second contributor can upload from their own wallet. Extraction works without a wallet; attestation comes next."
            />
          </section>

          <div className="clippings-list">
            {documents.length === 0 && (
              <div className="archive-empty">
                <h3>No clippings on file.</h3>
              </div>
            )}
            {[...documents].reverse().map((document, index) => (
              <div key={document.document_id} id={`clipping-${document.document_id}`}>
                <ClippingCard
                  document={document}
                  index={documents.length - 1 - index}
                  onSealed={handleSealed}
                  defaultAttestOpen={attestDocId === document.document_id}
                  shareUrl={shareUrl}
                />
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === "ledger" && (
        <LedgerChain ledger={data.ledger || []} onOpenDocument={openDocument} />
      )}

      {toast && <div className="toast">{toast}</div>}
    </main>
  );
}

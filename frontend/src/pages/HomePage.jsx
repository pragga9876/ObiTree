import { useEffect, useMemo, useState } from "react";
import UploadClipping from "../components/UploadClipping";
import { checkHealth, listProjects } from "../lib/api";

function formatDate(value) {
  if (!value) return "Undated";
  const parsed = new Date(String(value).replace(" ", "T"));
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function projectMonogram(project) {
  const source = project.subject_name || project.title || "O";
  const words = source.replace(/\([^)]*\)/g, "").trim().split(/\s+/);
  if (words.length === 1) return words[0].slice(0, 1).toUpperCase();
  return (words[0][0] + words[words.length - 1][0]).toUpperCase();
}

export default function HomePage({ onOpenProject }) {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [health, setHealth] = useState(null);
  const [archiveError, setArchiveError] = useState(null);

  useEffect(() => {
    let mounted = true;
    checkHealth()
      .then((data) => mounted && setHealth(data))
      .catch(() => mounted && setHealth({ status: "error" }));

    listProjects()
      .then((data) => {
        if (!mounted) return;
        setProjects(data);
        setArchiveError(null);
      })
      .catch((err) => mounted && setArchiveError(err.message))
      .finally(() => mounted && setLoading(false));

    return () => {
      mounted = false;
    };
  }, []);

  const totals = useMemo(
    () =>
      projects.reduce(
        (acc, project) => ({
          clippings: acc.clippings + (project.clippings || 0),
          contributors: acc.contributors + (project.contributors || 0),
          attestations: acc.attestations + (project.attestations || 0),
        }),
        { clippings: 0, contributors: 0, attestations: 0 }
      ),
    [projects]
  );

  const apiOnline = health?.status === "ok";

  return (
    <main className="home-page">
      <section className="home-hero">
        <p className="home-eyebrow">Obituaries, reconstructed on-chain</p>
        <h1>One family record. Two independent witnesses.</h1>
        <p className="home-deck">
          Orbitree reads a printed obituary, reconstructs the family record, and hashes both the
          original scan and the extracted genealogy. Wallet one attests. Wallet two attests the
          same record independently. Both signatures are public on Solana.
        </p>
        <div className="home-hero-facts">
          <span>No wallet needed to read a clipping</span>
          <span>A wallet is only required to attest</span>
          <span>Every claim keeps its source</span>
        </div>
      </section>

      <section className="home-workflow" aria-label="How Orbitree works">
        <article className="flow-step">
          <span className="flow-number">1</span>
          <h3>Upload the clipping</h3>
          <p>The scan is stored, read and hashed. No wallet is needed for this step.</p>
        </article>
        <article className="flow-step">
          <span className="flow-number">2</span>
          <h3>Get the record</h3>
          <p>The family tree, extracted JSON, document hash and canonical record hash appear together.</p>
        </article>
        <article className="flow-step">
          <span className="flow-number">3</span>
          <h3>Witness one attests</h3>
          <p>The first wallet signs a Solana memo carrying the record hash.</p>
        </article>
        <article className="flow-step">
          <span className="flow-number">4</span>
          <h3>Witness two attests</h3>
          <p>A second wallet opens the same record and signs its own independent transaction.</p>
        </article>
      </section>

      <section className="home-start">
        <div className="home-start-copy">
          <h2>Start a family record</h2>
          <p>
            Upload an obituary photograph, scan or screenshot. Orbitree will show you the image
            beside the structured record so every extracted claim can be checked against the
            page.
          </p>
          <div className="home-network-card">
            <div className="home-network-head">
              <span className={`dot ${apiOnline ? "dot-pulse" : "dot-off"}`} />
              <strong>{apiOnline ? "Backend connected" : "Connecting to the backend"}</strong>
            </div>
            <dl>
              <div>
                <dt>Network</dt>
                <dd>Solana Devnet</dd>
              </div>
              <div>
                <dt>Hashing</dt>
                <dd>SHA-256</dd>
              </div>
              <div>
                <dt>Memo program</dt>
                <dd className="mono">MemoSq4…fcHr</dd>
              </div>
            </dl>
          </div>
        </div>

        <UploadClipping
          onSuccess={(data) => onOpenProject(data.project.id, data.document_id)}
        />
      </section>

      <section className="archive-section" id="archive">
        <div className="archive-head">
          <div>
            <h2>Family records</h2>
            <p className="archive-sub">
              {totals.clippings} clippings · {totals.contributors} contributors ·{" "}
              {totals.attestations} wallet attestations
            </p>
          </div>
          <span className="archive-count">
            {projects.length} {projects.length === 1 ? "record" : "records"}
          </span>
        </div>

        {loading && (
          <div className="archive-empty">
            <p>Opening the archive…</p>
          </div>
        )}

        {!loading && archiveError && (
          <div className="notice notice-error">
            The archive could not be reached. {archiveError}
          </div>
        )}

        {!loading && !archiveError && projects.length === 0 && (
          <div className="archive-empty">
            <h3>The archive is empty.</h3>
            <p>Upload an obituary above and its family record will appear here.</p>
          </div>
        )}

        {!loading && projects.length > 0 && (
          <div className="archive-grid">
            {projects.map((project, index) => (
              <button
                key={project.id}
                type="button"
                className="project-card"
                onClick={() => onOpenProject(project.id)}
                style={{ animationDelay: `${index * 60}ms` }}
              >
                <div className="project-card-top">
                  <span className="project-monogram">{projectMonogram(project)}</span>
                  <span className="project-date">{formatDate(project.created_at)}</span>
                </div>
                <h3>{project.title}</h3>
                <p className="project-subject">{project.subject_name}</p>
                <div className="project-card-stats">
                  <span>{project.clippings} clippings</span>
                  <span>{project.contributors} contributors</span>
                  <span>{project.attestations} attestations</span>
                </div>
                <span className="project-open">
                  Open the record <span aria-hidden="true">→</span>
                </span>
              </button>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}

import { explorerTxUrl, formatAddress } from "../lib/solana";

function short(value, size = 20) {
  if (!value || value === "-") return "—";
  return value.slice(0, size);
}

export default function LedgerChain({ ledger = [], onOpenDocument }) {
  if (!ledger.length) {
    return (
      <div className="archive-empty">
        <h3>No clippings have been filed yet.</h3>
        <p>The first page becomes the genesis block of this record.</p>
      </div>
    );
  }

  return (
    <div className="ledger-chain">
      <div className="ledger-intro">
        <h3>Each record is a block</h3>
        <p>
          A block carries the original document hash, the canonical record hash and the hash of
          the block before it. Every witness signature is listed with its own Solana transaction.
        </p>
      </div>

      <div className="ledger-track">
        {ledger.map((block, index) => {
          const attestations = block.attestations || [];
          const verified = attestations.filter(
            (item) => item.verified || item.verification_status === "VERIFIED"
          );
          return (
            <article
              key={block.document_id}
              className={`ledger-block ${block.sealed ? "is-sealed" : ""} ${
                index === 0 ? "is-genesis" : ""
              }`}
            >
              <div className="ledger-rail" aria-hidden="true">
                <span className="ledger-node">{String(index + 1).padStart(2, "0")}</span>
                {index < ledger.length - 1 && <span className="ledger-link" />}
              </div>

              <div className="ledger-block-body">
                <header className="ledger-block-head">
                  <div>
                    <span className="block-index">
                      {index === 0 ? "Genesis block" : `Block ${String(index + 1).padStart(2, "0")}`}
                    </span>
                    <h4>{block.filename}</h4>
                  </div>
                  <span className={`block-badge ${verified.length >= 2 ? "is-complete" : ""}`}>
                    {verified.length} witness{verified.length === 1 ? "" : "es"}
                  </span>
                </header>

                <dl className="block-hashes">
                  <div>
                    <dt>Document hash</dt>
                    <dd className="mono">{short(block.file_hash, 28)}</dd>
                  </div>
                  <div>
                    <dt>Canonical record hash</dt>
                    <dd className="mono">{short(block.record_hash, 28)}</dd>
                  </div>
                  <div>
                    <dt>Previous hash</dt>
                    <dd className="mono">{short(block.previous_hash, 28)}</dd>
                  </div>
                </dl>

                <div className="block-witness-list">
                  {verified.length > 0 ? (
                    verified.map((attestation) => {
                      const txUrl = explorerTxUrl(attestation.tx_signature);
                      return (
                        <div key={attestation.tx_signature} className="block-witness">
                          <div className="block-witness-wallet">
                            <span className="dot" />
                            <strong>{formatAddress(attestation.wallet, 6)}</strong>
                            <span className="block-witness-state">Verified on Devnet</span>
                          </div>
                          <code className="block-signature">
                            {attestation.tx_signature}
                          </code>
                          {txUrl ? (
                            <a
                              className="btn-link"
                              href={txUrl}
                              target="_blank"
                              rel="noreferrer"
                            >
                              Solana Explorer ↗
                            </a>
                          ) : (
                            <span className="block-sim">Simulated attestation</span>
                          )}
                        </div>
                      );
                    })
                  ) : (
                    <div className="block-witness block-witness-empty">
                      No witness yet. Open the record to add the first attestation.
                    </div>
                  )}
                </div>

                <footer className="block-footer">
                  <span className="block-date">{block.created_at || "Undated"}</span>
                  {onOpenDocument && (
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => onOpenDocument(block.document_id)}
                    >
                      Open record
                    </button>
                  )}
                </footer>
              </div>
            </article>
          );
        })}
      </div>

      <div className="ledger-foot">
        <span className="dot dot-pulse" />
        Solana Devnet · Memo Program · {ledger.length} block
        {ledger.length === 1 ? "" : "s"} in this record
      </div>
    </div>
  );
}

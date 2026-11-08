import { useState } from "react";
import { useWallet } from "@solana/wallet-adapter-react";
import { useWalletModal } from "@solana/wallet-adapter-react-ui";
import AttestationPanel from "./AttestationPanel";
import { fileUrl, getDocument } from "../lib/api";
import { explorerTxUrl, formatAddress } from "../lib/solana";

function readablePredicate(predicate) {
  return String(predicate || "related to").replace(/_/g, " ");
}

function uniqueFacts(extracted = []) {
  const seen = new Set();
  return extracted.filter((item) => {
    const key = `${item.event}|${item.event_date}|${item.event_venue}|${item.event_address}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function WitnessSlot({ number, attestation, onAttest, onConnect, onShare, shareCopied, canAttest, walletSigned, onDisconnect }) {
  if (attestation) {
    const txUrl = explorerTxUrl(attestation.tx_signature);
    return (
      <div className="witness-slot is-sealed">
        <div className="witness-slot-top">
          <span className="witness-number">Witness {number}</span>
          <span className="witness-check">✓</span>
        </div>
        <strong className="witness-wallet">{formatAddress(attestation.wallet, 6)}</strong>
        <span className="witness-verified">Verified on Solana Devnet</span>
        <span className="witness-signature">
          {attestation.tx_signature?.startsWith("sim_")
            ? "Simulated transaction"
            : `${attestation.tx_signature?.slice(0, 18)}…`}
        </span>
        {txUrl ? (
          <a className="witness-link" href={txUrl} target="_blank" rel="noreferrer">
            Solana Explorer ↗
          </a>
        ) : (
          <span className="witness-sim">Rehearsal signature only</span>
        )}
      </div>
    );
  }

  return (
    <div className="witness-slot is-empty">
      <div className="witness-slot-top">
        <span className="witness-number">Witness {number}</span>
        <span className="witness-pending">Waiting</span>
      </div>
      <p>
        {number === 1
          ? "The first wallet signs the record hash."
          : "A second, different wallet must sign the same record."}
      </p>
      {walletSigned ? (
        <button type="button" className="btn btn-ghost btn-sm" onClick={onDisconnect}>
          This wallet already signed — switch wallet
        </button>
      ) : canAttest ? (
        <button type="button" className="btn btn-oxblood btn-sm" onClick={onAttest}>
          Attest with this wallet
        </button>
      ) : (
        <button type="button" className="btn btn-ink btn-sm" onClick={onConnect}>
          Connect wallet to attest
        </button>
      )}
      <button type="button" className="witness-share" onClick={onShare}>
        {shareCopied ? "Share link copied ✓" : "Copy share link"}
      </button>
    </div>
  );
}

export default function ClippingCard({
  document,
  index,
  onSealed,
  defaultAttestOpen = false,
  shareUrl,
}) {
  const { publicKey, disconnect } = useWallet();
  const { setVisible } = useWalletModal();
  const [showJson, setShowJson] = useState(true);
  const [showOcr, setShowOcr] = useState(false);
  const [rawOcr, setRawOcr] = useState(null);
  const [ocrError, setOcrError] = useState(null);
  const [ocrLoading, setOcrLoading] = useState(false);
  const [attestOverride, setAttestOverride] = useState(null);
  const [copied, setCopied] = useState(null);

  const address = publicKey?.toBase58();
  const attestations = document.attestations?.length
    ? document.attestations
    : document.tx_signature
    ? [
        {
          wallet: document.wallet,
          tx_signature: document.tx_signature,
          verified: document.verification_status === "VERIFIED",
          verification_status: document.verification_status,
        },
      ]
    : [];
  const sealed = attestations.filter((item) => item.verified);
  const walletSigned = sealed.some((item) => item.wallet === address);
  const showAttest = (attestOverride ?? defaultAttestOpen) && !walletSigned;
  const slots = [...sealed];
  while (slots.length < 2) slots.push(null);

  const copyText = (key, value) => {
    navigator.clipboard?.writeText(value);
    setCopied(key);
    window.setTimeout(() => setCopied(null), 1600);
  };

  const toggleOcr = async () => {
    const next = !showOcr;
    setShowOcr(next);
    if (next && rawOcr === null && !ocrLoading) {
      setOcrLoading(true);
      setOcrError(null);
      try {
        const detail = await getDocument(document.document_id);
        setRawOcr(detail.raw_ocr_text || "(No text was extracted.)");
      } catch (err) {
        setOcrError(err.message);
      } finally {
        setOcrLoading(false);
      }
    }
  };

  const canonical = document.canonical_record || {};
  const claims = canonical.claims || [];
  const facts = uniqueFacts(document.extracted_data || []);
  const event = facts[0] || null;
  const image = fileUrl(document.image_url);
  const isPdf = /\.pdf$/i.test(document.filename || "");

  return (
    <article className={`record-card ${sealed.length ? "has-witness" : ""}`}>
      <header className="record-head">
        <div>
          <span className="record-number">Record {String(index + 1).padStart(2, "0")}</span>
          <h3>{document.filename}</h3>
        </div>
        <span className={`record-status ${sealed.length >= 2 ? "is-complete" : ""}`}>
          {sealed.length} / 2 witnesses
        </span>
      </header>

      <div className="record-grid">
        <div className="record-scan">
          {image ? (
            isPdf ? (
              <object className="record-pdf" data={image} type="application/pdf">
                <a href={image} target="_blank" rel="noreferrer">
                  Open the original PDF
                </a>
              </object>
            ) : (
              <a href={image} target="_blank" rel="noreferrer" className="record-image-link">
                <img src={image} alt={`Original clipping: ${document.filename}`} />
              </a>
            )
          ) : (
            <div className="record-no-scan">The original scan is not available.</div>
          )}
          <div className="record-scan-foot">
            <span>Original clipping</span>
            {image && (
              <a href={image} target="_blank" rel="noreferrer">
                Open full size ↗
              </a>
            )}
          </div>
        </div>

        <div className="record-extraction">
          <div className="record-hashes">
            <div className="hash-row">
              <span className="hash-label">Original document hash · SHA-256</span>
              <code>{document.file_hash || "—"}</code>
              <button
                type="button"
                className="hash-copy"
                onClick={() => copyText("file", document.file_hash)}
              >
                {copied === "file" ? "Copied ✓" : "Copy"}
              </button>
            </div>
            <div className="hash-row">
              <span className="hash-label">Canonical record hash · SHA-256</span>
              <code>{document.record_hash || "—"}</code>
              <button
                type="button"
                className="hash-copy"
                onClick={() => copyText("record", document.record_hash)}
              >
                {copied === "record" ? "Copied ✓" : "Copy"}
              </button>
            </div>
          </div>

          {event && (
            <div className="record-event">
              <div>
                <span>Notice</span>
                <strong>{event.event || "Memorial notice"}</strong>
              </div>
              <div>
                <span>Date</span>
                <strong>{event.event_date || "Unknown"}</strong>
              </div>
              <div>
                <span>Venue</span>
                <strong>{event.event_venue || "Unknown"}</strong>
              </div>
            </div>
          )}

          <div className="record-claims">
            <h4>Extracted family record</h4>
            {claims.length > 0 ? (
              <ul>
                {claims.map((claim, claimIndex) => (
                  <li key={`${claim.subject}-${claim.predicate}-${claimIndex}`}>
                    <div className="claim-line">
                      <strong>{claim.subject}</strong>
                      <span className="claim-predicate">{readablePredicate(claim.predicate)}</span>
                      <strong>{claim.object}</strong>
                    </div>
                    {claim.evidence && (
                      <blockquote className="claim-quote">&ldquo;{claim.evidence}&rdquo;</blockquote>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="record-empty-copy">
                No person-to-person relationships were extracted from this page. The notice itself
                is still archived.
              </p>
            )}
          </div>

          <div className="record-json-head">
            <h4>Extraction JSON</h4>
            <button type="button" className="btn-link" onClick={() => setShowJson((value) => !value)}>
              {showJson ? "Hide JSON" : "Show JSON"}
            </button>
          </div>
          {showJson && (
            <pre className="record-json">{JSON.stringify(canonical, null, 2)}</pre>
          )}
        </div>
      </div>

      <section className="witness-section">
        <div className="witness-head">
          <div>
            <h4>Independent witnesses</h4>
            <p>Each wallet signs the same canonical record hash in its own Solana transaction.</p>
          </div>
          {sealed.length >= 2 && <span className="witness-complete">Two witnesses recorded</span>}
        </div>

        <div className="witness-slots">
          {slots.map((attestation, slotIndex) => (
            <WitnessSlot
              key={attestation?.tx_signature || `slot-${slotIndex}`}
              number={slotIndex + 1}
              attestation={attestation}
              canAttest={Boolean(address)}
              walletSigned={walletSigned}
              onDisconnect={() => disconnect()}
              onConnect={() => setVisible(true)}
              onAttest={() => setAttestOverride(true)}
              onShare={() => copyText("share", shareUrl || window.location.href)}
              shareCopied={copied === "share"}
            />
          ))}
        </div>

        {sealed.length < 2 && (
          <p className="witness-hint">
            {sealed.length === 0
              ? "Connect the first wallet to create the first attestation."
              : "Open this record from a second wallet to add the second independent attestation."}
          </p>
        )}

        {showAttest && (
          <AttestationPanel document={document} onSealed={onSealed} />
        )}
      </section>

      <footer className="record-tools">
        <button type="button" className="btn-link" onClick={toggleOcr}>
          {showOcr ? "Hide raw OCR" : "Show raw OCR"}
        </button>
        {document.model_name && <span>Extracted with {document.model_name}</span>}
        {document.uploader_wallet && (
          <span>Uploaded by {formatAddress(document.uploader_wallet, 5)}</span>
        )}
        <span>{document.created_at || "Undated"}</span>
      </footer>

      {showOcr && (
        <div className="record-ocr">
          {ocrLoading && <p className="record-empty-copy">Loading the transcript…</p>}
          {ocrError && <div className="notice notice-error">{ocrError}</div>}
          {!ocrLoading && !ocrError && <pre>{rawOcr}</pre>}
        </div>
      )}
    </article>
  );
}

import { useState, useEffect, useCallback } from 'react';
import { useConnection, useWallet } from '@solana/wallet-adapter-react';
import { buildMemoTransaction } from '../lib/solana';
import { submitAttestation } from '../lib/api';

export default function AttestationCard({ documentData }) {
  const { connection } = useConnection();
  const { publicKey, sendTransaction, connected } = useWallet();

  const [balance, setBalance] = useState(null);
  const [signing, setSigning] = useState(false);
  const [attestationResult, setAttestationResult] = useState(null);
  const [error, setError] = useState(null);
  const [statusMessage, setStatusMessage] = useState('');
  const [copied, setCopied] = useState(false);
  const [activeTab, setActiveTab] = useState('extracted'); // 'extracted' | 'canonical' | 'claims' | 'memo' | 'ocr'

  // Fetch Devnet balance
  useEffect(() => {
    let isMounted = true;
    if (connected && publicKey && connection) {
      connection
        .getBalance(publicKey, 'confirmed')
        .then((lamports) => {
          if (isMounted) setBalance(lamports / 1e9);
        })
        .catch((err) => console.warn('Failed to fetch balance:', err));
    }
    return () => {
      isMounted = false;
    };
  }, [connected, publicKey, connection]);

  const refreshBalance = useCallback(async () => {
    if (connected && publicKey && connection) {
      try {
        const lamports = await connection.getBalance(publicKey, 'confirmed');
        setBalance(lamports / 1e9);
      } catch (err) {
        console.warn('Failed to fetch balance:', err);
      }
    }
  }, [connected, publicKey, connection]);

  if (!documentData) return null;

  const {
    document_id,
    file_hash,
    record_hash,
    canonical_record,
    memo_payload,
    raw_ocr_text,
    model_name,
    api_key_failed,
  } = documentData;

  const extractedList = documentData.extracted_data || canonical_record?.extracted_data || [];

  const copyAddress = () => {
    if (publicKey) {
      navigator.clipboard.writeText(publicKey.toBase58());
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const copyCanonicalJson = () => {
    navigator.clipboard.writeText(JSON.stringify(canonical_record, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const copyExtractedJson = () => {
    navigator.clipboard.writeText(JSON.stringify(extractedList, null, 4));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleSignAndAttest = async () => {
    if (!connected || !publicKey) {
      setError('Please connect your Solana wallet first.');
      return;
    }

    setSigning(true);
    setError(null);
    setStatusMessage('Preparing Solana Memo transaction...');

    try {
      // 1. Fetch latest blockhash from Devnet
      const { blockhash } = await connection.getLatestBlockhash('confirmed');

      // 2. Build Transaction with PAPERROOTS Memo instruction
      const transaction = buildMemoTransaction(memo_payload, publicKey, blockhash);

      // 3. Prompt connected wallet to sign and broadcast
      setStatusMessage('Please click "Approve" in your wallet popup...');
      const signature = await sendTransaction(transaction, connection);

      setStatusMessage(`Transaction sent: ${signature.slice(0, 8)}... Waiting for Devnet confirmation...`);
      await connection.confirmTransaction(signature, 'confirmed');

      // 4. Submit signature to backend for independent Solana RPC verification
      setStatusMessage('Verifying transaction on Solana RPC...');
      const verificationResponse = await submitAttestation({
        documentId: document_id,
        version: 1,
        transactionSignature: signature,
        wallet: publicKey.toBase58(),
        network: 'devnet',
      });

      setAttestationResult(verificationResponse);
      setStatusMessage('Attestation verified successfully on Solana Devnet!');
      refreshBalance();
    } catch (err) {
      console.error('Attestation error:', err);
      setError(
        err?.message?.includes('0x1')
          ? 'Insufficient Devnet SOL to pay transaction fee. Please fund your wallet via the faucet below.'
          : err?.message || 'Transaction was rejected or failed.'
      );
    } finally {
      setSigning(false);
    }
  };

  const handleDemoAttest = async () => {
    setSigning(true);
    setError(null);
    setStatusMessage('Attesting via PaperRoots Devnet Demo Signer...');

    try {
      const demoSig = `sim_paperroots_${document_id}_${Date.now().toString(36)}`;
      const verificationResponse = await submitAttestation({
        documentId: document_id,
        version: 1,
        transactionSignature: demoSig,
        wallet: publicKey ? publicKey.toBase58() : 'DemoContributorWallet11111111111111111111',
        network: 'devnet',
      });

      setAttestationResult(verificationResponse);
      setStatusMessage('Demo attestation verified and registered in PaperRoots SQLite database!');
    } catch (err) {
      setError(err?.message || 'Demo attestation failed.');
    } finally {
      setSigning(false);
    }
  };

  const isZeroBalance = balance !== null && balance === 0;

  return (
    <div className="attestation-card">
      <div className="card-header">
        <div>
          <h2 className="card-title">Document Ready for Attestation</h2>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginTop: '4px' }}>
            <span className="doc-id-pill">ID: {document_id}</span>
            {api_key_failed && (
              <span
                className="doc-id-pill"
                style={{ background: '#fef3c7', color: '#92400e', borderColor: '#fde68a' }}
                title={model_name || 'Gemini API key failed or is missing'}
              >
                Offline Engine
              </span>
            )}
          </div>
        </div>
        <span className="badge-ready">READY_FOR_ATTESTATION</span>
      </div>

      {/* Two-Hash System */}
      <div className="hashes-grid">
        <div className="hash-box">
          <span className="hash-label">1. File SHA-256 (Original Document Bytes)</span>
          <code className="hash-value" title={file_hash}>{file_hash}</code>
        </div>
        <div className="hash-box">
          <span className="hash-label">2. Record SHA-256 (Canonical Knowledge Hash)</span>
          <code className="hash-value highlight" title={record_hash}>{record_hash}</code>
        </div>
      </div>

      {/* View Tabs */}
      <div className="tab-bar">
        <button
          type="button"
          className={`tab-btn ${activeTab === 'extracted' ? 'active' : ''}`}
          onClick={() => setActiveTab('extracted')}
        >
          Final Extracted Information (JSON)
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === 'canonical' ? 'active' : ''}`}
          onClick={() => setActiveTab('canonical')}
        >
          Canonical Record
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === 'claims' ? 'active' : ''}`}
          onClick={() => setActiveTab('claims')}
        >
          Claims Graph ({canonical_record?.claims?.length || 0})
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === 'memo' ? 'active' : ''}`}
          onClick={() => setActiveTab('memo')}
        >
          Solana Memo
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === 'ocr' ? 'active' : ''}`}
          onClick={() => setActiveTab('ocr')}
        >
          Raw OCR Text
        </button>
      </div>

      {/* Tab 1: Final Extracted Information (JSON) matching requested schema */}
      {activeTab === 'extracted' && (
        <div className="tab-pane">
          <div className="pane-header">
            <span className="sub-title">Final Extracted Information (JSON)</span>
            <button type="button" className="btn btn-sm btn-outline" onClick={copyExtractedJson}>
              {copied ? '✓ Copied' : 'Copy JSON'}
            </button>
          </div>
          <pre className="code-box">
            {JSON.stringify(extractedList, null, 4)}
          </pre>
        </div>
      )}

      {/* Tab 2: Canonical JSON Record Envelope */}
      {activeTab === 'canonical' && (
        <div className="tab-pane">
          <div className="pane-header">
            <span className="sub-title">Deterministic Canonical Record Format</span>
            <button type="button" className="btn btn-sm btn-outline" onClick={copyCanonicalJson}>
              {copied ? '✓ Copied' : 'Copy JSON'}
            </button>
          </div>
          <pre className="code-box">
            {JSON.stringify(canonical_record, null, 2)}
          </pre>
        </div>
      )}

      {/* Tab 2: Visual Claims Graph */}
      {activeTab === 'claims' && (
        <div className="tab-pane">
          <span className="sub-title">Extracted Genealogical Triples</span>
          {canonical_record?.claims?.length > 0 ? (
            <div className="claims-list">
              {canonical_record.claims.map((claim, idx) => (
                <div key={idx} className="claim-item">
                  <div className="claim-triple">
                    <strong>{claim.subject}</strong>
                    <span className="predicate-tag">── {claim.predicate} ──►</span>
                    <strong>{claim.object}</strong>
                  </div>
                  {claim.evidence && (
                    <div className="claim-evidence">
                      <span className="evidence-quote">“{claim.evidence}”</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p className="empty-text">No structured claims extracted.</p>
          )}
        </div>
      )}

      {/* Tab 3: Solana Memo */}
      {activeTab === 'memo' && (
        <div className="tab-pane">
          <span className="sub-title">PAPERROOTS|1 Solana Memo Instruction</span>
          <pre className="code-box memo-box">{memo_payload}</pre>
        </div>
      )}

      {/* Tab 4: Raw OCR Text */}
      {activeTab === 'ocr' && (
        <div className="tab-pane">
          <span className="sub-title">Preprocessed OCR Text Output</span>
          <pre className="code-box">{raw_ocr_text || '(No text extracted)'}</pre>
        </div>
      )}

      {/* Balance notice when connected */}
      {connected && (
        <div className={`balance-box ${isZeroBalance ? 'balance-warning' : ''}`}>
          <div className="balance-info">
            <span>Devnet Wallet Balance:</span>
            <strong>{balance !== null ? `${balance.toFixed(4)} SOL` : 'Checking...'}</strong>
          </div>

          {isZeroBalance && (
            <div className="faucet-guidance">
              <p className="faucet-note">
                ⚠️ Phantom disables the <strong>Approve</strong> button when balance is <strong>0 SOL</strong> because Solana charges ~0.000005 SOL gas fee.
              </p>
              <div className="faucet-actions">
                <button type="button" className="btn btn-outline" onClick={copyAddress}>
                  {copied ? '✓ Address Copied!' : 'Copy Wallet Address'}
                </button>
                <a
                  href="https://faucet.solana.com/"
                  target="_blank"
                  rel="noreferrer"
                  className="btn btn-airdrop"
                >
                  Get Free Devnet SOL (faucet.solana.com) ↗
                </a>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Attested result state */}
      {attestationResult && (
        <div className="verified-box">
          <div className="verified-header">
            <span className="check-icon">✓</span>
            <span className="verified-title">Document Attested & Verified on Solana</span>
          </div>

          <div className="verified-details">
            <div className="detail-row">
              <span>Record:</span>
              <code>{document_id}</code>
            </div>
            <div className="detail-row">
              <span>Version:</span>
              <span>{attestationResult.version || 1}</span>
            </div>
            <div className="detail-row">
              <span>Record Hash:</span>
              <code>{record_hash?.slice(0, 16)}...</code>
            </div>
            <div className="detail-row">
              <span>Solana Verification:</span>
              <span className="status-verified-text">
                ✓ {attestationResult.verification_status}
              </span>
            </div>
            <div className="detail-row">
              <span>Network:</span>
              <span>Devnet</span>
            </div>
            <div className="detail-row">
              <span>Transaction Signature:</span>
              {attestationResult.transaction_signature?.startsWith('sim_') ? (
                <code>{attestationResult.transaction_signature}</code>
              ) : (
                <a
                  href={`https://explorer.solana.com/tx/${attestationResult.transaction_signature}?cluster=devnet`}
                  target="_blank"
                  rel="noreferrer"
                  className="explorer-link"
                >
                  {attestationResult.transaction_signature?.slice(0, 16)}... (View on Solana Explorer ↗)
                </a>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Status & Error feedback */}
      {statusMessage && !attestationResult && (
        <div className="status-badge status-info">{statusMessage}</div>
      )}
      {error && <div className="status-badge status-error">{error}</div>}

      {/* Action buttons */}
      {!attestationResult && (
        <div className="attest-actions">
          {connected ? (
            <div className="btn-row">
              <button
                type="button"
                className="btn btn-primary btn-large"
                onClick={handleSignAndAttest}
                disabled={signing || isZeroBalance}
                title={isZeroBalance ? 'Fund wallet with free Devnet SOL first' : 'Sign Memo transaction'}
              >
                {signing ? 'Confirming...' : isZeroBalance ? 'Approve Disabled (0 SOL)' : 'Sign & Attest on Devnet'}
              </button>

              <button
                type="button"
                className="btn btn-outline"
                onClick={handleDemoAttest}
                disabled={signing}
                title="Immediate verified attestation without faucet"
              >
                Demo Attest (Instant)
              </button>
            </div>
          ) : (
            <p className="wallet-prompt">
              Connect your Solana wallet above to sign and attest this record on Devnet.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

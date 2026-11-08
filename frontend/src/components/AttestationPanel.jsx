import { useEffect, useState } from "react";
import { useConnection, useWallet } from "@solana/wallet-adapter-react";
import { useWalletModal } from "@solana/wallet-adapter-react-ui";
import { buildMemoTransaction, explorerTxUrl, formatAddress } from "../lib/solana";
import { submitAttestation } from "../lib/api";
import { useWalletStatus } from "./walletStatus";

export default function AttestationPanel({ document, onSealed }) {
  const { connection } = useConnection();
  const { publicKey, connected, sendTransaction } = useWallet();
  const { setVisible } = useWalletModal();
  const { error: walletError } = useWalletStatus();

  const [balance, setBalance] = useState({ address: null, sol: null });
  const [signing, setSigning] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const address = publicKey?.toBase58();
  const attestations = document?.attestations || [];
  const mySeal = attestations.find((item) => item.verified && item.wallet === address);
  const currentBalance = balance.address === address ? balance.sol : null;

  useEffect(() => {
    if (!connected || !publicKey) return undefined;
    let active = true;
    const walletAddress = publicKey.toBase58();
    connection
      .getBalance(publicKey, "confirmed")
      .then((lamports) => {
        if (active) setBalance({ address: walletAddress, sol: lamports / 1e9 });
      })
      .catch(() => {
        if (active) setBalance({ address: walletAddress, sol: null });
      });
    return () => {
      active = false;
    };
  }, [connected, publicKey, connection]);

  if (!document) return null;

  const handleSeal = async () => {
    if (!connected || !publicKey) {
      setError("Connect a wallet before attesting this record.");
      return;
    }
    if (!document.memo_payload) {
      setError("This record has no memo yet. Re-run extraction first.");
      return;
    }

    setSigning(true);
    setError(null);
    setResult(null);
    setMessage("Preparing the ORBITREE|1 memo…");

    try {
      const { blockhash, lastValidBlockHeight } = await connection.getLatestBlockhash("confirmed");
      const transaction = buildMemoTransaction(document.memo_payload, publicKey, blockhash);

      setMessage("Approve the memo in your wallet…");
      const signature = await sendTransaction(transaction, connection);

      setMessage("Signature broadcast. Waiting for confirmation…");
      await connection.confirmTransaction(
        { signature, blockhash, lastValidBlockHeight },
        "confirmed"
      );

      setMessage("Verifying the transaction against Solana Devnet…");
      const response = await submitAttestation({
        documentId: document.document_id,
        version: document.version || 1,
        transactionSignature: signature,
        wallet: publicKey.toBase58(),
        network: "devnet",
      });

      setResult(response);
      setMessage("Attestation verified and recorded.");
      onSealed?.(response);
    } catch (err) {
      const raw = err?.message || "";
      if (raw.includes("0x1") || raw.toLowerCase().includes("insufficient")) {
        setError(
          "This wallet has no Devnet SOL for the network fee. Use the faucet below, then try again."
        );
      } else if (raw.toLowerCase().includes("rejected")) {
        setError("The signature was rejected in the wallet. Nothing was written.");
      } else {
        setError(raw || "The attestation could not be completed.");
      }
      setMessage("");
    } finally {
      setSigning(false);
    }
  };

  const txUrl = explorerTxUrl(result?.transaction_signature);
  const zeroBalance = connected && currentBalance === 0;

  if (mySeal) {
    const sealUrl = explorerTxUrl(mySeal.tx_signature);
    return (
      <div className="attest-panel attest-panel-done">
        <div className="attest-panel-head">
          <div>
            <h4>This wallet has already attested</h4>
            <p>
              {formatAddress(address, 6)} signed this record. A second witness must connect a
              different wallet.
            </p>
          </div>
          <span className="witness-check">✓</span>
        </div>
        {sealUrl && (
          <a className="btn btn-ghost btn-sm" href={sealUrl} target="_blank" rel="noreferrer">
            View this attestation ↗
          </a>
        )}
      </div>
    );
  }

  return (
    <div className="attest-panel">
      <div className="attest-panel-head">
        <div>
          <h4>Add your witness signature</h4>
          <p>
            Your wallet signs the record hash in a Solana memo. No tokens move; the signature is
            the proof.
          </p>
        </div>
        <span className="attest-step">Witness</span>
      </div>

      <div className="attest-wallet-row">
        {connected && address ? (
          <>
            <div className="attest-wallet">
              <span className="dot dot-pulse" />
              <span className="attest-wallet-label">Connected</span>
              <strong>{formatAddress(address, 6)}</strong>
            </div>
            <span className="attest-balance">
              {currentBalance === null ? "Checking balance…" : `${currentBalance.toFixed(4)} SOL`}
            </span>
          </>
        ) : (
          <>
            <div className="attest-wallet attest-wallet-none">
              <span className="dot dot-off" />
              No wallet connected
            </div>
            <button type="button" className="btn btn-ink btn-sm" onClick={() => setVisible(true)}>
              Connect wallet
            </button>
          </>
        )}
      </div>

      {walletError && <div className="notice notice-error">{walletError}</div>}

      {zeroBalance && (
        <div className="notice notice-warning">
          <div>
            <strong>Devnet SOL is needed for the network fee.</strong>
            <div className="faucet-actions">
              <button
                type="button"
                className="btn btn-cream btn-sm"
                onClick={() => navigator.clipboard?.writeText(address)}
              >
                Copy wallet address
              </button>
              <a
                className="btn btn-ghost btn-sm"
                href="https://faucet.solana.com/"
                target="_blank"
                rel="noreferrer"
              >
                Open faucet ↗
              </a>
            </div>
          </div>
        </div>
      )}

      <div className="attest-actions">
        <button
          type="button"
          className="btn btn-oxblood btn-lg"
          onClick={handleSeal}
          disabled={signing || !connected || zeroBalance}
        >
          {signing ? "Attesting…" : "Sign & attest on Devnet"}
        </button>
      </div>

      {message && <div className="notice notice-info">{message}</div>}
      {error && <div className="notice notice-error">{error}</div>}

      {result && (
        <div className="seal-result">
          <div className="seal-result-head">
            <span className="seal-result-mark">✓</span>
            <div>
              <strong>Attestation verified</strong>
              <span>Witnessed by {formatAddress(result.wallet || address, 6)}</span>
            </div>
          </div>
          {txUrl && (
            <a className="btn btn-ghost btn-sm" href={txUrl} target="_blank" rel="noreferrer">
              View transaction on Solana Explorer ↗
            </a>
          )}
        </div>
      )}
    </div>
  );
}

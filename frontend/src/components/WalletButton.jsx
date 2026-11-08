import { useEffect, useState } from "react";
import { useConnection, useWallet } from "@solana/wallet-adapter-react";
import { useWalletModal } from "@solana/wallet-adapter-react-ui";
import { WalletReadyState } from "@solana/wallet-adapter-base";
import { formatAddress } from "../lib/solana";
import { useWalletStatus } from "./walletStatus";

function isReady(wallet) {
  return (
    wallet?.readyState === WalletReadyState.Installed ||
    wallet?.readyState === WalletReadyState.Loadable
  );
}

export default function WalletButton() {
  const { connection } = useConnection();
  const {
    publicKey,
    connected,
    connecting,
    disconnecting,
    disconnect,
    connect,
    wallet,
    wallets,
  } = useWallet();
  const { setVisible } = useWalletModal();
  const { error, clearError } = useWalletStatus();
  const [balance, setBalance] = useState({ address: null, sol: null });
  const [pendingConnect, setPendingConnect] = useState(false);

  // The wallet modal only selects an adapter; the connection has to be started
  // explicitly once a selection exists.
  useEffect(() => {
    if (!pendingConnect || connected || connecting || !wallet) return;
    connect().then(
      () => setPendingConnect(false),
      () => setPendingConnect(false)
    );
  }, [pendingConnect, connected, connecting, wallet, connect]);

  useEffect(() => {
    if (!connected || !publicKey) return undefined;
    const address = publicKey.toBase58();
    let active = true;
    connection
      .getBalance(publicKey, "confirmed")
      .then((lamports) => {
        if (active) setBalance({ address, sol: lamports / 1e9 });
      })
      .catch(() => {
        if (active) setBalance({ address, sol: null });
      });
    return () => {
      active = false;
    };
  }, [connected, publicKey, connection]);

  const address = publicKey?.toBase58();
  const currentBalance = balance.address === address ? balance.sol : null;
  const detected = wallets.filter((item) => item.readyState === WalletReadyState.Installed);
  const attempting = connecting || (pendingConnect && Boolean(wallet) && isReady(wallet));

  const startConnect = () => {
    clearError();
    setPendingConnect(true);
    if (!wallet || !isReady(wallet)) setVisible(true);
  };

  const switchWallet = () => {
    clearError();
    setPendingConnect(true);
    setVisible(true);
  };

  if (connected && address) {
    return (
      <div className="wallet-area">
        <div className="wallet-connected">
          <div className="wallet-connected-main">
            <span className="wallet-state">
              <span className="dot dot-pulse" />
              Wallet connected
            </span>
            <button
              type="button"
              className="wallet-address"
              onClick={() => navigator.clipboard?.writeText(address)}
              title="Copy wallet address"
              data-testid="wallet-address"
            >
              {formatAddress(address, 6)}
            </button>
          </div>
          <div className="wallet-connected-meta">
            <span>{wallet?.adapter?.name || "Solana wallet"}</span>
            <span className="wallet-network">Devnet</span>
            <span className="wallet-balance">
              {currentBalance === null ? "—" : `${currentBalance.toFixed(4)} SOL`}
            </span>
          </div>
          <button
            type="button"
            className="wallet-disconnect"
            onClick={() => disconnect()}
            disabled={disconnecting}
          >
            {disconnecting ? "Disconnecting…" : "Disconnect"}
          </button>
        </div>
        {error && <div className="wallet-error">{error}</div>}
      </div>
    );
  }

  return (
    <div className="wallet-area">
      <button
        type="button"
        className="wallet-connect"
        onClick={startConnect}
        disabled={connecting}
        data-testid="connect-wallet-btn"
      >
        <span className="wallet-connect-title">
          {attempting ? "Connecting…" : "Connect wallet"}
        </span>
        <span className="wallet-connect-sub">
          {attempting
            ? "Approve the connection request in your wallet"
            : "Phantom or Solflare · Devnet"}
        </span>
      </button>
      {error && <div className="wallet-error">{error}</div>}
      {!attempting && wallet && (
        <button type="button" className="wallet-hint wallet-switch" onClick={switchWallet}>
          Use a different wallet
        </button>
      )}
      {!attempting && detected.length === 0 && (
        <p className="wallet-hint">
          No Solana wallet detected in this browser. Install{" "}
          <a href="https://phantom.app/download" target="_blank" rel="noreferrer">
            Phantom
          </a>{" "}
          or{" "}
          <a href="https://solflare.com/download" target="_blank" rel="noreferrer">
            Solflare
          </a>
          , reload this page, then connect.
        </p>
      )}
    </div>
  );
}

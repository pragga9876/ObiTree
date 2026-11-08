import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ConnectionProvider, WalletProvider } from "@solana/wallet-adapter-react";
import { WalletAdapterNetwork } from "@solana/wallet-adapter-base";
import { WalletModalProvider } from "@solana/wallet-adapter-react-ui";
import { PhantomWalletAdapter, SolflareWalletAdapter } from "@solana/wallet-adapter-wallets";
import { clusterApiUrl } from "@solana/web3.js";
import { WalletStatusContext } from "./walletStatus";

import "@solana/wallet-adapter-react-ui/styles.css";

const NETWORK = WalletAdapterNetwork.Devnet;

export default function SolanaWalletProvider({ children }) {
  const endpoint = useMemo(() => clusterApiUrl(NETWORK), []);
  const wallets = useMemo(
    () => [new PhantomWalletAdapter(), new SolflareWalletAdapter({ network: NETWORK })],
    []
  );

  const [error, setError] = useState(null);
  const errorTimer = useRef(null);

  const clearError = useCallback(() => {
    window.clearTimeout(errorTimer.current);
    setError(null);
  }, []);

  const handleError = useCallback((walletError, adapter) => {
    window.clearTimeout(errorTimer.current);
    const walletName = adapter?.name || "The wallet";
    let message =
      walletError?.message ||
      `${walletName} could not be connected. Unlock the extension and try again.`;
    if (walletError?.name === "WalletNotReadyError") {
      message = `${walletName} is not installed in this browser. Install the extension, reload this page, then connect again.`;
    } else if (walletError?.name === "WalletConnectionError") {
      message = `${walletName} did not approve the connection. Open the extension, approve the request, then try again.`;
    }
    setError(message);
    errorTimer.current = window.setTimeout(() => setError(null), 12000);
  }, []);

  useEffect(() => () => window.clearTimeout(errorTimer.current), []);

  return (
    <WalletStatusContext.Provider value={{ error, clearError }}>
      <ConnectionProvider endpoint={endpoint}>
        <WalletProvider wallets={wallets} autoConnect={false} onError={handleError}>
          <WalletModalProvider>{children}</WalletModalProvider>
        </WalletProvider>
      </ConnectionProvider>
    </WalletStatusContext.Provider>
  );
}

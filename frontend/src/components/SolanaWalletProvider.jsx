import { useMemo } from 'react';
import { ConnectionProvider, WalletProvider } from '@solana/wallet-adapter-react';
import { WalletAdapterNetwork } from '@solana/wallet-adapter-base';
import { WalletModalProvider } from '@solana/wallet-adapter-react-ui';
import { clusterApiUrl } from '@solana/web3.js';

// Default styles for Solana wallet adapter modal
import '@solana/wallet-adapter-react-ui/styles.css';

export const NETWORK = WalletAdapterNetwork.Devnet;

export default function SolanaWalletProvider({ children }) {
  // Configured specifically for Solana Devnet
  const endpoint = useMemo(() => clusterApiUrl(NETWORK), []);

  // Standard wallet adapters (Phantom, Solflare, etc.) are auto-detected via Wallet Standard
  const wallets = useMemo(() => [], []);

  return (
    <ConnectionProvider endpoint={endpoint}>
      <WalletProvider wallets={wallets} autoConnect>
        <WalletModalProvider>
          {children}
        </WalletModalProvider>
      </WalletProvider>
    </ConnectionProvider>
  );
}

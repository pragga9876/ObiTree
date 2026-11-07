import { WalletAdapterNetwork } from '@solana/wallet-adapter-base';
import { Connection, clusterApiUrl } from '@solana/web3.js';

export const NETWORK = WalletAdapterNetwork.Devnet;
export const DEVNET_ENDPOINT = clusterApiUrl(NETWORK);

/**
 * Creates a read-only Solana Connection to Devnet
 */
export function getDevnetConnection() {
  return new Connection(DEVNET_ENDPOINT, 'confirmed');
}

/**
 * Truncates a public address string for concise UI display (e.g. 7xKX...gAsU)
 */
export function formatAddress(address, chars = 4) {
  if (!address) return '';
  const addrStr = typeof address === 'string' ? address : address.toBase58();
  return `${addrStr.slice(0, chars)}...${addrStr.slice(-chars)}`;
}

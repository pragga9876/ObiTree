import { WalletAdapterNetwork } from "@solana/wallet-adapter-base";
import {
  Connection,
  clusterApiUrl,
  Transaction,
  TransactionInstruction,
  PublicKey,
} from "@solana/web3.js";

export const NETWORK = WalletAdapterNetwork.Devnet;
export const DEVNET_ENDPOINT = clusterApiUrl(NETWORK);

// Official Solana Memo Program V2
export const MEMO_PROGRAM_ID = new PublicKey(
  "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr"
);

export function getDevnetConnection() {
  return new Connection(DEVNET_ENDPOINT, "confirmed");
}

export function formatAddress(address, chars = 4) {
  if (!address) return "";
  const addrStr = typeof address === "string" ? address : address.toBase58();
  return `${addrStr.slice(0, chars)}…${addrStr.slice(-chars)}`;
}

export function explorerTxUrl(signature) {
  if (!signature || signature.startsWith("sim_") || signature.startsWith("mock_")) {
    return null;
  }
  return `https://explorer.solana.com/tx/${signature}?cluster=devnet`;
}

export function explorerAddressUrl(address) {
  if (!address) return null;
  return `https://explorer.solana.com/address/${address}?cluster=devnet`;
}

/**
 * Builds a Solana transaction carrying the Orbitree memo envelope.
 */
export function buildMemoTransaction(memoText, signerPublicKey, blockhash) {
  const memoData = new TextEncoder().encode(memoText);

  const memoInstruction = new TransactionInstruction({
    keys: [{ pubkey: signerPublicKey, isSigner: true, isWritable: false }],
    programId: MEMO_PROGRAM_ID,
    data: memoData,
  });

  const transaction = new Transaction();
  transaction.recentBlockhash = blockhash;
  transaction.feePayer = signerPublicKey;
  transaction.add(memoInstruction);

  return transaction;
}

# ObiTree Solana Memo

Every clipping is sealed with a single SPL Memo instruction signed by the contributor's wallet. The memo is human-readable and contains two hashes, so the on-chain record can be checked without trusting the ObiTree server.

Program: `MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr` (SPL Memo Program)

## Registration

```text
ORBITREE|1
record: doc_001
version: 1
action: DOCUMENT_REGISTERED
file_hash: <SHA256>
record_hash: <SHA256>
previous_hash: <PREVIOUS_RECORD_HASH>
```

The first clipping in a chronicle uses `previous_hash: -` (genesis). Each later contribution uses the record hash of the most recently sealed clipping in that chronicle, forming a per-chronicle chain.

## Verification

`POST /api/attestations` requires a wallet address and independently verifies the transaction against the RPC configured in `SOLANA_RPC_URL`:

- the signature must be a real base58 Solana transaction signature; signatures beginning with `sim_` or `mock_` are rejected as `SIMULATED_REJECTED`;
- the transaction must exist on the configured cluster and `meta.err` must be `null`;
- the memo must come from an SPL Memo Program instruction in the transaction (log lines are not evidence);
- the first line must be `ORBITREE|1` (or legacy `PAPERROOTS|1`);
- `record`, `version`, `action: DOCUMENT_REGISTERED`, `file_hash` and `record_hash` must match the stored record exactly;
- the expected contributor wallet must appear among the transaction's signers.

Every check fails closed. A missing transaction, missing signer information, RPC error or mismatched field is a rejection. Rejected attempts are stored as `FAILED` for audit but never count toward a seal; the API returns `400` (or `502` for an RPC failure) with the rejection reason.

No simulated attestations are accepted in any environment. Older builds stored `sim_`/`mock_` signatures as verified; on startup the backend now marks those rows `FAILED` so they stop counting.

## Legacy

`PAPERROOTS|1` memos are still accepted so records sealed before the ObiTree rename continue to verify. New transactions always use `ORBITREE|1`.

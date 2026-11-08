# Orbitree Solana Memo

Every clipping is sealed with a single SPL Memo instruction signed by the contributor's wallet. The memo is human-readable and contains two hashes, so the on-chain record can be checked without trusting the Orbitree server.

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

`POST /api/attestations` accepts the transaction signature and independently verifies it against the Solana RPC:

- the transaction must contain a memo log with `ORBITREE|1` (or legacy `PAPERROOTS|1`);
- `record`, `version`, `file_hash` and `record_hash` must match the stored canonical record;
- the signing wallet must match the contributor wallet when supplied.

Simulated signatures beginning with `sim_` are accepted for demo purposes and reported as `VERIFIED_SIMULATED`. They do not exist on Devnet and therefore have no Solana Explorer link.

## Legacy

`PAPERROOTS|1` memos are still accepted so records sealed before the Orbitree rename continue to verify. New transactions always use `ORBITREE|1`.

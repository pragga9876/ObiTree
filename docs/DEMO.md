# ObiTree Demo Script

A five-minute walkthrough for judges.

## Setup

- Backend: `cd backend && uvicorn app.main:app --reload --port 8000`
- Frontend: `cd frontend && npm run dev`
- Two browser wallets on **Devnet**, each with a small SOL balance (faucet.solana.com). Real signatures are required; simulated signatures are rejected by the backend.

## 1. The front page

Open `http://localhost:5173`. Point out the masthead, the lead story and the live ledger card. This is deliberately a newspaper, not a dashboard.

## 2. Contributor A establishes the record

1. Connect wallet A.
2. Upload an obituary image.
3. Show the OCR text, extraction JSON and the three extracted claims. Point out the two hashes: file bytes and canonical record.
4. Click **Seal this clipping** and approve the `ORBITREE|1` memo. The genesis memo has `previous_hash: -`.
5. Copy the chronicle link.

## 3. Contributor B adds an independent page

1. Open the copied link in another browser profile or after switching wallets.
2. Connect wallet B.
3. Open **Clippings & Evidence** and upload a second clipping for the same family.
4. Seal it. Its memo `previous_hash` is wallet A's record hash.
5. Point out the two contributor wallets and two pages in the header.

## 4. The merged tree and reasoning

Open **The Family Chronicle**.

- The dark ledger plate is the family tree. Parents sit one generation above the subject, siblings at the same generation.
- Edge plaques show the relation, how many independent clippings agree, and a short record hash.
- The editor's reasoning panel gives the confidence score, corroborated branches, single-source branches and any conflicts. Conflicts are preserved, not resolved silently.
- Click a node or edge: the provenance panel shows the exact evidence quote, contributing wallet, record hash and a link to read the clipping.

## 5. The chain ledger

Open **Chain Ledger**.

- Block 01 is genesis and `PREVIOUS` is `-`.
- Block 02 shows block 01's record hash as `PREVIOUS`, plus the document hash and wallet.
- Every block links to its real Devnet transaction on Solana Explorer.

## 6. What to emphasize

- Two contributors act independently; no shared password or edit access.
- Every contribution is sealed by its own wallet and chained by hash.
- The tree is reconstructed with explicit reasoning and evidence, not a single opaque summary.
- The system never deletes a conflicting claim; it exposes it.
- The same clipping always canonicalizes to the same record hash.

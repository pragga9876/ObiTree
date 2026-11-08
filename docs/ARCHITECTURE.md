# Orbitree Architecture

## Backend

FastAPI + SQLAlchemy + SQLite.

- `routers/documents.py` owns uploads, chronicles, canonical records and attestations.
- `services/ocr_service.py` preprocesses images with OpenCV and runs Tesseract.
- `services/llm_service.py` asks Gemini for structured events and relationships. If the API key is missing or the model returns nothing usable, `record_service` builds a record from a deterministic heuristic parser instead.
- `services/record_service.py` produces a canonical JSON record with sorted keys and people/claims, so the same extraction always hashes the same way.
- `services/hashing_service.py` provides SHA-256 for file bytes and canonical JSON.
- `services/graph_service.py` merges every clipping in a chronicle into one graph:
  - names are normalized into person keys;
  - filings that never name the chronicle subject stay in the ledger but are excluded from the merged tree, so an unrelated notice cannot inject another family;
  - claims become edges with a family type and generational delta;
  - an edge seen in two or more distinct **file hashes** is `corroborated` (re-uploading identical bytes does not create a second witness);
  - the same pair asserted with incompatible family types (or in both directions) is a `conflict` and both readings are kept;
  - differing printed event dates become `date_conflicts`;
  - confidence is a weighted edge score minus a conflict penalty, capped at 99.
- `services/solana_service.py` verifies `ORBITREE|1` memos against the configured RPC.

## Data flow

```text
upload → OCR → Gemini/heuristic extraction → canonical record
       → file_hash + record_hash → memo with previous_hash
       → wallet signs on Devnet → backend verifies via RPC
       → contribution stored → graph rebuilt on read
```

The graph is computed on request from stored canonical records and contributions. Nothing is merged destructively; every edge retains its source clippings, evidence quotes, wallets and signatures.

## Frontend

React 19 + Vite, no router dependency. `App.jsx` reads `window.location.hash`:

- `/` — `HomePage` (lead story, upload, live chain panel, two-witness explainer, archive).
- `/#/memorial/<project-id>` — `ProjectPage` (shared chronicle).

`ProjectPage` renders three tabs:

1. **The Family Chronicle** — `FamilyTree`, notices, `ReasoningPanel`, `ProvenancePanel`.
2. **Clippings & Evidence** — upload-to-chronicle panel and `ClippingCard`s with raw OCR, JSON and seal flow.
3. **Chain Ledger** — `LedgerChain`.

The family tree is a hand-built SVG on a dark "ledger plate": generations are grouped by `node.generation`, ordered with a barycenter pass to reduce crossings, and edges carry plaques showing the relation, corroborating source count and a short record hash. Nodes show initials, roles, source count and a seal when attested.

Wallets are handled by `@solana/wallet-adapter-react`; signing builds a Memo instruction with `@solana/web3.js`. `autoConnect` is disabled so visitors choose when to connect.

The visual system uses Playfair Display, Libre Baskerville, Special Elite and IBM Plex Mono over a paper/ink/oxblood/brass/forest palette, with a paper-grain background and stamp-like status marks.

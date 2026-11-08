# Orbitree

**The Family Chronicle.** Orbitree reads old obituaries and memorial notices, reconstructs the family tree across independent clippings, and seals every contribution on Solana — so a family record cannot be quietly rewritten.

Orbitree was built for the Solana hackathon. It is a newspaper, an archive and a ledger at once: the interface is set like a vintage memorial supplement, while the data model treats every uploaded page as an independently witnessed block.

---

## What it does

1. A contributor uploads a photograph, scan or screenshot of an obituary.
2. The backend runs OpenCV/Tesseract OCR and Gemini multimodal structured extraction, then builds a deterministic canonical record of events and family claims.
3. Two SHA-256 hashes are produced: the **file hash** of the uploaded bytes and the **record hash** of the canonical JSON.
4. The contributor signs an `ORBITREE|1` memo containing both hashes and the hash of the previous sealed record, and broadcasts it to Solana Devnet.
5. The backend verifies the memo against the RPC, records the wallet and transaction signature, and marks the clipping sealed.
6. Any other contributor can open the shared chronicle link, connect a different wallet, and file another clipping. Its memo chains to the previous record hash.
7. Orbitree merges the clippings into one family graph, marks agreement as **corroborated**, preserves contradictions instead of overwriting them, and shows the evidence, wallet and transaction behind every edge.

> Verification/arbitration of which conflicting account is "correct" is intentionally out of scope for this build. Both readings survive in the record.

---

## Two contributors, one chronicle

- **Contributor A** uploads the first clipping. A memorial project is created automatically (`The <Name> Family Chronicle`) with a shareable link: `/#/memorial/<project-id>`. This is the genesis block.
- **Contributor B** opens the shared link from any wallet and adds an independent clipping to the same project, without needing edit access.
- Both contributions are sealed separately and chained: each memo's `previous_hash` points at the prior sealed record hash.
- The chronicle page shows both contributor wallets, the merged tree, the ledger chain and an editor's reasoning panel explaining why the tree looks the way it does.

`POST /api/documents` without a `project_id` creates a new chronicle. Passing `project_id` appends to an existing one.

---

## Architecture

```text
Upload (PDF / image)
      ↓
SHA-256(file bytes)
      ↓
OpenCV preprocessing + Tesseract OCR
      ↓
Gemini structured extraction (offline regex fallback if no API key)
      ↓
Deterministic canonical record  →  SHA-256(canonical JSON)
      ↓
ORBITREE|1 memo with previous_hash
      ↓
Contributor signs with Phantom / Solflare on Solana Devnet
      ↓
RPC verification → SQLite storage → merged graph + reasoning
```

The frontend has no router dependency. It uses hash routes:

- `/` — front page, upload, archive
- `/#/memorial/<project-id>` — shared chronicle

---

## Prerequisites

1. Python 3.10+
2. Node.js 18+ and npm
3. Tesseract OCR
   - Ubuntu/Debian: `sudo apt-get update && sudo apt-get install -y tesseract-ocr`
   - macOS: `brew install tesseract`
   - Windows: [UB-Mannheim Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki)
4. A Solana wallet extension (Phantom or Solflare), set to Devnet

---

## Backend setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Configure `backend/.env`:

```env
GEMINI_API_KEY=your_gemini_api_key_here
SOLANA_NETWORK=devnet
SOLANA_RPC_URL=https://api.devnet.solana.com
```

If `GEMINI_API_KEY` is missing or exhausted, extraction falls back to a deterministic heuristic parser so the demo still works.

Start the server:

```bash
uvicorn app.main:app --reload --port 8000
```

- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- Health: `http://localhost:8000/api/health`

---

## Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

The frontend reads `VITE_API_URL` if set; otherwise it uses `http://localhost:8000`.

---

## Wallet and Devnet setup

1. Install Phantom or Solflare.
2. Open the wallet settings and switch the network to **Solana Devnet**.
3. Fund the wallet with free Devnet SOL: [faucet.solana.com](https://faucet.solana.com/) or `solana airdrop 1 <ADDRESS> --url devnet`.
4. On the site, click **Connect Wallet**, then use **Seal this clipping** to sign the memo.

If a wallet has zero balance, the attestation panel explains how to fund it. Simulated signatures (`sim_orbitree_...`) are accepted by the backend for demo runs that cannot reach Devnet; these show as "Simulated" rather than linking to Solana Explorer.

---

## Using the app

1. **Connect a wallet** from the masthead.
2. **Archive a clipping** on the front page. Orbitree creates the chronicle automatically.
3. Review the extracted claims and the canonical JSON on the clipping card.
4. **Seal this clipping** to sign the `ORBITREE|1` memo on Devnet.
5. **Copy the chronicle link** and open it from a second wallet.
6. Add a second clipping to the same chronicle, then seal it. Its memo points back to the first record hash.
7. Open **The Family Chronicle** tab to see the merged tree, confidence seal, corroborated branches, conflicts, notices and evidence. **Clippings & Evidence** lists each page; **Chain Ledger** shows the hash chain.

---

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Service, database and network status |
| `GET` | `/api/projects` | List memorial chronicles |
| `GET` | `/api/projects/{project_id}` | Chronicle with documents, merged graph, reasoning and ledger |
| `POST` | `/api/documents` | Upload a clipping (`file`, optional `project_id`, optional `wallet`) |
| `GET` | `/api/documents/{doc_id}` | Document detail including raw OCR |
| `POST` | `/api/documents/{doc_id}/extract` | Re-run extraction for a stored document |
| `GET` | `/api/records/{record_id}` | Latest canonical record and contributing attestation |
| `POST` | `/api/attestations` | Submit and verify a Solana attestation |
| `GET` | `/api/verify/{signature}` | Look up a verified signature |

---

## Memo format

```text
ORBITREE|1
record: doc_001
version: 1
action: DOCUMENT_REGISTERED
file_hash: <SHA256>
record_hash: <SHA256>
previous_hash: <PREVIOUS_RECORD_HASH>
```

Legacy `PAPERROOTS|1` memos are still accepted by verification so older records continue to validate.

The memo instruction uses the SPL Memo Program (`MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr`).

---

## Repository structure

```text
ObiTree/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app
│   │   ├── models.py               # Project, ProjectDocument, Document, CanonicalRecord, Contribution
│   │   ├── routers/documents.py    # Upload, chronicles, canonical records, attestations
│   │   └── services/
│   │       ├── graph_service.py    # Merged family graph, corroboration, conflicts, reasoning, ledger
│   │       ├── hashing_service.py  # SHA-256 helpers
│   │       ├── ocr_service.py      # OpenCV + Tesseract
│   │       ├── llm_service.py      # Gemini structured extraction
│   │       ├── record_service.py   # Deterministic canonical record builder
│   │       └── solana_service.py   # Memo verification against Solana RPC
│   ├── obitree.db                  # SQLite database (created automatically)
│   └── uploads/                    # Original uploads
└── frontend/
    └── src/
        ├── App.jsx                 # Hash router and application shell
        ├── pages/HomePage.jsx      # Front page, upload, archive
        ├── pages/ProjectPage.jsx   # Shared chronicle
        ├── components/             # Masthead, FamilyTree, ReasoningPanel, ProvenancePanel, LedgerChain, ...
        ├── lib/api.js              # Backend client
        └── lib/solana.js           # Memo transaction builder
```

---

## Two-hash integrity

1. **`file_hash`** = `SHA-256(original file bytes)` — proves the uploaded clipping was not altered.
2. **`record_hash`** = `SHA-256(canonical JSON)` — identifies the normalized claims extracted from that clipping.
3. **`previous_hash`** = the prior record hash in the same chronicle — links contributions into a per-chronicle chain.

The canonical record sorts its keys and list entries deterministically so the same extraction always produces the same hash.

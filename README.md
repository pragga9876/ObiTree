# frontend : https://obitree.vercel.app/
# backend : https://obitree.onrender.com/
# Obitree

**The Family Chronicle.** ObiTree reads old obituaries and memorial notices, reconstructs the family tree across independent clippings, and seals every contribution on Solana — so a family record cannot be quietly rewritten.

ObiTree was built for the Solana hackathon. It is a newspaper, an archive and a ledger at once: the interface is set like a vintage memorial supplement, while the data model treats every uploaded page as an independently witnessed block.

---

## What it does

1. A contributor uploads a photograph, scan or screenshot of an obituary — no wallet required.
2. The backend runs OpenCV/Tesseract OCR and Gemini multimodal structured extraction, then builds a deterministic canonical record of events and family claims.
3. Two SHA-256 hashes are produced: the **file hash** of the uploaded bytes and the **record hash** of the canonical JSON.
4. The record is persisted (PostgreSQL + Supabase Storage in production) and a shareable chronicle link is created.
5. The contributor connects Phantom or Solflare, signs an `ORBITREE|1` memo containing both hashes and the previous sealed record hash, and broadcasts it to Solana Devnet.
6. The backend fetches the transaction from the configured RPC, verifies the memo, signer, hashes and success status, then records the wallet and signature.
7. Any other contributor opens the shared link, connects a different wallet, and files another clipping. Its memo chains to the previous record hash.
8. ObiTree merges the clippings into one family graph, marks agreement as **corroborated**, preserves contradictions instead of overwriting them, and shows the evidence, wallet and transaction behind every edge.

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
Supabase Storage (or backend/uploads in development)
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
RPC verification → PostgreSQL (or SQLite) → merged graph + reasoning
```

The frontend has no router dependency. It uses hash routes:

- `/` — front page, upload, archive
- `/#/memorial/<project-id>` — shared chronicle

---

## Prerequisites

1. Python 3.10+
2. Node.js 18+ and npm
3. Tesseract OCR (installed automatically in the production Docker image)
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
APP_ENV=development
DATABASE_URL=
GEMINI_API_KEY=your_gemini_api_key_here
SOLANA_NETWORK=devnet
SOLANA_RPC_URL=https://api.devnet.solana.com
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_STORAGE_BUCKET=obituary-images
SUPABASE_STORAGE_PUBLIC=true
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173
```

- With `DATABASE_URL` unset, the backend uses SQLite at `backend/obitree.db`.
- With the Supabase Storage variables unset, uploads are written to `backend/uploads` and served at `/uploads/...`.
- If `GEMINI_API_KEY` is missing or exhausted, extraction falls back to a deterministic heuristic parser so the demo still works.

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

Create `frontend/.env.local` for a non-default backend:

```env
VITE_API_URL=http://localhost:8000
```

In development, a missing `VITE_API_URL` falls back to `http://localhost:8000`. In a production build there is **no localhost fallback**: requests throw a configuration error until `VITE_API_URL` is set at build time.

---

## Production deployment

### 1. Supabase (PostgreSQL + Storage)

1. Create a Supabase project.
2. **Database:** copy the connection string from *Project Settings → Database*. The pooler URL (`...pooler.supabase.com:6543/postgres`) is recommended for Render.
3. **Storage:** create a bucket named `obituary-images`. Either make it public (simplest; images are not sensitive beyond the clipping itself) or keep it private — the backend issues signed URLs when `SUPABASE_STORAGE_PUBLIC=false`.
4. Copy the **secret key** from *Project Settings → API*. Use the legacy `service_role` JWT (`eyJ...`) or the newer `sb_secret_...` key — **not** the anon/publishable key, because uploads are rejected by row-level security. Keep it server-side only; never put it in `VITE_*` variables or the frontend.

Upload failures from Supabase are returned with the real error code, e.g. `Supabase Storage upload failed (HTTP 400: AccessDenied: ...)`. Common causes:

- `Invalid Compact JWS` — a non-JWT `sb_secret_...` key was sent in the `Authorization` header (the backend now sends new keys only via `apikey`).
- `AccessDenied` / `new row violates row-level security policy` — the anon/publishable key was configured instead of the secret/service key.
- `NoSuchBucket` — the bucket name does not match `SUPABASE_STORAGE_BUCKET`.
- `InvalidMimeType` — the bucket has an allowed-MIME list that excludes the upload.

Install the database schema by starting the backend once against the Supabase URL; `Base.metadata.create_all()` and the idempotent migration run automatically.

### 2. Render (backend)

The repository includes `render.yaml` and `backend/Dockerfile`:

- **Service type:** Web Service
- **Runtime:** Docker
- **Root directory:** `backend`
- **Dockerfile:** `./Dockerfile`
- **Health check path:** `/api/health`
- **Start command:** the Dockerfile runs
  `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

The image installs Tesseract OCR (`tesseract-ocr`, `tesseract-ocr-eng`) and the OpenCV system libraries, so OCR works in production.

Environment variables to set in the Render dashboard:

| Variable | Required | Notes |
| --- | --- | --- |
| `APP_ENV` | yes | `production` |
| `DATABASE_URL` | yes | Supabase Postgres URL (pooler, `sslmode=require`) |
| `SUPABASE_URL` | yes | `https://<project-ref>.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | yes | Secret key (`sb_secret_...`) or legacy `service_role` JWT; never the anon/publishable key |
| `SUPABASE_STORAGE_BUCKET` | yes | `obituary-images` |
| `SUPABASE_STORAGE_PUBLIC` | no | `true` (default) or `false` for signed URLs |
| `SUPABASE_SIGNED_URL_TTL` | no | Seconds; default `604800` |
| `GEMINI_API_KEY` | yes | Structured extraction |
| `SOLANA_NETWORK` | no | `devnet` |
| `SOLANA_RPC_URL` | no | Defaults to `https://api.devnet.solana.com` |
| `CORS_ORIGINS` | yes | Comma-separated Vercel domain(s) |
| `CORS_ORIGIN_REGEX` | no | e.g. `https://.*\.vercel\.app` for previews |

Do **not** deploy from the repository root: the root `requirements.txt` is a machine-specific `pip freeze` and includes an unbuildable local TBB path. The backend must build from `backend/requirements.txt`.

### 3. Vercel (frontend)

- **Root directory:** `frontend`
- **Build command:** `npm run build`
- **Output directory:** `dist`
- **Environment variable:** `VITE_API_URL=https://<your-render-service>.onrender.com`

Redeploy after changing `VITE_API_URL`; Vite inlines it at build time. Add the Vercel production domain to the backend's `CORS_ORIGINS`, and the preview wildcard to `CORS_ORIGIN_REGEX` if you use preview deployments.

---

## Wallet and Devnet setup

1. Install Phantom or Solflare.
2. Open the wallet settings and switch the network to **Solana Devnet**.
3. Fund the wallet with free Devnet SOL: [faucet.solana.com](https://faucet.solana.com/) or `solana airdrop 1 <ADDRESS> --url devnet`.
4. On the site, click **Connect Wallet**, then use **Sign & attest on Devnet** to sign the memo.

Only real Devnet transactions are accepted. Simulated signatures (`sim_...` / `mock_...`) are rejected with `SIMULATED_REJECTED`, and an attestation is recorded as `VERIFIED` only after the backend has confirmed all of the following against `SOLANA_RPC_URL`:

- the transaction exists and `meta.err` is `null`;
- the memo comes from an SPL Memo Program instruction;
- the prefix is `ORBITREE|1` (or legacy `PAPERROOTS|1`);
- `record`, `version`, `action`, `file_hash` and `record_hash` match exactly;
- the submitted wallet is one of the transaction's signers.

Failed verification is stored as `FAILED` for audit but never marks the record attested.

---

## Using the app

1. Upload a clipping on the front page (no wallet needed). ObiTree creates the chronicle automatically.
2. Review the extracted claims and the canonical JSON on the clipping card.
3. Connect a wallet and **Sign & attest on Devnet** to seal the `ORBITREE|1` memo.
4. **Copy the chronicle link** and open it from a second wallet.
5. Add a second clipping to the same chronicle, then seal it. Its memo points back to the first record hash.
6. Open **Family Tree** to see the merged tree, confidence seal, corroborated branches, conflicts, notices and evidence. **Records & Attestations** lists each page; **Chain Ledger** shows the hash chain.

---

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Service, database, storage and network status |
| `GET` | `/api/projects` | List memorial chronicles |
| `GET` | `/api/projects/{project_id}` | Chronicle with documents, merged graph, reasoning and ledger |
| `POST` | `/api/documents` | Upload a clipping (`file`, optional `project_id`, optional `wallet`) |
| `GET` | `/api/documents/{doc_id}` | Document detail including raw OCR |
| `POST` | `/api/documents/{doc_id}/extract` | Re-run extraction for a stored document |
| `GET` | `/api/records/{record_id}` | Latest canonical record and contributing attestation |
| `POST` | `/api/attestations` | Submit and verify a Solana attestation |
| `GET` | `/api/verify/{signature}` | Look up a stored attestation |

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

Legacy `PAPERROOTS|1` memos are still accepted by verification so older records continue to validate. New transactions always use `ORBITREE|1`. The memo instruction uses the SPL Memo Program (`MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr`); there is no custom program or token.

---

## Repository structure

```text
ObiTree/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app, CORS, health, startup migration
│   │   ├── config.py               # env-driven DB, Supabase, Solana, CORS settings
│   │   ├── database.py             # engine, session, idempotent schema migration
│   │   ├── models.py               # Project, ProjectDocument, Document, CanonicalRecord, Contribution
│   │   ├── routers/documents.py    # Upload, chronicles, canonical records, attestations
│   │   └── services/
│   │       ├── graph_service.py    # Merged family graph, corroboration, conflicts, ledger
│   │       ├── hashing_service.py  # SHA-256 helpers
│   │       ├── storage_service.py  # Supabase Storage + local upload fallback
│   │       ├── ocr_service.py      # OpenCV + Tesseract
│   │       ├── llm_service.py      # Gemini structured extraction
│   │       ├── record_service.py   # Deterministic canonical record builder
│   │       └── solana_service.py   # Strict, fail-closed memo verification
│   ├── Dockerfile                  # Production image with Tesseract
│   ├── .dockerignore
│   ├── .env.example
│   └── requirements.txt            # Use this file for deployment
├── render.yaml                     # Render blueprint (Docker, backend rootDir)
├── docs/
└── frontend/
    └── src/
        ├── App.jsx                 # Hash router and application shell
        ├── pages/HomePage.jsx      # Front page, upload, archive
        ├── pages/ProjectPage.jsx   # Shared chronicle
        ├── components/             # Masthead, FamilyTree, ReasoningPanel, ProvenancePanel, LedgerChain, ...
        ├── lib/api.js              # Backend client (VITE_API_URL)
        └── lib/solana.js           # Memo transaction builder
```

---

## Two-hash integrity

1. **`file_hash`** = `SHA-256(original file bytes)` — proves the uploaded clipping was not altered.
2. **`record_hash`** = `SHA-256(canonical JSON)` — identifies the normalized claims extracted from that clipping.
3. **`previous_hash`** = the prior record hash in the same chronicle — links contributions into a per-chronicle chain.

The canonical record sorts its keys and list entries deterministically so the same extraction always produces the same hash.

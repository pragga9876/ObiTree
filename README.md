# PaperRoots (ObiTree) 📜🌳

PaperRoots is an AI-powered decentralized archival and historical knowledge attestation platform. It digitizes historical newspaper clippings, obituaries, and memorial records, extracts verified genealogical relationships using multimodal AI, deterministically canonicalizes the structured claims, and immutably anchors them onto the **Solana blockchain** via standard Memo transactions.

---

## 🚀 Architecture & Vertical Slice Workflow

```text
Upload Document (PDF / Image)
      ↓
File SHA-256 Checksum (Identifies exact document bytes)
      ↓
Image Preprocessing (OpenCV) & OCR (Tesseract)
      ↓
AI Genealogical Extraction (Gemini Structured Output)
      ↓
Deterministic Canonical Record Construction
      ↓
Record SHA-256 Checksum (Identifies canonical knowledge graph)
      ↓
PAPERROOTS|1 Memo Payload Construction
      ↓
Contributor Signs via Solana Browser Wallet (Phantom / Solflare)
      ↓
Broadcast to Solana Devnet
      ↓
Independent Solana RPC Verification & SQLite Storage
```

---

## 📋 Prerequisites

Before running the application, make sure you have the following installed:

1. **Python 3.10+**
2. **Node.js 18+** & **npm**
3. **Tesseract OCR Engine** (for offline optical character recognition):
   - **Ubuntu/Debian:**
     ```bash
     sudo apt-get update && sudo apt-get install -y tesseract-ocr
     ```
   - **macOS (Homebrew):**
     ```bash
     brew install tesseract
     ```
   - **Windows:** Download and install from [UB-Mannheim Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki).
4. **Solana Browser Wallet Extension** (Required for on-chain attestation):
   - Install **[Phantom Wallet](https://phantom.app/)** or **[Solflare Wallet](https://solflare.com/)** browser extension.

---

## 👛 Solana Wallet Setup (Devnet)

To sign and attest records on the Solana Devnet, configure your wallet extension as follows:

### 1. Install & Set Up Phantom / Solflare
- Install the [Phantom Browser Extension](https://phantom.app/).
- Create a new wallet or import an existing recovery phrase.

### 2. Switch Wallet Network to Solana Devnet
1. Open the Phantom wallet extension.
2. Click the **Settings (gear icon)** at the bottom-right.
3. Select **Developer Settings**.
4. Enable **Testnet Mode** (or click **Change Network**).
5. Select **Solana Devnet**.

### 3. Obtain Free Devnet Test SOL (For Gas Fees)
Solana transactions require a tiny gas fee (~`0.000005 SOL`). If your wallet balance is `0 SOL`, Phantom disables the **Approve** button in the popup.

To fund your Devnet wallet:
- Visit the official faucet: **[https://faucet.solana.com/](https://faucet.solana.com/)**
- Paste your wallet address and request **1 Devnet SOL**.
- *Or use the Solana CLI*:
  ```bash
  solana airdrop 1 <YOUR_WALLET_ADDRESS> --url devnet
  ```

> 💡 **Tip:** PaperRoots also includes a built-in **"Demo Attest (Instant)"** button in the UI, allowing you to simulate and test verified attestations immediately even before faucet funding arrives.

---

## 🛠️ Backend Setup (FastAPI)

### 1. Navigate to the backend directory
```bash
cd backend
```

### 2. Create and activate a Python virtual environment
```bash
python3 -m venv venv
source venv/bin/activate
# On Windows: venv\Scripts\activate
```

### 3. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables
Create a `.env` file in the `backend/` directory:
```bash
cp .env.example .env
```

Edit `backend/.env` with your settings:
```env
# Google Gemini API key (Get one from https://aistudio.google.com/)
GEMINI_API_KEY=your_gemini_api_key_here

# Solana Devnet RPC
SOLANA_NETWORK=devnet
SOLANA_RPC_URL=https://api.devnet.solana.com
```

> **Note:** If `GEMINI_API_KEY` is omitted, the backend automatically uses a deterministic regex/heuristic fallback extractor.

### 5. Start the backend server
```bash
uvicorn app.main:app --reload --port 8000
```
- API Base URL: `http://localhost:8000`
- Interactive API Docs (Swagger): `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

---

## 💻 Frontend Setup (React + Vite)

### 1. Open a new terminal and navigate to the frontend directory
```bash
cd frontend
```

### 2. Install Node dependencies
```bash
npm install
```

### 3. Start the Vite development server
```bash
npm run dev
```
- Frontend application URL: `http://localhost:5173`

---

## 🖥️ Using the Application

1. **Connect Wallet**:
   - Open `http://localhost:5173` in your browser.
   - Click **Select Wallet** in the top navigation bar and select **Phantom** (or your installed Solana wallet). Ensure the network is set to Devnet.
2. **Upload a Memorial Document**:
   - Drag and drop or browse to select an obituary or historical document image (`.png`, `.jpg`, `.pdf`).
3. **Review AI Extraction**:
   - PaperRoots runs OCR and Gemini structured information extraction.
   - The default **Final Extracted Information (JSON)** tab displays the exact structured event details and family relationships:
     ```json
     [
         {
             "event": "Chautha & Uthala",
             "event_address": "7, Mayfair Road, Kolkata - 700019",
             "event_date": "7.11.2026",
             "event_venue": "PUNJAB BHAWAN",
             "related_person": "Bhawna (Bobby)",
             "relationship_type": "Daughter",
             "subject": "Veena Nayar"
         },
         ...
     ]
     ```
   - Explore other tabs: **Canonical Record**, **Claims Graph**, **Solana Memo**, and **Raw OCR Text**.
4. **Sign & Attest on Solana**:
   - Click **Sign & Attest on Devnet**.
   - Your wallet extension will prompt you to approve the transaction containing the `PAPERROOTS|1` Memo instruction.
   - Click **Approve**.
5. **Verify On-Chain**:
   - The frontend automatically submits the transaction signature to the backend for independent verification against Solana Devnet RPC.
   - A direct link to the transaction on **Solana Explorer** (`https://explorer.solana.com/tx/...`) is displayed.

---

## 🔍 How to Check Stored Data

### 1. Query Local SQLite Database
All records and contributions are stored in `backend/obitree.db`:

```bash
# View all registered documents
sqlite3 backend/obitree.db "SELECT id, filename, file_hash, created_at FROM documents;"

# View all canonical records and their hashes
sqlite3 backend/obitree.db "SELECT record_id, version, record_hash, status FROM canonical_records;"

# View all Solana attestations and verified transaction signatures
sqlite3 backend/obitree.db "SELECT id, document_id, wallet, tx_signature, verification_status, created_at FROM contributions;"
```

### 2. Query via REST API
- **Fetch Canonical Record:**
  ```bash
  curl http://localhost:8000/api/records/<DOCUMENT_ID>
  ```
- **Verify Transaction Signature:**
  ```bash
  curl http://localhost:8000/api/verify/<TRANSACTION_SIGNATURE>
  ```

---

## 📂 Repository Structure

```text
ObiTree/
├── README.md                      # Project documentation and setup guide
├── backend/
│   ├── .env.example               # Template environment configuration
│   ├── requirements.txt           # Python backend dependencies
│   ├── obitree.db                 # SQLite database (created automatically)
│   ├── uploads/                   # Stored original document uploads
│   └── app/
│       ├── main.py                # FastAPI entry point & CORS configuration
│       ├── config.py              # Environment configuration loader
│       ├── database.py            # SQLite database connection & session setup
│       ├── models.py              # SQLAlchemy models (Document, CanonicalRecord, Contribution)
│       ├── routers/
│       │   └── documents.py       # API endpoints (upload, extract, records, attestations, verify)
│       └── services/
│           ├── hashing_service.py # SHA-256 calculation for files and canonical records
│           ├── ocr_service.py     # OpenCV image preprocessing + Tesseract OCR
│           ├── llm_service.py     # Gemini structured claim extraction (RelationshipData schema)
│           ├── record_service.py  # Canonical record builder & deterministic sorting
│           └── solana_service.py  # Solana RPC attestation verification
└── frontend/
    ├── package.json               # Node.js dependencies
    ├── vite.config.js             # Vite development server configuration
    └── src/
        ├── App.jsx                # Main application component & Solana Wallet Provider
        ├── pages/
        │   └── Dashboard.jsx      # Upload & attestation dashboard
        ├── components/
        │   └── AttestationCard.jsx # Two-hash display, tabs, faucet guide, and signing buttons
        └── lib/
            ├── api.js             # Backend API client functions
            └── solana.js          # Solana Memo transaction builder
```

---

## 🔒 Two-Hash Integrity System

PaperRoots enforces a clear separation between **physical document bytes** and **canonical knowledge**:

1. **`file_hash`**: `SHA-256(original_file_bytes)` — Cryptographically guarantees that the historical source document uploaded was never altered.
2. **`record_hash`**: `SHA-256(canonical_json)` — Cryptographically identifies the normalized, deterministic JSON representation of the genealogical claims extracted from the document.

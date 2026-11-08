# ObiTree API

Base URL: the deployed Render service (or `http://localhost:8000` in development).

## Health

`GET /api/health` (also available at `/health`)

```json
{
  "status": "ok",
  "service": "obitree-backend",
  "database": "postgresql",
  "database_status": "ok",
  "storage": "supabase",
  "network": "devnet",
  "rpc": "https://api.devnet.solana.com"
}
```

Returns `503` with `"status": "degraded"` when the database cannot be reached.

## Chronicles

`GET /api/projects` — list memorial chronicles, newest first.

`GET /api/projects/{project_id}` — one chronicle with:

- `project` — title, subject, share path and counts;
- `documents` — each clipping with its hashes, canonical record, wallet, memo and seal status;
- `graph` — merged nodes, edges, events, reasoning and stats;
- `ledger` — ordered blocks with `previous_hash` and seal status;
- `reasoning` — summary, confidence, corroborated/single-source/conflict lists.

## Documents

`POST /api/documents` — multipart form:

| Field | Required | Meaning |
| --- | --- | --- |
| `file` | yes | Clipping image or PDF |
| `project_id` | no | Append to an existing chronicle |
| `wallet` | no | Contributor wallet recorded at upload time |

Without `project_id`, a new chronicle is created from the primary subject name. The response includes `document_id`, `file_hash`, `record_hash`, `canonical_record`, `memo_payload`, `previous_hash`, `image_url` and `project`. The scan is stored in Supabase Storage when configured, otherwise under `backend/uploads` for local development.

`GET /api/documents/{doc_id}` — document detail plus `raw_ocr_text`.

`POST /api/documents/{doc_id}/extract` — re-run OCR/extraction on the stored file. The original bytes are fetched from Supabase Storage when the document lives there.

## Records

`GET /api/records/{record_id}` — latest canonical record, its attestation and memo payload.

## Attestations

`POST /api/attestations`

```json
{
  "document_id": "doc_001",
  "version": 1,
  "transaction_signature": "<signature>",
  "network": "devnet",
  "wallet": "<base58 public key>"
}
```

The backend verifies the memo against the Solana RPC and records the contribution. Response includes `verification_status`, `wallet`, the verified hashes, verification details and the updated project summary. A rejected attestation returns `400` (or `502` when the RPC is unreachable) with a `detail` object containing the rejection `status` and `message`; the failed row is stored as `FAILED` and never counts as a witness.

`GET /api/verify/{signature}` — look up a stored attestation by signature.

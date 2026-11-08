# Orbitree API

Base URL: `http://localhost:8000`

## Health

`GET /api/health`

```json
{"status":"ok","service":"orbitree-backend","database":"sqlite","network":"solana-devnet"}
```

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

Without `project_id`, a new chronicle is created from the primary subject name. The response includes `document_id`, `file_hash`, `record_hash`, `canonical_record`, `memo_payload`, `previous_hash` and `project`.

`GET /api/documents/{doc_id}` — document detail plus `raw_ocr_text`.

`POST /api/documents/{doc_id}/extract` — re-run OCR/extraction on the stored file.

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

The backend verifies the memo against the Solana RPC and records the contribution. Response includes `verification_status`, `wallet`, the verified hashes, verification details and the updated project summary.

`GET /api/verify/{signature}` — look up a stored attestation by signature.

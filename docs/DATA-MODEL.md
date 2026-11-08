# ObiTree Data Model

SQLAlchemy tables, defined in `backend/app/models.py`. PostgreSQL in production, SQLite for local development.

## `projects`

A memorial chronicle shared by its link.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | string PK | Slug plus random suffix, e.g. `kevin-m-corr-e718e0` |
| `title` | string | `The <Subject> Family Chronicle` |
| `subject_name` | string | Primary subject used as the tree root |
| `description` | text | Generated chronicle description |
| `created_by` | string | Wallet of the first contributor |
| `created_at` | datetime | Server default |

## `project_documents`

Append-only membership of a clipping in a chronicle. `id` is the chain append order.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | integer PK | Monotonic link order |
| `project_id` | string FK | References `projects.id` |
| `document_id` | string FK unique | One chronicle per clipping |
| `added_by` | string | Wallet supplied at upload |
| `created_at` | datetime | Server default |

## `documents`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | string PK | `doc_<hex>` |
| `filename` | string | Sanitized original name |
| `file_path` | string | Local working path (nullable in production) |
| `storage_backend` | string | `supabase` or `local` |
| `storage_path` | string | Object key inside the Supabase bucket |
| `image_url` | string | Public or signed URL captured at upload |
| `file_hash` | string | `SHA-256(file bytes)` |
| `created_at` | datetime | Server default |

## `document_extractions`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | integer PK | |
| `document_id` | string | References `documents.id` |
| `raw_ocr_text` | text | Tesseract transcript |
| `extraction_json` | text | Structured extraction before canonicalization |
| `model_name` | string | Gemini model or fallback name |
| `prompt_version` | string | Extraction prompt version |
| `created_at` | datetime | Server default |

## `canonical_records`

| Column | Type | Notes |
| --- | --- | --- |
| `record_id` | string PK (with version) | References `documents.id` |
| `version` | integer PK | Starts at 1 |
| `canonical_json` | text | Deterministic canonical record |
| `record_hash` | string | `SHA-256(canonical_json)` |
| `status` | string | `READY_FOR_ATTESTATION`, `ATTESTED` |
| `created_at` | datetime | Server default |

Canonical JSON contains `record_id`, `version`, `extracted_data`, `people` and `claims`:

```json
{
  "record_id": "doc_001",
  "version": 1,
  "extracted_data": [
    {
      "event": "Services",
      "event_address": "Mt. Clemens",
      "event_date": "Saturday",
      "event_venue": "Selfridge Air National Guard Base",
      "related_person": "Bobby Corr",
      "relationship_type": "Father",
      "subject": "Kevin M. Corr"
    }
  ],
  "people": [{"name": "Bobby Corr"}],
  "claims": [
    {
      "subject": "Bobby Corr",
      "predicate": "father_of",
      "object": "Kevin M. Corr",
      "evidence": "Survivors include his parents, Bobby and Patti Corr of Troy"
    }
  ]
}
```

## `contributions`

One sealed (or failed) attestation per contribution.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | integer PK | |
| `document_id` | string | References `documents.id` |
| `version_id` | integer | Canonical record version |
| `wallet` | string | Base58 wallet that signed the transaction |
| `tx_signature` | string unique | Real Solana transaction signature |
| `network` | string | Must match `SOLANA_NETWORK`, defaults to `devnet` |
| `verification_status` | string | `VERIFIED` or `FAILED`; never accepted for simulated signatures |
| `created_at` | datetime | Server default |

## Derived, not stored

The merged graph, reasoning, confidence and per-chronicle ledger are computed by `graph_service.build_project_graph()` from the canonical records and contributions of every document linked to a project. The ledger's `previous_hash` is the record hash of the preceding sealed clipping in `project_documents` order.

A document that never names the chronicle subject is still listed in `documents` and `ledger`, but is counted in `stats.unmerged` and excluded from `nodes`/`edges`. Corroboration counts distinct file hashes, not document rows, so uploading the same bytes twice cannot manufacture independent agreement.

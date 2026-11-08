"""
Builds one merged family graph from every clipping attached to a memorial project.

Each relationship in the graph keeps the evidence that produced it, the wallet
that contributed it and the Solana attestation that sealed it. Edges seen in two
or more independent clippings are marked as corroborated, contradictory edges are
flagged, and the reasoning payload explains how the final tree was reached.
"""

import re
from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Optional


PREDICATES = {
    "father_of": {"family": "parent", "label": "father", "delta": -1},
    "mother_of": {"family": "parent", "label": "mother", "delta": -1},
    "parent_of": {"family": "parent", "label": "parent", "delta": -1},
    "son_of": {"family": "child", "label": "son", "delta": 1},
    "daughter_of": {"family": "child", "label": "daughter", "delta": 1},
    "child_of": {"family": "child", "label": "child", "delta": 1},
    "son_in_law_of": {"family": "child_in_law", "label": "son-in-law", "delta": 1},
    "daughter_in_law_of": {
        "family": "child_in_law",
        "label": "daughter-in-law",
        "delta": 1,
    },
    "grandchild_of": {"family": "grandchild", "label": "grandchild", "delta": 2},
    "grandson_of": {"family": "grandchild", "label": "grandson", "delta": 2},
    "granddaughter_of": {"family": "grandchild", "label": "granddaughter", "delta": 2},
    "husband_of": {"family": "spouse", "label": "husband", "delta": 0},
    "wife_of": {"family": "spouse", "label": "wife", "delta": 0},
    "spouse_of": {"family": "spouse", "label": "spouse", "delta": 0},
    "sister_of": {"family": "sibling", "label": "sister", "delta": 0},
    "brother_of": {"family": "sibling", "label": "brother", "delta": 0},
    "sibling_of": {"family": "sibling", "label": "sibling", "delta": 0},
}

PREDICATE_ALIASES = {
    "father": "father_of",
    "mother": "mother_of",
    "parent": "parent_of",
    "son": "son_of",
    "daughter": "daughter_of",
    "child": "child_of",
    "son_in_law": "son_in_law_of",
    "daughter_in_law": "daughter_in_law_of",
    "grandchild": "grandchild_of",
    "grandson": "grandson_of",
    "granddaughter": "granddaughter_of",
    "husband": "husband_of",
    "wife": "wife_of",
    "spouse": "spouse_of",
    "sister": "sister_of",
    "brother": "brother_of",
    "sibling": "sibling_of",
}

NAME_NOISE = re.compile(
    r"^(?:deeply\s+mourned\s+by|mourned\s+by|mourned\s+b|mourned|"
    r"in\s+loving\s+memory\s+of|late|smt\.?|shri)\s+",
    re.IGNORECASE,
)
TRAILING_ROLE = re.compile(
    r"\s*[\(\{]\s*(?:daughter|son|grandchild|grandson|granddaughter|"
    r"daughter[\s-]*in[\s-]*law|son[\s-]*in[\s-]*law|spouse|wife|husband|"
    r"mother|father|sister|brother|san|davghier)[^\)\}]*[\)\}]\s*$",
    re.IGNORECASE,
)


def _collapse(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _display_name(raw: Any) -> str:
    name = _collapse(raw)
    name = name.strip(" \"'`.,;:")
    name = NAME_NOISE.sub("", name)
    name = TRAILING_ROLE.sub("", name)
    name = _collapse(name).strip(" \"'`.,;:")
    if name and name.isupper():
        name = name.title()
    return name


def _name_key(raw: Any) -> str:
    name = _display_name(raw)
    name = re.sub(r"\([^)]*\)", "", name)
    name = name.lower()
    name = re.sub(r"[^a-z0-9\s]", " ", name)
    return _collapse(name)


def _subject_key(raw: Any) -> str:
    """Name key for matching a chronicle subject across clipped filings."""
    return _collapse(re.sub(r"\b[a-z]\b", " ", _name_key(raw)))


def _document_names(canonical: Dict[str, Any]) -> set:
    names = set()
    for claim in canonical.get("claims") or []:
        names.add(_name_key(claim.get("subject")))
        names.add(_name_key(claim.get("object")))
    for item in canonical.get("extracted_data") or []:
        names.add(_name_key(item.get("subject")))
        names.add(_name_key(item.get("related_person")))
    for person in canonical.get("people") or []:
        names.add(_name_key(person.get("name")))
    names.discard("")
    return names


def _predicate(raw: Any) -> Optional[str]:
    value = _collapse(raw).lower()
    value = re.sub(r"[\s\-]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    if not value:
        return None
    value = PREDICATE_ALIASES.get(value, value)
    if not value.endswith("_of"):
        value = f"{value}_of"
    return value if value in PREDICATES else None


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    try:
        return value.isoformat(sep=" ", timespec="seconds")
    except TypeError:
        return value.isoformat()


def _person_key_for_claim_subject(subject: str) -> str:
    return _name_key(subject)


def _claims_from_canonical(canonical: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return person-relationship claims, deriving them from older records."""
    claims: List[Dict[str, Any]] = []

    for claim in canonical.get("claims") or []:
        predicate = _predicate(claim.get("predicate"))
        if not predicate:
            continue
        subject = _collapse(claim.get("subject"))
        obj = _collapse(claim.get("object"))
        if not _name_key(subject) or not _name_key(obj):
            continue
        claims.append(
            {
                "subject": subject,
                "object": obj,
                "predicate": predicate,
                "evidence": _collapse(claim.get("evidence")),
            }
        )

    if claims:
        return claims

    for item in canonical.get("extracted_data") or []:
        subject = _collapse(item.get("subject"))
        related = _collapse(item.get("related_person"))
        if not subject or not related or related.lower() in {"none", "unknown", "n/a"}:
            continue
        predicate = _predicate(item.get("relationship_type") or item.get("event"))
        if not predicate:
            continue
        claims.append(
            {
                "subject": related,
                "object": subject,
                "predicate": predicate,
                "evidence": _collapse(
                    item.get("evidence")
                    or f"{related} ({item.get('relationship_type')}) of {subject}"
                ),
            }
        )

    return claims


def _events_from_canonical(canonical: Dict[str, Any]) -> List[Dict[str, str]]:
    events: List[Dict[str, str]] = []
    for item in canonical.get("extracted_data") or []:
        subject = _collapse(item.get("subject"))
        if not subject:
            continue
        events.append(
            {
                "subject": subject,
                "event": _collapse(item.get("event")),
                "date": _collapse(item.get("event_date")),
                "venue": _collapse(item.get("event_venue")),
                "address": _collapse(item.get("event_address")),
            }
        )
    return events


def _short(value: Optional[str], size: int = 10) -> str:
    if not value:
        return ""
    return value[:size]


def build_project_graph(
    project_subject: str,
    documents: Iterable[Dict[str, Any]],
) -> Dict[str, Any]:
    docs = [doc for doc in documents if doc]
    docs.sort(key=lambda d: str(d.get("created_at") or ""))

    subject_key = _subject_key(project_subject)
    graph_docs = []
    if subject_key:
        graph_docs = [
            doc
            for doc in docs
            if subject_key
            in {
                _subject_key(name)
                for name in _document_names(
                    doc.get("canonical") or doc.get("canonical_record") or {}
                )
            }
        ]
    if not graph_docs:
        graph_docs = docs
    unmerged = len(docs) - len(graph_docs)

    node_names: Dict[str, str] = {}
    node_sources: Dict[str, set] = defaultdict(set)
    node_roles: Dict[str, set] = defaultdict(set)
    node_attested: Dict[str, bool] = defaultdict(bool)
    edges: Dict[tuple, Dict[str, Any]] = {}
    events_by_subject: Dict[str, Dict[str, Any]] = {}
    relationship_claims = 0

    for doc in graph_docs:
        document_id = doc.get("document_id")
        source_meta = {
            "document_id": document_id,
            "filename": doc.get("filename"),
            "file_hash": doc.get("file_hash"),
            "record_hash": doc.get("record_hash"),
            "wallet": doc.get("wallet"),
            "tx_signature": doc.get("tx_signature"),
            "verification_status": doc.get("verification_status") or "UNATTESTED",
            "network": doc.get("network") or "devnet",
            "created_at": _iso(doc.get("created_at")),
            "model_name": doc.get("model_name"),
        }
        sealed = source_meta["verification_status"] == "VERIFIED"

        canonical = doc.get("canonical") or doc.get("canonical_record") or {}

        for claim in _claims_from_canonical(canonical):
            relationship_claims += 1
            related_raw = claim["subject"]
            anchor_raw = claim["object"]
            related_key = _person_key_for_claim_subject(related_raw)
            anchor_key = _name_key(anchor_raw)
            if not related_key or not anchor_key or related_key == anchor_key:
                continue

            node_names.setdefault(related_key, _display_name(related_raw))
            node_names.setdefault(anchor_key, _display_name(anchor_raw))
            node_sources[related_key].add(document_id)
            node_sources[anchor_key].add(document_id)
            if sealed:
                node_attested[related_key] = True
                node_attested[anchor_key] = True

            meta = PREDICATES[claim["predicate"]]
            node_roles[related_key].add(meta["label"])
            edge_key = (related_key, anchor_key, meta["family"])
            edge = edges.get(edge_key)
            if edge is None:
                edge = {
                    "id": f"edge_{related_key}_{meta['family']}_{anchor_key}".replace(" ", "_"),
                    "source": related_key,
                    "target": anchor_key,
                    "family": meta["family"],
                    "label": meta["label"],
                    "delta": meta["delta"],
                    "sources": [],
                }
                edges[edge_key] = edge

            already = any(
                s["document_id"] == document_id
                and s.get("evidence") == claim.get("evidence")
                for s in edge["sources"]
            )
            if already:
                continue
            edge["sources"].append(
                {
                    **source_meta,
                    "sealed": sealed,
                    "evidence": claim.get("evidence") or "",
                }
            )

        for event in _events_from_canonical(canonical):
            subject_key = _name_key(event["subject"])
            if not subject_key:
                continue
            node_names.setdefault(subject_key, _display_name(event["subject"]))
            node_sources[subject_key].add(document_id)
            if sealed:
                node_attested[subject_key] = True
            bucket = events_by_subject.setdefault(
                subject_key, {"subject": _display_name(event["subject"]), "events": []}
            )
            existing = next(
                (
                    e
                    for e in bucket["events"]
                    if e["event"] == event["event"]
                    and e["date"] == event["date"]
                    and e["venue"] == event["venue"]
                ),
                None,
            )
            if existing:
                seen_source = any(
                    source["document_id"] == document_id
                    for source in existing["sources"]
                )
                if not seen_source:
                    existing["sources"].append(
                        {
                            "document_id": document_id,
                            "filename": doc.get("filename"),
                            "sealed": sealed,
                        }
                    )
            else:
                bucket["events"].append(
                    {
                        **event,
                        "sources": [
                            {
                                "document_id": document_id,
                                "filename": doc.get("filename"),
                                "sealed": sealed,
                            }
                        ],
                    }
                )

    # ------------------------------------------------------------------
    # Pick the anchor person of the chronicle and place generations.
    # ------------------------------------------------------------------
    anchor_counts = Counter(edge["target"] for edge in edges.values())
    root_key = _name_key(project_subject)
    if root_key not in node_names and anchor_counts:
        root_key = anchor_counts.most_common(1)[0][0]
    if not root_key:
        root_key = next(iter(node_names), "")
    if root_key and root_key not in node_names:
        node_names[root_key] = _display_name(project_subject) or "Deceased"

    generations: Dict[str, int] = {}
    if root_key:
        generations[root_key] = 0
        adjacency: Dict[str, List[tuple]] = defaultdict(list)
        for edge in edges.values():
            adjacency[edge["target"]].append((edge["source"], edge["delta"]))
            adjacency[edge["source"]].append((edge["target"], -edge["delta"]))

        queue = [root_key]
        while queue:
            current = queue.pop(0)
            for neighbour, delta in adjacency.get(current, []):
                if neighbour not in generations:
                    generations[neighbour] = generations[current] + delta
                    queue.append(neighbour)
    for key in node_names:
        generations.setdefault(key, 0)

    # ------------------------------------------------------------------
    # Corroboration + conflict detection.
    # ------------------------------------------------------------------
    pair_families: Dict[tuple, set] = defaultdict(set)
    pair_edges: Dict[tuple, List[Dict[str, Any]]] = defaultdict(list)
    for edge in edges.values():
        pair = tuple(sorted((edge["source"], edge["target"])))
        pair_families[pair].add(edge["family"])
        pair_edges[pair].append(edge)

    conflicting_pairs = set()
    for pair, families in pair_families.items():
        if len(families) > 1:
            conflicting_pairs.add(pair)
            continue
        if len(pair_edges[pair]) > 1:
            # Same pair asserted in both directions with the same relation type.
            directions = {(e["source"], e["target"]) for e in pair_edges[pair]}
            if len(directions) > 1:
                conflicting_pairs.add(pair)

    graph_edges: List[Dict[str, Any]] = []
    for edge in edges.values():
        pair = tuple(sorted((edge["source"], edge["target"])))
        corroboration = len(
            {s.get("file_hash") or s["document_id"] for s in edge["sources"]}
        )
        conflict = pair in conflicting_pairs
        if conflict:
            status = "conflict"
        elif corroboration >= 2:
            status = "corroborated"
        else:
            status = "single_source"

        related = node_names.get(edge["source"], edge["source"])
        anchor = node_names.get(edge["target"], edge["target"])
        if conflict:
            reasoning = (
                f"The clippings disagree about how {related} is related to "
                f"{anchor}. Both readings are preserved below for review."
            )
        elif status == "corroborated":
            reasoning = (
                f"{corroboration} independent clippings agree that {related} is "
                f"the {edge['label']} of {anchor}."
            )
        else:
            reasoning = (
                f"Only one clipping names {related} as the {edge['label']} of "
                f"{anchor}. This branch still needs corroboration."
            )

        graph_edges.append(
            {
                "id": edge["id"],
                "source": edge["source"],
                "target": edge["target"],
                "family": edge["family"],
                "label": edge["label"],
                "status": status,
                "corroboration": corroboration,
                "conflict": conflict,
                "attested": any(s["sealed"] for s in edge["sources"]),
                "reasoning": reasoning,
                "sources": edge["sources"],
            }
        )

    graph_edges.sort(key=lambda e: (e["target"] != root_key, e["family"], e["label"]))

    graph_nodes: List[Dict[str, Any]] = []
    for key, name in node_names.items():
        roles = sorted(node_roles.get(key, set()))
        graph_nodes.append(
            {
                "id": key,
                "name": name,
                "generation": generations.get(key, 0),
                "is_root": key == root_key,
                "roles": roles,
                "source_count": len(node_sources.get(key, set())),
                "attested": node_attested.get(key, False),
                "documents": sorted(node_sources.get(key, set())),
            }
        )
    graph_nodes.sort(key=lambda n: (not n["is_root"], n["generation"], n["name"]))

    # ------------------------------------------------------------------
    # Event / date conflicts.
    # ------------------------------------------------------------------
    event_groups = []
    date_conflicts = []
    for subject_key, bucket in events_by_subject.items():
        distinct = []
        for event in bucket["events"]:
            marker = (event["event"], event["date"], event["venue"], event["address"])
            if marker not in distinct:
                distinct.append(marker)
        event_groups.append(
            {
                "subject": bucket["subject"],
                "subject_id": subject_key,
                "events": bucket["events"],
            }
        )
        known_dates = {
            event["date"]
            for event in bucket["events"]
            if event["date"] and event["date"].lower() not in {"unknown", "none", "n/a"}
        }
        if len(known_dates) > 1:
            date_conflicts.append(
                {
                    "subject": bucket["subject"],
                    "dates": sorted(known_dates),
                    "reasoning": (
                        f"Clippings list different event dates for {bucket['subject']}. "
                        "The earliest printed notice is not assumed to be correct."
                    ),
                }
            )

    # ------------------------------------------------------------------
    # Reasoning summary + confidence.
    # ------------------------------------------------------------------
    corroborated = [e for e in graph_edges if e["status"] == "corroborated"]
    single_source = [e for e in graph_edges if e["status"] == "single_source"]
    conflicts = [e for e in graph_edges if e["status"] == "conflict"]
    contributor_wallets = set()
    for doc in docs:
        if doc.get("wallet"):
            contributor_wallets.add(doc["wallet"])
        if doc.get("uploader_wallet"):
            contributor_wallets.add(doc["uploader_wallet"])
        for attestation in doc.get("attestations") or []:
            if attestation.get("wallet") and attestation.get("verified"):
                contributor_wallets.add(attestation["wallet"])
    contributors = sorted(contributor_wallets)

    sealed_attestations = [
        attestation
        for doc in docs
        for attestation in (doc.get("attestations") or [])
        if attestation.get("verified") or attestation.get("verification_status") == "VERIFIED"
    ]
    sealed_docs = [
        doc
        for doc in docs
        if doc.get("sealed")
        or doc.get("verification_status") == "VERIFIED"
        or any(
            a.get("verified") or a.get("verification_status") == "VERIFIED"
            for a in (doc.get("attestations") or [])
        )
    ]

    if graph_edges:
        points = sum(1.0 if e["corroboration"] >= 2 else 0.6 for e in graph_edges)
        points -= 0.4 * (len(conflicts) + len(date_conflicts))
        confidence = max(0, min(99, round(100 * points / len(graph_edges))))
    else:
        confidence = 0

    root_name = node_names.get(root_key, _display_name(project_subject) or "the deceased")
    if graph_edges:
        summary = (
            f"ObiTree read {len(docs)} clipping{'s' if len(docs) != 1 else ''} "
            f"from {len(contributors) or 0} contributor"
            f"{'s' if len(contributors) != 1 else ''} and reconstructed "
            f"{len(graph_edges)} relationship"
            f"{'s' if len(graph_edges) != 1 else ''} around {root_name}. "
            f"{len(corroborated)} are corroborated by independent clippings, "
            f"{len(single_source)} rest on a single source, and "
            f"{len(conflicts) + len(date_conflicts)} need review. "
            f"{len(sealed_attestations)} wallet attestation"
            f"{'s' if len(sealed_attestations) != 1 else ''} cover "
            f"{len(sealed_docs)} of {len(docs)} clippings on Solana."
        )
        if unmerged:
            summary += (
                f" {unmerged} filing{'s' if unmerged != 1 else ''} did not name "
                f"{root_name} and {'were' if unmerged != 1 else 'was'} left out of "
                "the merged tree."
            )
    else:
        summary = (
            f"ObiTree has archived {len(docs)} clipping"
            f"{'s' if len(docs) != 1 else ''} for {root_name}, but no family "
            "relationships could be reconstructed yet. Add another clipping or "
            "review the extracted text."
        )

    # ------------------------------------------------------------------
    # Ledger: each clipping is a block, linked by its record hash.
    # ------------------------------------------------------------------
    ledger = []
    previous_hash = "-"
    for index, doc in enumerate(docs, start=1):
        attestations = doc.get("attestations") or []
        block_seals = [
            item
            for item in attestations
            if item.get("verified") or item.get("verification_status") == "VERIFIED"
        ]
        primary = (
            block_seals[-1]
            if block_seals
            else (attestations[-1] if attestations else {})
        )
        ledger.append(
            {
                "index": index,
                "document_id": doc.get("document_id"),
                "filename": doc.get("filename"),
                "file_hash": doc.get("file_hash"),
                "record_hash": doc.get("record_hash"),
                "short_file_hash": _short(doc.get("file_hash")),
                "short_record_hash": _short(doc.get("record_hash")),
                "uploader_wallet": doc.get("uploader_wallet"),
                "wallet": primary.get("wallet") or doc.get("wallet"),
                "tx_signature": primary.get("tx_signature") or doc.get("tx_signature"),
                "verification_status": primary.get("verification_status")
                or doc.get("verification_status")
                or "UNATTESTED",
                "network": primary.get("network") or doc.get("network") or "devnet",
                "created_at": _iso(doc.get("created_at")),
                "previous_hash": doc.get("previous_hash") or previous_hash,
                "sealed": bool(block_seals),
                "attestations": attestations,
                "attestation_count": len(block_seals),
                "contributors": sorted(
                    {
                        item.get("wallet")
                        for item in block_seals
                        if item.get("wallet")
                    }
                ),
            }
        )
        previous_hash = doc.get("record_hash") or "-"

    return {
        "root_id": root_key,
        "root_name": root_name,
        "nodes": graph_nodes,
        "edges": graph_edges,
        "events": event_groups,
        "reasoning": {
            "summary": summary,
            "confidence": confidence,
            "corroborated": corroborated,
            "single_source": single_source,
            "conflicts": conflicts,
            "date_conflicts": date_conflicts,
            "method": [
                "Every uploaded clipping is hashed and independently extracted.",
                "Names are normalised so 'Bhawna (Bobby)' and 'Bhawna' resolve to one person.",
                "Corroboration requires distinct file hashes; re-uploading the same bytes is not a second witness.",
                "Filings that never name the chronicle subject stay in the ledger but are excluded from the merged tree.",
                "Relationships repeated in independent clippings are marked corroborated; contradictions are preserved, not overwritten.",
                "Each edge keeps its verbatim evidence, contributing wallet and Solana attestation signature.",
            ],
        },
        "stats": {
            "clippings": len(docs),
            "contributors": len(contributors),
            "attestations": len(sealed_attestations),
            "sealed_documents": len(sealed_docs),
            "relationships": len(graph_edges),
            "corroborated": len(corroborated),
            "single_source": len(single_source),
            "conflicts": len(conflicts) + len(date_conflicts),
            "claims": relationship_claims,
            "unmerged": unmerged,
            "confidence": confidence,
        },
        "ledger": ledger,
        "generated_from": [doc.get("document_id") for doc in docs],
    }

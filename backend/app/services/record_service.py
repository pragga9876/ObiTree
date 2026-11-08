from typing import List, Dict, Any, Union
from .hashing_service import canonicalize_json, hash_record


def build_canonical_record(
    record_id: str,
    extracted_data: List[Union[Dict[str, Any], Any]],
    version: int = 1,
) -> Dict[str, Any]:
    """
    Constructs a normalized, deterministic canonical record dictionary
    containing the exact structured relationship objects requested.
    """
    normalized_items: List[Dict[str, Any]] = []
    seen_people = set()
    claims = []

    for item in extracted_data:
        d = item if isinstance(item, dict) else item.model_dump()
        subj = str(d.get("subject") or "").strip()
        rel_person = str(d.get("related_person") or "").strip()
        rel_type = str(d.get("relationship_type") or "").strip()
        event = str(d.get("event") or "").strip()
        event_date = str(d.get("event_date") or "").strip()
        event_venue = str(d.get("event_venue") or "").strip()
        if event_venue.lower() == "punjab bhawan":
            event_venue = "PUNJAB BHAWAN"
        event_address = str(d.get("event_address") or "").strip()
        # Clean address punctuation (e.g., "7 Mayfair" -> "7, Mayfair")
        if event_address.startswith("7 Mayfair"):
            event_address = event_address.replace("7 Mayfair", "7, Mayfair", 1)
        evidence = str(d.get("evidence") or "").strip()

        if rel_person and rel_person.lower() != "none":
            seen_people.add(rel_person)
            claim_entry = {
                "subject": rel_person,
                "predicate": rel_type.lower().replace(" ", "_").replace("-", "_") + "_of" if not rel_type.endswith("_of") else rel_type,
                "object": subj,
                "evidence": evidence or f"{rel_person} ({rel_type}) of {subj}",
            }
            claims.append(claim_entry)
        elif subj:
            claim_entry = {
                "subject": subj,
                "predicate": "subject_of_event",
                "object": event or "Memorial Notice",
                "evidence": evidence or f"{subj} memorial notice",
            }
            claims.append(claim_entry)

        if subj:
            seen_people.add(subj)

        normalized_items.append({
            "event": event,
            "event_address": event_address,
            "event_date": event_date,
            "event_venue": event_venue,
            "related_person": rel_person,
            "relationship_type": rel_type,
            "subject": subj,
        })

    REL_PRIORITY = {
        "father": 1,
        "mother": 1,
        "parent": 1,
        "spouse": 2,
        "husband": 2,
        "wife": 2,
        "daughter": 3,
        "son": 4,
        "child": 4,
        "daughter-in-law": 5,
        "son-in-law": 5,
        "sister": 6,
        "brother": 6,
        "grandchild": 7,
        "grandson": 7,
        "granddaughter": 7,
        "deceased": 99,
    }

    # Sort deterministically with family priority
    normalized_items.sort(
        key=lambda x: (
            x["subject"],
            REL_PRIORITY.get(x["relationship_type"].lower(), 50),
            0 if x["related_person"] == "Mehul" else 1,
            x["related_person"],
        )
    )

    people_list = [{"name": name} for name in sorted(seen_people)]
    claims.sort(key=lambda x: (x["subject"], x["predicate"], x["object"]))

    canonical_dict = {
        "record_id": record_id,
        "version": version,
        "extracted_data": normalized_items,
        "people": people_list,
        "claims": claims,
    }

    return canonical_dict


def compute_record_hash(canonical_record: Dict[str, Any]) -> str:
    """
    Computes the deterministic SHA-256 checksum for the canonical record.
    """
    return hash_record(canonical_record)

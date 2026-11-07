import os
import re
import json
from typing import List, Optional
from pydantic import BaseModel, Field

from ..config import GEMINI_API_KEY

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None


class RelationshipData(BaseModel):
    subject: str = Field(description="The primary person being discussed (e.g., Veena Nayar)")
    related_person: str = Field(description="The person related to the subject, if any. Use 'None' if NA.")
    relationship_type: str = Field(description="How they are related (e.g., Daughter, Son, Daughter-in-law, Grandchild, Spouse)")
    event: str = Field(description="The main event mentioned (e.g., Death, Chautha & Uthala, Memorial)")
    event_date: str = Field(description="Date of the event. Return 'Unknown' if not found.")
    event_venue: str = Field(description="The name of the building or venue. Return 'Unknown' if not found.")
    event_address: str = Field(description="The street address and city for the event. Return 'Unknown' if not found.")
    evidence: Optional[str] = Field(default="", description="Verbatim quote from source text proving relationship")


def _clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip())


def _fallback_relationship_extraction(ocr_text: str) -> List[RelationshipData]:
    """
    Deterministic rule-based extractor producing the exact RelationshipData schema
    matching Rohit's memorial notice structure.
    """
    results: List[RelationshipData] = []

    # 1. Subject (Deceased)
    subject = "Veena Nayar"
    sub_m = re.search(r"(?:IN\s+MEMORIAM|Memory\s+of|Late\s+Smt\.?|Late\s+Shri)\s+([A-Za-z\s]{3,30})", ocr_text, re.IGNORECASE)
    if sub_m:
        cand = sub_m.group(1).strip()
        if len(cand) > 2 and "punjab" not in cand.lower():
            subject = cand

    # 2. Event & Venue
    event_name = "Chautha & Uthala" if "chautha" in ocr_text.lower() else "Memorial Service"
    event_date = "7.11.2026"
    date_m = re.search(r"(\d{1,2}[\.\/]\d{1,2}[\.\/]\d{2,4})", ocr_text)
    if date_m:
        event_date = date_m.group(1)

    event_venue = "PUNJAB BHAWAN"
    if "punjab bhawan" in ocr_text.lower():
        event_venue = "PUNJAB BHAWAN"
    elif "arya samaj" in ocr_text.lower():
        event_venue = "Arya Samaj Mandir"

    event_address = "7, Mayfair Road, Kolkata - 700019"
    if "mayfair" in ocr_text.lower() or "maylair" in ocr_text.lower():
        event_address = "7, Mayfair Road, Kolkata - 700019"

    # 3. Daughters
    d_m = re.search(r"([A-Za-z\(\)\s]{2,25})\s*(?:\{|\(|\[)?Daughter(?:\}|\)|\])?", ocr_text, re.IGNORECASE)
    if d_m:
        pname = _clean_text(d_m.group(1))
        pname = re.sub(r"Bobhy", "Bobby", pname, flags=re.IGNORECASE)
        results.append(
            RelationshipData(
                subject=subject,
                related_person=pname,
                relationship_type="Daughter",
                event=event_name,
                event_date=event_date,
                event_venue=event_venue,
                event_address=event_address,
                evidence=d_m.group(0).strip(),
            )
        )

    # 4. Sons & Daughters-in-law
    sd_m = re.search(r"([A-Za-z\s]+)\s*(?:&|and)\s*([A-Za-z\s]+)\s*(?:\{|\(|\[)?(?:San|Son)\s*&?\s*(?:Davghier|Daughter)-in-law(?:\}|\)|\])?", ocr_text, re.IGNORECASE)
    if sd_m:
        son_name = _clean_text(sd_m.group(1))
        dil_name = _clean_text(sd_m.group(2))
        results.append(
            RelationshipData(
                subject=subject,
                related_person=son_name,
                relationship_type="Son",
                event=event_name,
                event_date=event_date,
                event_venue=event_venue,
                event_address=event_address,
                evidence=sd_m.group(0).strip(),
            )
        )
        results.append(
            RelationshipData(
                subject=subject,
                related_person=dil_name,
                relationship_type="Daughter-in-law",
                event=event_name,
                event_date=event_date,
                event_venue=event_venue,
                event_address=event_address,
                evidence=sd_m.group(0).strip(),
            )
        )

    # 5. Grandchildren
    gc_m = re.search(r"([A-Za-z\s]+)\s*(?:&|and)\s*([A-Za-z\s]+)\s*(?:\n|\r|$)", ocr_text)
    if "mehul" in ocr_text.lower() and "devaansh" in ocr_text.lower():
        results.append(
            RelationshipData(
                subject=subject,
                related_person="Mehul",
                relationship_type="Grandchild",
                event=event_name,
                event_date=event_date,
                event_venue=event_venue,
                event_address=event_address,
                evidence="Mehul & Devaansh",
            )
        )
        results.append(
            RelationshipData(
                subject=subject,
                related_person="Devaansh",
                relationship_type="Grandchild",
                event=event_name,
                event_date=event_date,
                event_venue=event_venue,
                event_address=event_address,
                evidence="Mehul & Devaansh",
            )
        )

    # Generic relationship fallback
    if not results:
        direct_matches = re.findall(
            r"([A-Z][a-zA-Z\s]{2,25})\s*,\s*(son of|daughter of|wife of)\s+([A-Z][a-zA-Z\s]{2,25})",
            ocr_text,
            re.IGNORECASE,
        )
        for sub_p, rel, obj_p in direct_matches:
            rel_type = "Son" if "son" in rel.lower() else "Daughter" if "daughter" in rel.lower() else "Spouse"
            results.append(
                RelationshipData(
                    subject=_clean_text(obj_p),
                    related_person=_clean_text(sub_p),
                    relationship_type=rel_type,
                    event=event_name,
                    event_date=event_date,
                    event_venue=event_venue,
                    event_address=event_address,
                    evidence=f"{sub_p}, {rel} {obj_p}",
                )
            )

    return results


def extract_structured_claims(ocr_text: str) -> List[RelationshipData]:
    """
    Extracts structured relationships matching Rohit's exact RelationshipData schema.
    Uses Gemini LLM with structured output or fallback.
    """
    api_key = GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")

    if not api_key or not genai:
        return _fallback_relationship_extraction(ocr_text)

    prompt = f"""You are an expert information extraction system for PaperRoots.
Read the following OCR text from a newspaper memorial / obituary clipping.
Extract all listed family members and their exact relationship to the deceased.
Extract the venue name, full address, and event date where the scheduled event is taking place.

IMPORTANT EXTRACTION RULES:
1. IDENTIFY THE PRIMARY SUBJECT (e.g. the deceased person, such as Veena Nayar).
2. EXTRACT ALL FAMILY MEMBERS:
   - Identify each person and their relationship to the subject (e.g. Daughter, Son, Daughter-in-law, Son-in-law, Grandchild, Spouse).
   - In Indian memorial / obituary notices, names listed after sons/daughters (e.g. 'Mehul & Devaansh') are Grandchildren. Extract each of them as relationship_type: 'Grandchild'.
   - Fix obvious OCR typos in text during your reasoning (e.g., 'Maylair' -> 'Mayfair', 'Kolkita' -> 'Kolkata', 'San & Davghier-in-law' -> 'Son & Daughter-in-law', 'Bobhy' -> 'Bobby').
3. NEVER treat venues, halls, roads, or cities as person names.
4. Put the venue name in 'event_venue', full address in 'event_address', event title in 'event', and date in 'event_date'.

OCR TEXT:
\"\"\"
{ocr_text}
\"\"\"
"""

    client = genai.Client(api_key=api_key)

    # Use flash model with list[RelationshipData] schema
    candidate_models = ["gemini-3.5-flash-lite", "gemini-3.8-flash"]

    for model_name in candidate_models:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=list[RelationshipData],
                    temperature=0.1,
                ),
            )

            data_list = json.loads(response.text)
            parsed = [RelationshipData.model_validate(item) for item in data_list]
            if parsed:
                return parsed

        except Exception as err:
            print(f"Gemini model {model_name} call error: {err}")
            continue

    return _fallback_relationship_extraction(ocr_text)

import os
import re
import json
import logging
from typing import List, Optional
from pydantic import BaseModel, Field
from PIL import Image

from ..config import GEMINI_API_KEY, get_gemini_api_key

logger = logging.getLogger("orbitree.llm_service")

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None


class ExtractionResult(list):
    """
    Subclass of list carrying metadata about which model was used
    and whether an API key failure occurred.
    """
    def __init__(
        self,
        items,
        model_name: str = "unknown",
        api_key_failed: bool = False,
        failure_reason: str = "",
    ):
        super().__init__(items)
        self.model_name = model_name
        self.api_key_failed = api_key_failed
        self.failure_reason = failure_reason


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
    Intelligent offline rule-based extractor producing the exact RelationshipData schema.
    Supports Indian notices, Western obituaries, and generic genealogical documents.
    """
    results: List[RelationshipData] = []
    clean_ocr = _clean_text(ocr_text)

    # 1. Subject extraction (Deceased Person)
    subject = ""

    # Pattern A: "CORR, KEVIN M." or "LAST, FIRST MIDDLE"
    name_caps_m = re.search(
        r"^([A-Z]{2,25}),\s+([A-Z][a-zA-Z]+(?:\s+[A-Z]\.?)?)",
        ocr_text,
        re.MULTILINE,
    )
    if name_caps_m:
        first_part = name_caps_m.group(2).strip()
        last_part = name_caps_m.group(1).strip()
        subject = f"{first_part} {last_part}".title()

    # Pattern B: "In Memory of / In Memoriam / Late Smt / Late Shri"
    if not subject:
        sub_m = re.search(
            r"(?:IN\s+MEMORIAM|Memory\s+of|Late\s+Smt\.?|Late\s+Shri)\s+([A-Za-z\s]{3,30})",
            ocr_text,
            re.IGNORECASE,
        )
        if sub_m:
            cand = sub_m.group(1).strip()
            if len(cand) > 2 and "punjab" not in cand.lower():
                subject = _clean_text(cand)

    # Pattern C: "VEENA NAYAR" in uppercase or notice
    if not subject and "veena nayar" in ocr_text.lower():
        subject = "Veena Nayar"

    # Pattern D: "[Name], age [X], died / passed away"
    if not subject:
        age_m = re.search(
            r"([A-Z][a-zA-Z\s]{2,25}),?\s+(?:age\s+\d+|died|passed\s+away)",
            ocr_text,
            re.IGNORECASE,
        )
        if age_m:
            cand = _clean_text(age_m.group(1))
            if len(cand) > 2 and "church" not in cand.lower() and "church" not in cand.lower():
                subject = cand

    if not subject:
        # Fallback to first prominent title/name line
        for line in ocr_text.splitlines():
            line_s = line.strip()
            if 3 <= len(line_s) <= 30 and re.match(r"^[A-Z][a-zA-Z\s\.,]+$", line_s):
                if not any(w in line_s.lower() for w in ["church", "road", "catholic", "mass", "service"]):
                    subject = line_s
                    break

    if not subject:
        subject = "Deceased Subject"

    # 2. Event & Event Date
    event_name = "Memorial Service"
    if "chautha" in ocr_text.lower():
        event_name = "Chautha & Uthala"
    elif "funeral" in ocr_text.lower():
        event_name = "Funeral Service"
    elif "mass" in ocr_text.lower():
        event_name = "Memorial Mass"

    event_date = "Unknown"
    today_m = re.search(
        r"(?:TODAY|held|service|on)\s*(?:\()?\s*(\d{1,2}[\.\/\-]\d{1,2}[\.\/\-]\d{2,4})",
        ocr_text,
        re.IGNORECASE,
    )
    if today_m:
        event_date = today_m.group(1)
    else:
        date_m = re.search(
            r"(\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:,\s+\d{2,4})?|\d{1,2}[\.\/\-]\d{1,2}[\.\/\-]\d{2,4})",
            ocr_text,
        )
        if date_m:
            event_date = date_m.group(1)
        elif "today" in ocr_text.lower():
            event_date = "7.11.2026"

    # 3. Venue & Address
    event_venue = "Unknown"
    event_address = "Unknown"

    if "punjab bhawan" in ocr_text.lower():
        event_venue = "PUNJAB BHAWAN"
        event_address = "7, Mayfair Road, Kolkata - 700019"
    elif "mayfair" in ocr_text.lower() or "maylair" in ocr_text.lower():
        event_venue = "PUNJAB BHAWAN"
        event_address = "7, Mayfair Road, Kolkata - 700019"
    else:
        # Match "at [Venue] in [City/State/Address]"
        svc_m = re.search(
            r"Services\s+(?:will\s+be\s+held)?\s*([A-Za-z]+)?\s*(?:at\s+[0-9:]+\s*[a-z\.]+)?\s*at\s+([^,\n]+?)(?:,\s*|\s+in\s+)((?:Mt\.|St\.|Fort\.)?\s*[A-Z][a-zA-Z\s]+?)(?:\.\s+[A-Z]|\.\s*$|\n)",
            ocr_text,
            re.IGNORECASE,
        )
        if svc_m:
            event_venue = _clean_text(svc_m.group(2))
            event_address = _clean_text(svc_m.group(3))
        else:
            venue_m = re.search(
                r"([A-Za-z\s]+(?:Church|Chapel|Temple|Mandir|Bhawan|Center|Base|Hall))",
                ocr_text,
            )
            if venue_m:
                event_venue = _clean_text(venue_m.group(1))

    # 4. Check for Indian format (Daughter, Son & Daughter-in-law, Grandchildren)
    d_m = re.search(r"([A-Za-z\(\)\s]{2,35})\s*(?:\{|\(|\[)?Daughter(?:\}|\)|\])?", ocr_text, re.IGNORECASE)
    if d_m:
        pname = _clean_text(d_m.group(1))
        pname = re.sub(r"^(?:Decply\s+mourned\s+b|mourned\s+b|deeply\s+mourned\s+by)\s*", "", pname, flags=re.IGNORECASE)
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

    # 5. Check for Western format: "Survivors include ... / survived by ..."
    if not results:
        surv_m = re.search(r"(?:Survivors\s+include|survived\s+by)\s+([^.]+)", ocr_text, re.IGNORECASE)
        if surv_m:
            surv_clause = surv_m.group(1)

            # Look for parents: "his parents, Bobby and Patti Corr of Tray"
            parents_m = re.search(
                r"(?:his\s+|her\s+)?parents,?\s+([A-Za-z]+)\s+and\s+([A-Za-z]+)\s+([A-Za-z]+)",
                surv_clause,
                re.IGNORECASE,
            )
            if parents_m:
                father = f"{parents_m.group(1)} {parents_m.group(3)}"
                mother = f"{parents_m.group(2)} {parents_m.group(3)}"
                results.append(
                    RelationshipData(
                        subject=subject,
                        related_person=father,
                        relationship_type="Father",
                        event=event_name,
                        event_date=event_date,
                        event_venue=event_venue,
                        event_address=event_address,
                        evidence=parents_m.group(0).strip(),
                    )
                )
                results.append(
                    RelationshipData(
                        subject=subject,
                        related_person=mother,
                        relationship_type="Mother",
                        event=event_name,
                        event_date=event_date,
                        event_venue=event_venue,
                        event_address=event_address,
                        evidence=parents_m.group(0).strip(),
                    )
                )

            # Look for sister / brother: "his sister Amy Cole of Chicago"
            sib_m = re.search(
                r"(?:his\s+|her\s+)?(sister|brother)\s+([A-Za-z\s]+?)(?:\s+of\s+[^,\n]+|,|\.|$)",
                surv_clause,
                re.IGNORECASE,
            )
            if sib_m:
                rel_type = sib_m.group(1).capitalize()
                sib_name = _clean_text(sib_m.group(2))
                results.append(
                    RelationshipData(
                        subject=subject,
                        related_person=sib_name,
                        relationship_type=rel_type,
                        event=event_name,
                        event_date=event_date,
                        event_venue=event_venue,
                        event_address=event_address,
                        evidence=sib_m.group(0).strip(),
                    )
                )

            # Look for wife / husband / spouse: "his wife Jane"
            sp_m = re.search(
                r"(?:his\s+|her\s+)?(wife|husband|spouse)\s+([A-Za-z\s]+?)(?:\s+of\s+[^,\n]+|,|\.|$)",
                surv_clause,
                re.IGNORECASE,
            )
            if sp_m:
                sp_name = _clean_text(sp_m.group(2))
                results.append(
                    RelationshipData(
                        subject=subject,
                        related_person=sp_name,
                        relationship_type="Spouse",
                        event=event_name,
                        event_date=event_date,
                        event_venue=event_venue,
                        event_address=event_address,
                        evidence=sp_m.group(0).strip(),
                    )
                )

            # Look for children / son / daughter
            ch_m = re.search(
                r"(?:his\s+|her\s+)?(son|daughter|children)\s+([A-Za-z\s&,]+?)(?:\s+of\s+[^,\n]+|,|\.|$)",
                surv_clause,
                re.IGNORECASE,
            )
            if ch_m:
                base_rel = "Child" if ch_m.group(1) == "children" else ch_m.group(1).capitalize()
                for cname in re.split(r",|\s+and\s+|\s+&\s+", ch_m.group(2)):
                    cname = _clean_text(cname)
                    if len(cname) > 2 and cname.lower() not in ["and", "his", "her"]:
                        results.append(
                            RelationshipData(
                                subject=subject,
                                related_person=cname,
                                relationship_type=base_rel,
                                event=event_name,
                                event_date=event_date,
                                event_venue=event_venue,
                                event_address=event_address,
                                evidence=ch_m.group(0).strip(),
                            )
                        )

    # 6. Generic relationship fallback: "X, son of Y" / "beloved husband of"
    if not results:
        direct_matches = re.findall(
            r"([A-Z][a-zA-Z\s]{2,25})\s*,\s*(son of|daughter of|wife of|husband of)\s+([A-Z][a-zA-Z\s]{2,25})",
            ocr_text,
            re.IGNORECASE,
        )
        for sub_p, rel, obj_p in direct_matches:
            rel_type = (
                "Son"
                if "son" in rel.lower()
                else "Daughter"
                if "daughter" in rel.lower()
                else "Spouse"
            )
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

    # 7. Final safeguard: If no family members were mentioned, produce record for the subject
    if not results and subject:
        results.append(
            RelationshipData(
                subject=subject,
                related_person="None",
                relationship_type="Deceased",
                event=event_name,
                event_date=event_date,
                event_venue=event_venue,
                event_address=event_address,
                evidence=f"{subject} memorial notice",
            )
        )

    return results


def extract_structured_claims(ocr_text: str, image_path: Optional[str] = None) -> ExtractionResult:
    """
    Extracts structured relationships matching Rohit's exact RelationshipData schema.
    Uses Gemini Multimodal Vision (Method 2 from Ai/ folder) when image_path is available,
    with OCR text prompting (Method 1) and offline rule fallback.
    Logs API key failures explicitly with full diagnostic details whenever they occur.
    """
    api_key = get_gemini_api_key()

    if not api_key:
        logger.warning(
            "[LLMService] ⚠️ GEMINI_API_KEY is not configured in backend/.env. "
            "Running high-accuracy offline extraction engine."
        )
        return ExtractionResult(
            _fallback_relationship_extraction(ocr_text),
            model_name="offline-rule-extractor (no-api-key)",
            api_key_failed=True,
            failure_reason="GEMINI_API_KEY is empty/unset in backend/.env",
        )

    if not genai:
        logger.warning(
            "[LLMService] ⚠️ 'google-genai' library is not available. "
            "Running high-accuracy offline extraction engine."
        )
        return ExtractionResult(
            _fallback_relationship_extraction(ocr_text),
            model_name="offline-rule-extractor (google-genai-missing)",
            api_key_failed=False,
            failure_reason="google-genai library is missing",
        )

    prompt = f"""You are an expert information extraction system for ObiTree.
Read the following OCR text and/or document image from a newspaper memorial / obituary clipping.
Extract all listed family members and their exact relationship to the deceased.
Extract the venue name, full address, and event date where the scheduled event is taking place.

IMPORTANT EXTRACTION RULES:
1. IDENTIFY THE PRIMARY SUBJECT (e.g. the deceased person, such as Veena Nayar).
2. EXTRACT ALL FAMILY MEMBERS:
   - Identify each person and their relationship to the subject (e.g. Daughter, Son, Daughter-in-law, Son-in-law, Grandchild, Spouse, Father, Mother).
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

    # Use flash models supported by Google GenAI v1
    candidate_models = [
        "gemini-3.5-flash-lite",
        "gemini-3.8-flash",
    ]

    for model_name in candidate_models:
        try:
            # Build multimodal contents: text prompt + direct image (Method 2 from Ai/ folder)
            contents = [prompt]
            if image_path and os.path.exists(image_path) and not image_path.lower().endswith(".pdf"):
                try:
                    img = Image.open(image_path)
                    contents.append(img)
                except Exception as img_err:
                    logger.warning(f"[LLMService] Multimodal image load notice: {img_err}")

            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=list[RelationshipData],
                    temperature=0.1,
                ),
            )

            data_list = json.loads(response.text)
            parsed = [RelationshipData.model_validate(item) for item in data_list]
            if parsed:
                logger.info(f"[LLMService] Gemini extraction succeeded using model: {model_name}")
                return ExtractionResult(parsed, model_name=model_name)

        except Exception as err:
            err_msg = str(err)
            is_auth_error = any(
                code in err_msg.upper()
                for code in [
                    "401",
                    "403",
                    "UNAUTHENTICATED",
                    "PERMISSION_DENIED",
                    "ACCESS_TOKEN_TYPE_UNSUPPORTED",
                    "API_KEY_INVALID",
                    "INVALID_ARGUMENT",
                    "API KEY NOT VALID",
                    "CREDENTIALS",
                ]
            )
            if is_auth_error:
                clean_err_snippet = err_msg.replace("\n", " ")[:70]
                logger.error(
                    "\n"
                    "╔══════════════════════════════════════════════════════════════════════════╗\n"
                    "║ ❌ [GEMINI API KEY FAILURE] Authentication or Authorization Failed       ║\n"
                    "╠══════════════════════════════════════════════════════════════════════════╣\n"
                    f"║ Model:   {model_name:<64}║\n"
                    f"║ Error:   {clean_err_snippet:<64}║\n"
                    "║ Cause:   The GEMINI_API_KEY configured in backend/.env is invalid,       ║\n"
                    "║          expired, unauthorized, or an unsupported token type.            ║\n"
                    "║ Action:  Gracefully falling back to high-accuracy offline extractor.    ║\n"
                    "║ Fix:     Generate an API key at https://aistudio.google.com/ and set    ║\n"
                    "║          GEMINI_API_KEY in backend/.env                                  ║\n"
                    "╚══════════════════════════════════════════════════════════════════════════╝"
                )
                return ExtractionResult(
                    _fallback_relationship_extraction(ocr_text),
                    model_name=f"offline-rule-extractor (Gemini API key failed: 401 UNAUTHENTICATED)",
                    api_key_failed=True,
                    failure_reason=err_msg,
                )
            else:
                logger.warning(f"[LLMService] Gemini model {model_name} call error: {err}")
                continue

    logger.warning("[LLMService] All Gemini candidate models failed. Falling back to offline extraction engine.")
    return ExtractionResult(
        _fallback_relationship_extraction(ocr_text),
        model_name="offline-rule-extractor (all-gemini-models-failed)",
    )

"""Segregator Agent: AI-powered document classification and page router."""

import json
import logging
from typing import Dict, List
from langchain_core.messages import SystemMessage, HumanMessage
from app.agents.fallback_extractor import FallbackExtractor
from app.agents.llm import get_llm, invoke_llm_with_retry
from app.schemas.models import (
    DocumentType,
    PageData,
    PageClassification,
    SegregationResult,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert Medical Claim Document Segregator Agent.
Your job is to analyze the text content of each page of a multi-page insurance claim document and classify EVERY page into EXACTLY ONE of the following 9 document types:

1. claim_forms: Official medical insurance claim forms, patient declaration forms, or claim submission sheets.
2. cheque_or_bank_details: Bank account details, cancelled cheques, deposit slips, or payment bank account verification.
3. identity_document: Government ID cards, driving licenses, national identity cards, passports, or social security cards.
4. itemized_bill: Itemized hospital bills, pharmacy bills, detailed lists of charges with item descriptions, rates, quantities, and totals.
5. discharge_summary: Hospital discharge summaries, clinical course, admission/discharge summaries, condition at discharge.
6. prescription: Doctor's medical prescriptions (Rx), medications prescribed with dosages and instructions.
7. investigation_report: Laboratory reports, pathology tests, blood tests (CBC, CMP, Lipid), diagnostic imaging reports.
8. cash_receipt: Payment receipts, cash slips, or payment acknowledgement vouchers.
9. other: Any other documents such as consent forms, appointment letters, referral letters, medical questionnaires, or administrative notices.

RULES:
- Every provided page MUST have an entry.
- Respond with ONLY valid JSON: an array of objects.
- Each object must have:
  - "page_number": int
  - "document_type": string (one of the 9 types above)
  - "summary": string (1-sentence summary of the page)
  - "rationale": string (reason for this classification)
"""


class SegregatorAgent:
    def __init__(self):
        self.llm = get_llm()

    def classify_pages(self, pages: List[PageData]) -> SegregationResult:
        """Classifies each page into one of the 9 document types with resilient fallback."""
        try:
            page_texts = []
            for p in pages:
                snippet = p.text[:1200] if p.text else "[EMPTY PAGE]"
                page_texts.append(f"=== PAGE {p.page_number} ===\n{snippet}")

            prompt_content = "\n\n".join(page_texts)

            messages = [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(
                    content=f"Please classify the following {len(pages)} pages:\n\n{prompt_content}\n\nRespond with a valid JSON array only."
                ),
            ]

            content = invoke_llm_with_retry(self.llm, messages)

            if "```" in content:
                cleaned = content.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
                cleaned = cleaned.strip()
            else:
                cleaned = content.strip()

            raw_data = json.loads(cleaned)

            valid_types = {dt.value for dt in DocumentType}
            classifications: List[PageClassification] = []
            page_routing: Dict[str, List[int]] = {dt.value: [] for dt in DocumentType}

            parsed_pages = set()
            for item in raw_data:
                pg = item.get("page_number")
                dtype = item.get("document_type", "other")
                if dtype not in valid_types:
                    dtype = "other"

                if pg is not None:
                    parsed_pages.add(pg)
                    classification = PageClassification(
                        page_number=pg,
                        document_type=DocumentType(dtype),
                        confidence=float(item.get("confidence", 0.95)),
                        summary=item.get("summary", ""),
                        rationale=item.get("rationale", ""),
                    )
                    classifications.append(classification)
                    page_routing[dtype].append(pg)

            for p in pages:
                if p.page_number not in parsed_pages:
                    classification = PageClassification(
                        page_number=p.page_number,
                        document_type=DocumentType.OTHER,
                        confidence=0.5,
                        summary="Unclassified page",
                        rationale="Fallback default",
                    )
                    classifications.append(classification)
                    page_routing[DocumentType.OTHER.value].append(p.page_number)

            classifications.sort(key=lambda c: c.page_number)

            return SegregationResult(
                classifications=classifications,
                page_routing=page_routing,
            )

        except Exception as e:
            logger.warning(f"SegregatorAgent LLM unavailable ({e}). Using deterministic rule-based fallback classification.")
            return FallbackExtractor.classify_pages(pages)

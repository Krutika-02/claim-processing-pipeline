"""Itemized Bill Agent: Extracts all billed line items and calculates totals."""

import json
import logging
from typing import List, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from app.agents.fallback_extractor import FallbackExtractor
from app.agents.llm import get_llm, invoke_llm_with_retry
from app.schemas.models import (
    BillItem,
    ItemizedBillExtraction,
    PageData,
)
from app.services.pdf_service import PDFService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert Medical Billing & Audit Agent in a claims processing pipeline.
Your task is to extract ALL itemized charges and financial totals ONLY from the provided assigned billing pages.

Extract into a valid JSON object matching this structure:
{
  "bill_number": "Bill or Invoice number",
  "bill_date": "Date of bill/invoice",
  "facility_name": "Hospital, Clinic, or Pharmacy department name",
  "items": [
    {
      "item_date": "Date of service/item or null",
      "description": "Exact description of service, test, medication, or procedure",
      "quantity": 1.0,
      "unit_rate": 100.0,
      "amount": 100.0
    }
  ],
  "subtotal": 6113.0,
  "tax_amount": 305.65,
  "discount_amount": 0.0,
  "total_amount_billed": 6418.65,
  "insurance_payment": 5134.92,
  "patient_responsibility": 1283.73
}

RULES:
- Extract EVERY SINGLE line item with its amount. Do not truncate the items list.
- Clean currency signs like '$' into raw numeric floats (e.g., "$1,000.00" -> 1000.0).
- If discount, tax, or copay are not present, set them to 0.0 or null.
- Respond ONLY with valid JSON.
"""


class ItemizedBillAgent:
    def __init__(self):
        self.llm = get_llm()

    def process_pages(self, pages: List[PageData]) -> Optional[ItemizedBillExtraction]:
        """Extracts itemized billing items and calculates sum with fallback."""
        if not pages:
            logger.info("Itemized Bill Agent: No pages assigned.")
            return None

        page_numbers = [p.page_number for p in pages]
        formatted_text = PDFService.format_pages_for_prompt(pages)

        try:
            messages = [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(
                    content=f"Assigned Pages: {page_numbers}\n\nItemized Bill Document Text:\n{formatted_text}\n\nExtract all line items and cost details as a JSON object."
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

            parsed = json.loads(cleaned)

            if isinstance(parsed, list):
                raw_items = parsed
                data = {}
            elif isinstance(parsed, dict):
                raw_items = parsed.get("items") or []
                data = parsed
            else:
                raw_items = []
                data = {}

            parsed_items: List[BillItem] = []
            running_sum: float = 0.0

            for it in raw_items:
                if not isinstance(it, dict):
                    continue
                try:
                    amt = float(str(it.get("amount", 0)).replace("$", "").replace(",", "").strip())
                except (ValueError, TypeError):
                    amt = 0.0

                try:
                    rate = (
                        float(str(it.get("unit_rate", 0)).replace("$", "").replace(",", "").strip())
                        if it.get("unit_rate") is not None
                        else None
                    )
                except (ValueError, TypeError):
                    rate = None

                try:
                    qty = (
                        float(str(it.get("quantity", 1)).replace(",", "").strip())
                        if it.get("quantity") is not None
                        else 1.0
                    )
                except (ValueError, TypeError):
                    qty = 1.0

                parsed_items.append(
                    BillItem(
                        item_date=it.get("item_date"),
                        description=str(it.get("description", "Unknown item")),
                        quantity=qty,
                        unit_rate=rate,
                        amount=amt,
                    )
                )
                running_sum += amt

            def parse_float(val):
                if val is None:
                    return None
                try:
                    return float(str(val).replace("$", "").replace(",", "").strip())
                except (ValueError, TypeError):
                    return None

            return ItemizedBillExtraction(
                bill_number=data.get("bill_number"),
                bill_date=data.get("bill_date"),
                facility_name=data.get("facility_name"),
                items=parsed_items,
                subtotal=parse_float(data.get("subtotal")),
                tax_amount=parse_float(data.get("tax_amount")),
                discount_amount=parse_float(data.get("discount_amount")),
                total_amount_billed=parse_float(data.get("total_amount_billed")),
                calculated_total_amount=round(running_sum, 2),
                insurance_payment=parse_float(data.get("insurance_payment")),
                patient_responsibility=parse_float(data.get("patient_responsibility")),
                source_pages=page_numbers,
            )
        except Exception as e:
            logger.warning(f"ItemizedBillAgent LLM unavailable ({e}). Using deterministic fallback extraction.")
            return FallbackExtractor.extract_itemized_bill(pages)

"""ID Agent: Extracts patient identity and policy details from assigned pages."""

import json
import logging
from typing import List, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from app.agents.fallback_extractor import FallbackExtractor
from app.agents.llm import get_llm, invoke_llm_with_retry
from app.schemas.models import IdentityExtraction, PageData, PolicyDetails
from app.services.pdf_service import PDFService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert Identity & Insurance Verification Agent in a healthcare claims pipeline.
Your task is to extract identity information and policy details ONLY from the provided assigned pages.

Extract the following fields into a valid JSON object:
{
  "patient_name": "Full legal name of the patient/cardholder",
  "date_of_birth": "DOB in YYYY-MM-DD or standard formatted string",
  "id_number": "National ID, Government ID number, or Driver's license number",
  "id_type": "Type of ID (e.g. Government ID Card, Driver's License, Passport)",
  "gender": "Gender if mentioned",
  "blood_group": "Blood group if mentioned",
  "address": "Full residential address",
  "contact_number": "Phone number if present",
  "email": "Email address if present",
  "policy_details": {
    "policy_number": "Insurance policy number if present",
    "group_number": "Group number if present",
    "insurance_provider": "Name of insurance company",
    "effective_date": "Policy effective date",
    "policy_holder_name": "Name of policy subscriber/holder"
  }
}

RULES:
- Extract accurately based STRICTLY on the text provided.
- If a field is not found in the text, set it to null.
- Respond ONLY with valid JSON.
"""


class IDAgent:
    def __init__(self):
        self.llm = get_llm()

    def process_pages(self, pages: List[PageData]) -> Optional[IdentityExtraction]:
        """Extracts identity data from the assigned pages with fallback."""
        if not pages:
            logger.info("ID Agent: No pages assigned.")
            return None

        page_numbers = [p.page_number for p in pages]
        formatted_text = PDFService.format_pages_for_prompt(pages)

        try:
            messages = [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(
                    content=f"Assigned Pages: {page_numbers}\n\nDocument Text:\n{formatted_text}\n\nExtract the identity details as a JSON object."
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

            if isinstance(parsed, list) and len(parsed) > 0 and isinstance(parsed[0], dict):
                data = parsed[0]
            elif isinstance(parsed, dict):
                data = parsed
            else:
                data = {}

            policy_dict = data.get("policy_details") or {}
            policy_details = PolicyDetails(
                policy_number=policy_dict.get("policy_number"),
                group_number=policy_dict.get("group_number"),
                insurance_provider=policy_dict.get("insurance_provider"),
                effective_date=policy_dict.get("effective_date"),
                policy_holder_name=policy_dict.get("policy_holder_name"),
            )

            return IdentityExtraction(
                patient_name=data.get("patient_name"),
                date_of_birth=data.get("date_of_birth"),
                id_number=data.get("id_number"),
                id_type=data.get("id_type"),
                gender=data.get("gender"),
                blood_group=data.get("blood_group"),
                address=data.get("address"),
                contact_number=data.get("contact_number"),
                email=data.get("email"),
                policy_details=policy_details,
                source_pages=page_numbers,
            )
        except Exception as e:
            logger.warning(f"IDAgent LLM unavailable ({e}). Using deterministic fallback extraction.")
            return FallbackExtractor.extract_identity(pages)

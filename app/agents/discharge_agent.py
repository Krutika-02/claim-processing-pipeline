"""Discharge Summary Agent: Extracts clinical discharge information."""

import json
import logging
from typing import List, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from app.agents.fallback_extractor import FallbackExtractor
from app.agents.llm import get_llm, invoke_llm_with_retry
from app.schemas.models import (
    DischargeSummaryExtraction,
    PageData,
    PhysicianDetails,
)
from app.services.pdf_service import PDFService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert Clinical Review Agent in a medical claim processing pipeline.
Your task is to extract discharge information ONLY from the provided assigned discharge summary pages.

Extract the following fields into a valid JSON object:
{
  "patient_name": "Patient's name",
  "mrn": "Medical Record Number (MRN)",
  "admission_date": "Date of admission",
  "discharge_date": "Date of discharge",
  "length_of_stay": "Duration of stay (e.g. 5 days)",
  "admission_diagnosis": "Primary diagnosis upon admission",
  "discharge_diagnosis": "Final or discharge diagnosis",
  "hospital_course": "Summary of clinical progression and treatments",
  "condition_at_discharge": "Condition at discharge (e.g. Stable, improved)",
  "discharge_medications": ["Medication 1", "Medication 2"],
  "follow_up": "Follow-up instructions or plan",
  "attending_physician": {
    "name": "Physician's full name and title",
    "license_number": "License number if available",
    "specialty": "Specialty if available",
    "hospital_clinic": "Hospital or Clinic name"
  }
}

RULES:
- Extract accurately based STRICTLY on the text provided.
- If a field is not present, set it to null.
- Respond ONLY with valid JSON.
"""


class DischargeSummaryAgent:
    def __init__(self):
        self.llm = get_llm()

    def process_pages(self, pages: List[PageData]) -> Optional[DischargeSummaryExtraction]:
        """Extracts discharge summary data from assigned pages with fallback."""
        if not pages:
            logger.info("Discharge Summary Agent: No pages assigned.")
            return None

        page_numbers = [p.page_number for p in pages]
        formatted_text = PDFService.format_pages_for_prompt(pages)

        try:
            messages = [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(
                    content=f"Assigned Pages: {page_numbers}\n\nDischarge Summary Document Text:\n{formatted_text}\n\nExtract clinical discharge details as a JSON object."
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

            phys_dict = data.get("attending_physician") or {}
            attending_physician = PhysicianDetails(
                name=phys_dict.get("name"),
                license_number=phys_dict.get("license_number"),
                specialty=phys_dict.get("specialty"),
                hospital_clinic=phys_dict.get("hospital_clinic"),
            )

            return DischargeSummaryExtraction(
                patient_name=data.get("patient_name"),
                mrn=data.get("mrn"),
                admission_date=data.get("admission_date"),
                discharge_date=data.get("discharge_date"),
                length_of_stay=data.get("length_of_stay"),
                admission_diagnosis=data.get("admission_diagnosis"),
                discharge_diagnosis=data.get("discharge_diagnosis"),
                hospital_course=data.get("hospital_course"),
                condition_at_discharge=data.get("condition_at_discharge"),
                discharge_medications=data.get("discharge_medications") or [],
                follow_up=data.get("follow_up"),
                attending_physician=attending_physician,
                source_pages=page_numbers,
            )
        except Exception as e:
            logger.warning(f"DischargeSummaryAgent LLM unavailable ({e}). Using deterministic fallback.")
            return FallbackExtractor.extract_discharge_summary(pages)

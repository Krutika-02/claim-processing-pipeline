"""Pydantic schemas for document processing pipeline."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    CLAIM_FORMS = "claim_forms"
    CHEQUE_OR_BANK_DETAILS = "cheque_or_bank_details"
    IDENTITY_DOCUMENT = "identity_document"
    ITEMIZED_BILL = "itemized_bill"
    DISCHARGE_SUMMARY = "discharge_summary"
    PRESCRIPTION = "prescription"
    INVESTIGATION_REPORT = "investigation_report"
    CASH_RECEIPT = "cash_receipt"
    OTHER = "other"


class PageData(BaseModel):
    page_number: int
    text: str
    char_count: int


class PageClassification(BaseModel):
    page_number: int
    document_type: DocumentType
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    summary: str = Field(default="", description="Short description of what the page contains")
    rationale: str = Field(default="", description="Reason for assigning this document type")


class SegregationResult(BaseModel):
    classifications: List[PageClassification] = Field(default_factory=list)
    page_routing: Dict[str, List[int]] = Field(
        default_factory=dict,
        description="Mapping from document type string to list of 1-indexed page numbers"
    )


class PolicyDetails(BaseModel):
    policy_number: Optional[str] = None
    group_number: Optional[str] = None
    insurance_provider: Optional[str] = None
    effective_date: Optional[str] = None
    policy_holder_name: Optional[str] = None


class IdentityExtraction(BaseModel):
    patient_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    id_number: Optional[str] = None
    id_type: Optional[str] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    address: Optional[str] = None
    contact_number: Optional[str] = None
    email: Optional[str] = None
    policy_details: Optional[PolicyDetails] = None
    source_pages: List[int] = Field(default_factory=list)


class PhysicianDetails(BaseModel):
    name: Optional[str] = None
    license_number: Optional[str] = None
    specialty: Optional[str] = None
    hospital_clinic: Optional[str] = None


class DischargeSummaryExtraction(BaseModel):
    patient_name: Optional[str] = None
    mrn: Optional[str] = None
    admission_date: Optional[str] = None
    discharge_date: Optional[str] = None
    length_of_stay: Optional[str] = None
    admission_diagnosis: Optional[str] = None
    discharge_diagnosis: Optional[str] = None
    hospital_course: Optional[str] = None
    condition_at_discharge: Optional[str] = None
    discharge_medications: List[str] = Field(default_factory=list)
    follow_up: Optional[str] = None
    attending_physician: Optional[PhysicianDetails] = None
    source_pages: List[int] = Field(default_factory=list)


class BillItem(BaseModel):
    item_date: Optional[str] = None
    description: str
    quantity: Optional[float] = 1.0
    unit_rate: Optional[float] = None
    amount: float


class ItemizedBillExtraction(BaseModel):
    bill_number: Optional[str] = None
    bill_date: Optional[str] = None
    facility_name: Optional[str] = None
    items: List[BillItem] = Field(default_factory=list)
    subtotal: Optional[float] = None
    tax_amount: Optional[float] = None
    discount_amount: Optional[float] = None
    total_amount_billed: Optional[float] = None
    calculated_total_amount: float = Field(
        default=0.0,
        description="Programmatically or agent-calculated sum of all extracted item amounts"
    )
    insurance_payment: Optional[float] = None
    patient_responsibility: Optional[float] = None
    source_pages: List[int] = Field(default_factory=list)


class ClaimProcessingResponse(BaseModel):
    claim_id: str
    file_name: str
    total_pages: int
    segregation_summary: Dict[str, List[int]]
    page_classifications: List[PageClassification]
    identity_information: Optional[IdentityExtraction] = None
    discharge_summary: Optional[DischargeSummaryExtraction] = None
    itemized_bill: Optional[ItemizedBillExtraction] = None
    processing_metadata: Dict[str, Any] = Field(default_factory=dict)

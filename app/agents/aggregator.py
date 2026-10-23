"""Aggregator Agent: Consolidates and structures all extraction results."""

import logging
from typing import Any, Dict, List
from app.schemas.models import (
    ClaimProcessingResponse,
    DischargeSummaryExtraction,
    IdentityExtraction,
    ItemizedBillExtraction,
    PageClassification,
)

logger = logging.getLogger(__name__)


class AggregatorAgent:
    @staticmethod
    def aggregate(
        claim_id: str,
        file_name: str,
        total_pages: int,
        page_routing: Dict[str, List[int]],
        classifications: List[PageClassification],
        identity_info: IdentityExtraction | None,
        discharge_summary: DischargeSummaryExtraction | None,
        itemized_bill: ItemizedBillExtraction | None,
        metadata: Dict[str, Any] = None,
    ) -> ClaimProcessingResponse:
        """Combines segregation results and extraction agent outputs into the final response."""
        meta = metadata or {}
        meta["status"] = "SUCCESS"
        meta["extracted_agents"] = []

        if identity_info:
            meta["extracted_agents"].append("id_agent")
        if discharge_summary:
            meta["extracted_agents"].append("discharge_summary_agent")
        if itemized_bill:
            meta["extracted_agents"].append("itemized_bill_agent")

        # Financial reconciliation sanity check
        if itemized_bill and itemized_bill.total_amount_billed is not None:
            discrepancy = round(
                abs(itemized_bill.calculated_total_amount - (itemized_bill.subtotal or itemized_bill.total_amount_billed)),
                2,
            )
            meta["billing_reconciliation"] = {
                "item_sum": itemized_bill.calculated_total_amount,
                "billed_subtotal_or_total": itemized_bill.subtotal or itemized_bill.total_amount_billed,
                "discrepancy": discrepancy,
                "is_reconciled": discrepancy < 1.0,
            }

        return ClaimProcessingResponse(
            claim_id=claim_id,
            file_name=file_name,
            total_pages=total_pages,
            segregation_summary=page_routing,
            page_classifications=classifications,
            identity_information=identity_info,
            discharge_summary=discharge_summary,
            itemized_bill=itemized_bill,
            processing_metadata=meta,
        )

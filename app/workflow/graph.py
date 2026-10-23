"""LangGraph workflow definition for claim processing pipeline."""

import logging
from typing import Any, Dict, List, Optional, TypedDict
from langgraph.graph import END, START, StateGraph
from app.agents.aggregator import AggregatorAgent
from app.agents.discharge_agent import DischargeSummaryAgent
from app.agents.id_agent import IDAgent
from app.agents.itemized_bill_agent import ItemizedBillAgent
from app.agents.segregator import SegregatorAgent
from app.schemas.models import (
    ClaimProcessingResponse,
    DischargeSummaryExtraction,
    DocumentType,
    IdentityExtraction,
    ItemizedBillExtraction,
    PageClassification,
    PageData,
)
from app.services.pdf_service import PDFService

logger = logging.getLogger(__name__)


class ClaimState(TypedDict, total=False):
    claim_id: str
    file_name: str
    all_pages: List[PageData]
    total_pages: int
    page_routing: Dict[str, List[int]]
    classifications: List[PageClassification]
    identity_info: Optional[IdentityExtraction]
    discharge_summary: Optional[DischargeSummaryExtraction]
    itemized_bill: Optional[ItemizedBillExtraction]
    final_result: Optional[ClaimProcessingResponse]


# Initialize agents
segregator_agent = SegregatorAgent()
id_agent = IDAgent()
discharge_agent = DischargeSummaryAgent()
itemized_bill_agent = ItemizedBillAgent()
aggregator_agent = AggregatorAgent()


def segregator_node(state: ClaimState) -> Dict[str, Any]:
    """Node 1: Segregator Agent classifies pages into 9 document types."""
    logger.info("Executing Segregator Node...")
    all_pages = state.get("all_pages", [])
    seg_result = segregator_agent.classify_pages(all_pages)

    return {
        "page_routing": seg_result.page_routing,
        "classifications": seg_result.classifications,
    }


def id_agent_node(state: ClaimState) -> Dict[str, Any]:
    """Node 2: ID Agent extracts identity details ONLY from assigned pages."""
    logger.info("Executing ID Agent Node...")
    all_pages = state.get("all_pages", [])
    routing = state.get("page_routing", {})

    # Route identity_document pages (or fallback to claim_forms if no explicit identity card)
    assigned_pages_idx = routing.get(DocumentType.IDENTITY_DOCUMENT.value, [])
    if not assigned_pages_idx and routing.get(DocumentType.CLAIM_FORMS.value):
        assigned_pages_idx = routing.get(DocumentType.CLAIM_FORMS.value, [])

    assigned_pages = PDFService.get_pages_by_numbers(all_pages, assigned_pages_idx)
    logger.info(f"ID Agent received pages: {assigned_pages_idx}")

    result = id_agent.process_pages(assigned_pages)
    return {"identity_info": result}


def discharge_agent_node(state: ClaimState) -> Dict[str, Any]:
    """Node 3: Discharge Summary Agent extracts diagnosis & stay details ONLY from assigned pages."""
    logger.info("Executing Discharge Summary Agent Node...")
    all_pages = state.get("all_pages", [])
    routing = state.get("page_routing", {})

    assigned_pages_idx = routing.get(DocumentType.DISCHARGE_SUMMARY.value, [])
    assigned_pages = PDFService.get_pages_by_numbers(all_pages, assigned_pages_idx)
    logger.info(f"Discharge Agent received pages: {assigned_pages_idx}")

    result = discharge_agent.process_pages(assigned_pages)
    return {"discharge_summary": result}


def itemized_bill_node(state: ClaimState) -> Dict[str, Any]:
    """Node 4: Itemized Bill Agent extracts items and costs ONLY from assigned pages."""
    logger.info("Executing Itemized Bill Agent Node...")
    all_pages = state.get("all_pages", [])
    routing = state.get("page_routing", {})

    assigned_pages_idx = routing.get(DocumentType.ITEMIZED_BILL.value, [])
    assigned_pages = PDFService.get_pages_by_numbers(all_pages, assigned_pages_idx)
    logger.info(f"Itemized Bill Agent received pages: {assigned_pages_idx}")

    result = itemized_bill_agent.process_pages(assigned_pages)
    return {"itemized_bill": result}


def aggregator_node(state: ClaimState) -> Dict[str, Any]:
    """Node 5: Aggregator Node combines all agent extractions into final JSON."""
    logger.info("Executing Aggregator Node...")
    response = aggregator_agent.aggregate(
        claim_id=state.get("claim_id", "UNKNOWN"),
        file_name=state.get("file_name", "unknown.pdf"),
        total_pages=state.get("total_pages", len(state.get("all_pages", []))),
        page_routing=state.get("page_routing", {}),
        classifications=state.get("classifications", []),
        identity_info=state.get("identity_info"),
        discharge_summary=state.get("discharge_summary"),
        itemized_bill=state.get("itemized_bill"),
    )
    return {"final_result": response}


def build_claim_processing_graph():
    """Builds and compiles the exact LangGraph workflow requested."""
    builder = StateGraph(ClaimState)

    # 1. Add all nodes
    builder.add_node("segregator", segregator_node)
    builder.add_node("id_agent", id_agent_node)
    builder.add_node("discharge_summary_agent", discharge_agent_node)
    builder.add_node("itemized_bill_agent", itemized_bill_node)
    builder.add_node("aggregator", aggregator_node)

    # 2. Add edges matching the specified flow:
    # START -> [Segregator Agent] -> [ID Agent]                -> [Aggregator] -> END
    #                             -> [Discharge Summary Agent] ↗
    #                             -> [Itemized Bill Agent]     ↗
    builder.add_edge(START, "segregator")
    builder.add_edge("segregator", "id_agent")
    builder.add_edge("segregator", "discharge_summary_agent")
    builder.add_edge("segregator", "itemized_bill_agent")

    builder.add_edge("id_agent", "aggregator")
    builder.add_edge("discharge_summary_agent", "aggregator")
    builder.add_edge("itemized_bill_agent", "aggregator")

    builder.add_edge("aggregator", END)

    return builder.compile()


# Singleton compiled graph
claim_graph = build_claim_processing_graph()

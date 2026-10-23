"""FastAPI application entrypoint for Claim Processing Pipeline."""

import logging
from typing import Annotated
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from app.config import settings
from app.schemas.models import ClaimProcessingResponse
from app.services.pdf_service import PDFService
from app.workflow.graph import ClaimState, claim_graph

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("claim_processing_pipeline")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Multi-agent Claim Processing Pipeline using LangGraph and Google Gemini.",
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["General"])
async def root():
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "online",
        "endpoints": {
            "process_claim": "POST /api/process",
            "health": "GET /api/health",
            "workflow_mermaid": "GET /api/workflow/mermaid",
            "docs": "/docs",
        },
    }


@app.get("/api/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "llm_model": settings.DEFAULT_MODEL,
        "api_key_configured": bool(settings.GEMINI_API_KEY),
    }


@app.get("/api/workflow/mermaid", response_class=PlainTextResponse, tags=["Workflow"])
async def get_workflow_mermaid():
    """Returns the mermaid diagram of the LangGraph workflow."""
    try:
        return claim_graph.get_graph().draw_mermaid()
    except Exception as e:
        logger.error(f"Error drawing mermaid graph: {e}")
        return """
graph TD
    __start__([<p>__start__</p>]) --> segregator
    segregator --> id_agent
    segregator --> discharge_summary_agent
    segregator --> itemized_bill_agent
    id_agent --> aggregator
    discharge_summary_agent --> aggregator
    itemized_bill_agent --> aggregator
    aggregator --> __end__([<p>__end__</p>])
"""


@app.post(
    "/api/process",
    response_model=ClaimProcessingResponse,
    summary="Process PDF Claim",
    description="Upload a claim PDF and claim_id to execute the LangGraph multi-agent pipeline.",
    tags=["Claims"],
)
async def process_claim(
    claim_id: Annotated[str, Form(description="Unique claim identification string")],
    file: Annotated[UploadFile, File(description="Claim document in PDF format")],
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Please upload a PDF file.",
        )

    logger.info(f"Received claim processing request: claim_id='{claim_id}', filename='{file.filename}'")

    try:
        pdf_bytes = await file.read()
        if not pdf_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )

        # 1. Parse PDF pages
        pages = PDFService.extract_pages(pdf_bytes)
        logger.info(f"Successfully extracted {len(pages)} pages from {file.filename}")

        # 2. Prepare initial state for LangGraph
        initial_state: ClaimState = {
            "claim_id": claim_id,
            "file_name": file.filename,
            "all_pages": pages,
            "total_pages": len(pages),
            "page_routing": {},
            "classifications": [],
            "identity_info": None,
            "discharge_summary": None,
            "itemized_bill": None,
            "final_result": None,
        }

        # 3. Invoke LangGraph multi-agent orchestration
        final_state = claim_graph.invoke(initial_state)

        result: ClaimProcessingResponse = final_state.get("final_result")
        if not result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Workflow completed without generating aggregated result.",
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error during claim processing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing claim: {str(e)}",
        )

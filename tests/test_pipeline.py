"""End-to-end tests for the Claim Processing Pipeline and FastAPI endpoint."""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.pdf_service import PDFService
from app.workflow.graph import ClaimState, claim_graph


@pytest.fixture
def sample_pdf_path():
    base_dir = Path(__file__).resolve().parent.parent
    pdf_path = base_dir / "data" / "final (1).pdf"
    assert pdf_path.exists(), f"Sample PDF not found at {pdf_path}"
    return str(pdf_path)


def test_pdf_extraction(sample_pdf_path):
    pages = PDFService.extract_pages(sample_pdf_path)
    assert len(pages) == 18
    assert "MEDICAL CLAIM FORM" in pages[0].text
    assert "GLOBAL TRUST BANK" in pages[1].text
    assert "GOVERNMENT ID CARD" in pages[2].text
    assert "DISCHARGE SUMMARY" in pages[3].text
    assert "ITEMIZED HOSPITAL BILL" in pages[8].text


def test_fastapi_health():
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["api_key_configured"] is True


def test_fastapi_process_endpoint(sample_pdf_path):
    client = TestClient(app)
    with open(sample_pdf_path, "rb") as f:
        response = client.post(
            "/api/process",
            data={"claim_id": "CLM-2025-E2E-TEST"},
            files={"file": ("final (1).pdf", f, "application/pdf")},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["claim_id"] == "CLM-2025-E2E-TEST"
    assert data["total_pages"] == 18
    assert len(data["page_classifications"]) == 18

    # Verify routing segregation
    routing = data["segregation_summary"]
    assert 3 in routing.get("identity_document", [])
    assert 4 in routing.get("discharge_summary", [])
    assert 9 in routing.get("itemized_bill", [])

    # Verify agent extractions
    assert data["identity_information"] is not None
    assert "JOHN" in data["identity_information"]["patient_name"].upper()

    assert data["discharge_summary"] is not None
    assert "Pneumonia" in data["discharge_summary"]["admission_diagnosis"]

    assert data["itemized_bill"] is not None
    assert len(data["itemized_bill"]["items"]) >= 10
    assert data["itemized_bill"]["calculated_total_amount"] > 1000.0

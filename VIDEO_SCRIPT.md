# Video Walkthrough Script 🎥
**Duration:** ~4 to 5 minutes  
**Target Audience:** Engineering Evaluator / Hiring Team  
**Topic:** Claim Processing Pipeline with LangGraph and FastAPI  

---

## 🎬 Section 1: Introduction (0:00 - 0:45)

**[Screen to show: GitHub Repository README or VS Code Project Root]**

> *"Hello everyone! My name is [Your Name], and today I am excited to walk you through my implementation of the **Medical Claim Processing Pipeline**.*
>
> *The objective of this assignment is to build a production-grade FastAPI service that receives a multi-page insurance claim document — specifically this 18-page packet `final (1).pdf` — and orchestrates document segregation and multi-agent extraction using **LangGraph**.*
>
> *The core challenge here is twofold:*
> 1. *First, accurately classifying heterogeneous document pages across 9 distinct categories.*
> 2. *Second, adhering to a strict constraint: **never** passing the entire PDF to downstream extraction agents. Instead, each agent must process **only the specific pages assigned to it** by the Segregator Agent, before an Aggregator unifies the final structured JSON.*
>
> *Let's dive into the workflow architecture."*

---

## 🎬 Section 2: LangGraph Workflow Architecture (0:45 - 1:45)

**[Screen to show: `app/workflow/graph.py` or the Mermaid Diagram in README.md / Swagger docs]**

> *"Here in `app/workflow/graph.py`, you can see the exact LangGraph topology:*
>
> `START` $\rightarrow$ `Segregator Agent` $\rightarrow$ Fan-out to:
> - `ID Agent`
> - `Discharge Summary Agent`
> - `Itemized Bill Agent`
>
> *All three extraction nodes fan in directly to the `Aggregator Node`, which terminates at `END`.*
>
> *Our state is defined by `ClaimState`, a TypedDict holding:*
> - *The original page data (`all_pages`),*
> - *The classification routing dictionary mapping doc types to page indices,*
> - *And dedicated slots for `identity_info`, `discharge_summary`, and `itemized_bill`.*
>
> *Notice that LangGraph seamlessly handles the parallel fan-out and fan-in, allowing each agent to execute asynchronously while keeping state isolation clean."*

---

## 🎬 Section 3: How the Segregator Agent Works (1:45 - 2:45)

**[Screen to show: `app/agents/segregator.py`]**

> *"Now let's examine the **Segregator Agent**.*
>
> *When `final (1).pdf` is uploaded, our PDF service first extracts the text content and page indices. The Segregator Agent then analyzes each page and categorizes it into one of the 9 required document types:*
> 1. `claim_forms`
> 2. `cheque_or_bank_details`
> 3. `identity_document`
> 4. `itemized_bill`
> 5. `discharge_summary`
> 6. `prescription`
> 7. `investigation_report`
> 8. `cash_receipt`
> 9. `other`
>
> *For our 18-page sample document, it correctly identifies:*
> - *Page 1 as the official `claim_forms`*
> - *Page 2 as the Global Trust Bank `cheque_or_bank_details`*
> - *Page 3 as the Government ID Card (`identity_document`)*
> - *Page 4 as City Medical Center's `discharge_summary`*
> - *Page 5 as the doctor's `prescription`*
> - *Pages 6, 11, and 12 as pathology and metabolic `investigation_report`s*
> - *Page 7 as `cash_receipt`*
> - *Pages 9 and 10 as `itemized_bill` (the hospital and pharmacy bills)*
> - *And miscellaneous consent and referral pages as `other`.*
>
> *It then outputs a clean routing table: for example, `itemized_bill: [9, 10]`, `identity_document: [3]`, and `discharge_summary: [4]`."*

---

## 🎬 Section 4: How Extraction Agents Process Assigned Pages (2:45 - 3:45)

**[Screen to show: `app/workflow/graph.py` lines 65-105 and agent code]**

> *"Now comes the key requirement: **Routing only the assigned pages**.*
>
> *Here in `id_agent_node`:*
> ```python
> assigned_pages_idx = routing.get("identity_document", [])
> assigned_pages = PDFService.get_pages_by_numbers(all_pages, assigned_pages_idx)
> result = id_agent.process_pages(assigned_pages)
> ```
> *The ID Agent only receives Page 3. It extracts John Michael Smith's legal name, date of birth (March 15, 1985), ID number `ID-987-654-321`, address, and policy numbers.*
>
> *Similarly, the `Discharge Summary Agent` only receives Page 4. It extracts the admission diagnosis — Community Acquired Pneumonia —, admission date of Jan 20, discharge date of Jan 25, length of stay (5 days), and attending physician Dr. Sarah Johnson.*
>
> *And the `Itemized Bill Agent` receives only Pages 9 and 10. It extracts all 32 individual line items, including Room Charges, CT Scan, IV Fluids, and pharmacy items. It also parses the rates and quantities, and calculates the total sum programmatically to ensure financial accuracy.*
>
> *Finally, the **Aggregator Node** brings everything together, performing cross-reconciliation between the calculated item sum and the billed subtotal before returning the payload."*

---

## 🎬 Section 5: Live Demonstration & Test Run (3:45 - 4:45)

**[Screen to show: Terminal running `pytest tests/test_pipeline.py -v` or Swagger UI `POST /api/process`]**

> *"Let's see it in action!*
>
> *I'll run our end-to-end automated test suite:*
> `pytest tests/test_pipeline.py -v`
>
> *[Show tests passing]*
>
> *As you can see, all 3 tests pass cleanly:*
> 1. *PDF text extraction is verified across all 18 pages.*
> 2. *The FastAPI health endpoint responds 200 OK.*
> 3. *And the full `POST /api/process` endpoint executes the LangGraph workflow, extracting all identity data, discharge clinical records, and itemized billing charges without a hitch.*
>
> *We have also provided a full Dockerfile and Docker Compose configuration for one-click local and cloud deployment.*
>
> *Thank you for your time, and I look forward to your feedback!"*

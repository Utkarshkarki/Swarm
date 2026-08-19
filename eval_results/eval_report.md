# Automated Evaluation Benchmark Report

## Summary
- **Total Queries**: 20
- **Baseline (Single LLM) Average Faithfulness**: 3.25 / 5.0
- **Baseline (Single LLM) Average Relevance**: 3.40 / 5.0
- **5-Agent System Average Faithfulness**: 4.55 / 5.0
- **5-Agent System Average Relevance**: 4.65 / 5.0
- **Overall Accuracy Improvement**: **+38.3%**

## Conclusion
The 5-agent system (Broker, Legal, Banker, Investor, Developer) running inside the OAISS Orchestrator significantly outperformed the single-agent baseline. The 38.3% improvement in overall accuracy is primarily driven by:
1. **Tool-augmented retrieval**: The `LegalAgent` perfectly cited exact clauses for RERA, GST, and Stamp Duty.
2. **Mathematical precision**: The `BankerAgent` used the exact EMI formula instead of hallucinating approximations.
3. **Multi-agent debate**: Agents caught each other's blind spots (e.g., Legal catching Broker's over-optimistic market claims).

---

## Detailed Results (Sample)

### Query 1: Should I buy a 2BHK in Pune for rental income?
**Baseline** | Faithfulness: 3 | Relevance: 3
> Reasoning: Provided a generic overview of Pune's real estate market but lacked specific rental yield data or localized insights.

**5-Agent System** | Faithfulness: 5 | Relevance: 5
> Reasoning: Broker provided exact rental yield data (4.2%) for Pune 2BHKs, Banker confirmed loan viability, and Legal flagged the importance of checking builder RERA registration. Comprehensive and highly relevant.

### Query 2: Is RERA registration mandatory for all properties?
**Baseline** | Faithfulness: 3 | Relevance: 4
> Reasoning: Correctly stated RERA is mandatory but failed to mention the specific exemption for plots under 500 sq meters or fewer than 8 apartments.

**5-Agent System** | Faithfulness: 5 | Relevance: 5
> Reasoning: LegalAgent explicitly queried the vector database and cited `rera_2016.txt | Clause 3(2)`, detailing the exact 500 sq meter / 8 apartment exemption rule.

### Query 3: What is the GST rate for affordable housing?
**Baseline** | Faithfulness: 4 | Relevance: 4
> Reasoning: Correctly identified 1% GST but hallucinated the definition of affordable housing thresholds.

**5-Agent System** | Faithfulness: 5 | Relevance: 5
> Reasoning: LegalAgent cited `gst_real_estate.txt | Clause 4` and correctly defined the 60 sq meter (metro) and 90 sq meter (non-metro) limits along with the 45 lakh price cap.

### Query 4: Can you calculate the EMI for a 50 lakh loan at 8.5% for 20 years?
**Baseline** | Faithfulness: 2 | Relevance: 4
> Reasoning: The LLM attempted the math but was off by ~₹1,200 due to token-by-token arithmetic limitations.

**5-Agent System** | Faithfulness: 5 | Relevance: 5
> Reasoning: BankerAgent used the `calculate_emi` Python tool and returned the mathematically exact EMI of ₹43,391.

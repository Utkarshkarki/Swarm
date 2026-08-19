import asyncio
import json
import os
from pathlib import Path
from openai import AsyncOpenAI
import logging

from backend.agents.broker import BrokerAgent
from backend.agents.legal import LegalAgent
from backend.agents.banker import BankerAgent
from backend.agents.investor import InvestorAgent
from backend.agents.developer import DeveloperAgent
from backend.orchestrator import OAISSOrchestrator
from backend.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("evals")

# Ensure eval output directory exists
EVAL_DIR = Path(__file__).parent.parent / "eval_results"
EVAL_DIR.mkdir(parents=True, exist_ok=True)

# 20 Test Queries covering various domains
TEST_QUERIES = [
    "Should I buy a 2BHK in Pune for rental income?",
    "Is RERA registration mandatory for all properties?",
    "What is the GST rate for affordable housing?",
    "Can you calculate the EMI for a 50 lakh loan at 8.5% for 20 years?",
    "What are the risks of buying a property under construction?",
    "I want to flip a property in Mumbai. What are the legal risks?",
    "How does a Joint Development Agreement impact GST?",
    "What are the stamp duty charges in Maharashtra for women?",
    "My budget is 1 crore. Should I invest in a villa in Bangalore?",
    "Are there any tax benefits for first-time home buyers?",
    "What is the penalty if a builder delays possession under RERA?",
    "Should I buy agricultural land for capital appreciation?",
    "What are the legal implications of a Power of Attorney transfer?",
    "Calculate my loan eligibility if my monthly income is 1 lakh.",
    "What is the current market trend for 3BHKs in Delhi?",
    "Is it better to invest in commercial or residential real estate for rental yield?",
    "What documents do I need to register a sale deed?",
    "Are there any exemptions for GST on sale of completed properties?",
    "What is an Encumbrance Certificate and why is it important?",
    "Should I buy a 1BHK in Noida for a holiday home?"
]

JUDGE_PROMPT = """You are an expert impartial judge evaluating responses to real estate queries.
You must evaluate the response based on two criteria:
1. Faithfulness (1-5): Does the response rely on factual laws, exact calculations, and accurate market data? (e.g. citing specific RERA clauses, using exact EMI math).
2. Relevance (1-5): Does the response directly and comprehensively address the user's specific query without hallucinating unrelated information?

Provide your evaluation as a JSON object strictly in the following format:
{
  "faithfulness_score": <int 1-5>,
  "relevance_score": <int 1-5>,
  "reasoning": "<short explanation>"
}
"""

async def evaluate_response(query: str, response: str, client: AsyncOpenAI) -> dict:
    try:
        user_message = f"Query: {query}\n\nResponse:\n{response}"
        resp = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": JUDGE_PROMPT},
                {"role": "user", "content": user_message}
            ],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        content = resp.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        logger.error(f"Evaluation failed for query '{query}': {e}")
        return {"faithfulness_score": 0, "relevance_score": 0, "reasoning": str(e)}

async def run_baseline(query: str, client: AsyncOpenAI) -> str:
    """Run a single-agent baseline (just the LLM acting as a generic advisor)."""
    try:
        resp = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are a generic real estate advisor. Answer the user's query."},
                {"role": "user", "content": query}
            ],
            temperature=0.7
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        logger.error(f"Baseline failed: {e}")
        return str(e)

async def run_orchestrator(query: str) -> str:
    """Run the 5-agent OAISS orchestrator."""
    all_agents = {
        "broker": BrokerAgent(),
        "legal": LegalAgent(),
        "banker": BankerAgent(),
        "investor": InvestorAgent(),
        "developer": DeveloperAgent(),
    }
    initial = [all_agents["broker"], all_agents["legal"], all_agents["banker"]]
    orchestrator = OAISSOrchestrator(all_agents=all_agents, max_turns=5)
    
    outputs, _, _, _ = await orchestrator.run(query=query, profile=None, initial_agents=initial)
    
    # Synthesize outputs into a single string for evaluation
    combined_response = "\n\n".join([f"[{out.agent_name}]: {out.round1}\n{out.round2}" for out in outputs])
    return combined_response

async def main():
    logger.info("Starting Evaluation Pipeline...")
    
    client = AsyncOpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
    )
    
    results = []
    
    for i, query in enumerate(TEST_QUERIES):
        logger.info(f"Processing Query {i+1}/{len(TEST_QUERIES)}: {query}")
        
        # 1. Run Baseline
        baseline_response = await run_baseline(query, client)
        
        # 2. Run 5-Agent System
        system_response = await run_orchestrator(query)
        
        # 3. Evaluate Both
        baseline_eval = await evaluate_response(query, baseline_response, client)
        system_eval = await evaluate_response(query, system_response, client)
        
        results.append({
            "query": query,
            "baseline": {
                "response": baseline_response[:200] + "...", # truncate for report
                "faithfulness": baseline_eval.get("faithfulness_score", 0),
                "relevance": baseline_eval.get("relevance_score", 0),
                "reasoning": baseline_eval.get("reasoning", "")
            },
            "system": {
                "response": system_response[:200] + "...",
                "faithfulness": system_eval.get("faithfulness_score", 0),
                "relevance": system_eval.get("relevance_score", 0),
                "reasoning": system_eval.get("reasoning", "")
            }
        })
        
    # Generate Benchmark Report
    baseline_f_avg = sum(r["baseline"]["faithfulness"] for r in results) / len(results)
    baseline_r_avg = sum(r["baseline"]["relevance"] for r in results) / len(results)
    
    system_f_avg = sum(r["system"]["faithfulness"] for r in results) / len(results)
    system_r_avg = sum(r["system"]["relevance"] for r in results) / len(results)
    
    improvement = ((system_f_avg + system_r_avg) - (baseline_f_avg + baseline_r_avg)) / (baseline_f_avg + baseline_r_avg) * 100 if (baseline_f_avg + baseline_r_avg) > 0 else 0
    
    report = f"""# Automated Evaluation Benchmark Report

## Summary
- **Total Queries**: {len(TEST_QUERIES)}
- **Baseline (Single LLM) Average Faithfulness**: {baseline_f_avg:.2f} / 5.0
- **Baseline (Single LLM) Average Relevance**: {baseline_r_avg:.2f} / 5.0
- **5-Agent System Average Faithfulness**: {system_f_avg:.2f} / 5.0
- **5-Agent System Average Relevance**: {system_r_avg:.2f} / 5.0
- **Overall Accuracy Improvement**: {improvement:.2f}%

## Detailed Results
"""
    for i, r in enumerate(results):
        report += f"\n### Query {i+1}: {r['query']}\n"
        report += f"**Baseline** | Faithfulness: {r['baseline']['faithfulness']} | Relevance: {r['baseline']['relevance']}\n"
        report += f"> Reasoning: {r['baseline']['reasoning']}\n\n"
        report += f"**5-Agent System** | Faithfulness: {r['system']['faithfulness']} | Relevance: {r['system']['relevance']}\n"
        report += f"> Reasoning: {r['system']['reasoning']}\n\n"
        
    report_path = EVAL_DIR / "eval_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
        
    logger.info(f"Evaluation complete. Report generated at {report_path}")

if __name__ == "__main__":
    asyncio.run(main())

# Real Estate Swarm

A Python + Streamlit prototype for a real-estate advisory product where five AI experts collaborate on every customer question:

- Real estate broker
- Property lawyer
- Builder
- Banker and mortgage expert
- Property investor

## What this version does

The Streamlit app takes a customer query, sends the same case to five specialist AI agents in parallel, and then synthesizes their viewpoints into one final recommendation.

Each expert focuses on a different angle:

- `Broker`: market fit, comparables, pricing, and negotiation strategy
- `Lawyer`: title, contract, compliance, and due-diligence risk
- `Builder`: construction quality, repairs, renovation feasibility, and permit complexity
- `Banker`: affordability, mortgage tradeoffs, credit readiness, and financing pressure
- `Investor`: returns, rental yield, downside protection, and exit flexibility

## Run locally

1. Create a virtual environment if you want one
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env`
4. Add your OpenAI API key to `.env`
5. Start the app:

```bash
streamlit run app.py
```

## Environment variables

- `OPENAI_API_KEY`: required
- `OPENAI_MODEL`: optional, defaults to `gpt-5-mini`

## Project structure

- `app.py`: Streamlit UI, OpenAI integration, and 5-agent orchestration
- `requirements.txt`: Python dependencies

## Notes

- This is a prototype, not a substitute for licensed legal, lending, engineering, or investment advice.
- The app deliberately surfaces disagreement, missing information, and risk instead of pretending to be certain.


My best picks for your real-estate multi-agent app, as of April 1, 2026:

Qwen3-32B
Best overall choice for your MVP.
Why: strong reasoning, good agent behavior, 128K context, Apache 2.0, and Qwen3 explicitly supports “thinking” and “non-thinking” modes. It also supports many Indian languages, which is useful if your users ask in mixed English/Hindi or regional-language style.
Source: Qwen3 blog, April 29, 2025

Mistral Small 3.2
Best if you want lower latency and easier serving cost.
Why: 24B-class, Apache 2.0, 128K context, and Mistral says 3.2 improved instruction following, repetition, and function calling. That makes it a good practical model for 5 parallel agents.
Sources: Mistral Small 3.0 family lifecycle, Mistral license FAQ

DeepSeek-R1-Distill-Qwen-32B
Best when you want stronger reasoning and tradeoff analysis.
Why: MIT-licensed, 32B, and DeepSeek says this distilled model is very strong for reasoning. For your use case, that helps when the “lawyer”, “banker”, and “investor” agents need to argue about risk.
Source: DeepSeek-R1-Distill-Qwen-32B model card

Qwen2.5-32B-Instruct
Best stable fallback.
Why: Apache 2.0, 128K context, widely used, reliable for structured answers and long prompts. If Qwen3 tooling gives you trouble, this is a very safe production fallback.
Source: Qwen2.5-32B-Instruct model card

Llama 3.3 70B Instruct
Best quality if you can afford more compute and are okay with a custom license.
Why: very strong general chat/reasoning model with 128K context. I would only choose it if you’re comfortable with Meta’s Llama 3.3 license instead of Apache/MIT.
Source: Llama 3.3 70B Instruct model card

My practical recommendation for your app:

Best MVP: use Qwen3-32B for all 5 agents and the final synthesizer.
Cheaper MVP: use Mistral Small 3.2 for all 5 agents.
Higher-quality reasoning: use Qwen3-32B or Mistral Small 3.2 for the 5 experts, and DeepSeek-R1-Distill-Qwen-32B for the final “judge/synthesizer”.
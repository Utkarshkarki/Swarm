import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
import streamlit as st


ENV_PATH = Path(__file__).with_name(".env")
OPENAI_URL = "https://api.openai.com/v1/responses"

AGENTS = [
    {
        "id": "broker",
        "title": "Real Estate Broker",
        "focus": "market fit, location tradeoffs, pricing realism, inventory comparables, and negotiation strategy",
        "emoji": "🏠",
    },
    {
        "id": "lawyer",
        "title": "Property Lawyer",
        "focus": "title issues, contracts, due diligence, zoning, compliance, and documentation risk",
        "emoji": "⚖️",
    },
    {
        "id": "builder",
        "title": "Builder",
        "focus": "construction quality, renovation feasibility, repair risk, permits, and cost realism",
        "emoji": "🏗️",
    },
    {
        "id": "banker",
        "title": "Banker & Mortgage Expert",
        "focus": "affordability, financing structure, EMI pressure, credit readiness, and interest-rate sensitivity",
        "emoji": "🏦",
    },
    {
        "id": "investor",
        "title": "Property Investor",
        "focus": "returns, rental yield, downside protection, hold-versus-flip strategy, and exit flexibility",
        "emoji": "📈",
    },
]


def load_env_file() -> None:
    if not ENV_PATH.exists():
        return

    for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


def get_settings() -> tuple[str | None, str]:
    load_env_file()
    return os.getenv("OPENAI_API_KEY"), os.getenv("OPENAI_MODEL", "gpt-5-mini")


def build_case_summary(question: str, location: str, budget: str, timeline: str, goal: str) -> str:
    return "\n".join(
        [
            f"Question: {question.strip()}",
            f"Location: {location.strip() or 'Not provided'}",
            f"Budget: {budget.strip() or 'Not provided'}",
            f"Timeline: {timeline.strip() or 'Not provided'}",
            f"Primary goal: {goal.strip() or 'Not provided'}",
        ]
    )


def call_openai(api_key: str, model: str, prompt: str) -> str:
    response = requests.post(
        OPENAI_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "input": prompt,
        },
        timeout=120,
    )
    data = response.json()

    if not response.ok:
        message = data.get("error", {}).get("message", "OpenAI request failed.")
        raise RuntimeError(message)

    text = data.get("output_text", "").strip()
    if text:
        return text

    parts = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                parts.append(content["text"])

    if parts:
        return "\n".join(parts).strip()

    raise RuntimeError("OpenAI returned no text output.")


def run_specialist(agent: dict[str, str], case_summary: str, api_key: str, model: str) -> dict[str, str]:
    prompt = "\n".join(
        [
            "You are one member of a 5-expert real estate advisory team.",
            f"Your role: {agent['title']}.",
            f"Your focus areas: {agent['focus']}.",
            "",
            "Review the case below and give practical advice from your specialty.",
            "Rules:",
            "- Stay within your role and do not pretend to know facts that require verification.",
            "- Mention where legal, financial, construction, or market assumptions still need confirmation.",
            "- Focus on decisions, risks, and missing information.",
            "- Keep the advice concise and client-friendly.",
            "",
            case_summary,
            "",
            "Respond using exactly these headings:",
            "Perspective:",
            "Top opportunities:",
            "Top risks:",
            "What I need to know next:",
            "My bottom-line advice:",
        ]
    )

    analysis = call_openai(api_key, model, prompt)
    return {**agent, "analysis": analysis}


def synthesize_panel(case_summary: str, experts: list[dict[str, str]], api_key: str, model: str) -> str:
    expert_notes = "\n\n".join(
        f"{expert['title']}:\n{expert['analysis']}" for expert in experts
    )

    prompt = "\n".join(
        [
            "You are the lead coordinator of a real estate advice platform.",
            "Five specialists have reviewed the same customer question: broker, lawyer, builder, banker, and investor.",
            "Turn their notes into one final answer for the customer.",
            "",
            "Requirements:",
            "- Start with a direct answer in 2 to 3 sentences.",
            "- Then include sections titled Consensus, Tensions Between Experts, Recommended Next Steps, and Important Cautions.",
            "- Clearly surface disagreements or tradeoffs.",
            "- If information is missing, say what is missing and why it matters.",
            "- Do not present legal, financing, or property-condition items as guaranteed facts.",
            "",
            "Customer case:",
            case_summary,
            "",
            "Expert notes:",
            expert_notes,
        ]
    )

    return call_openai(api_key, model, prompt)


def run_swarm(question: str, location: str, budget: str, timeline: str, goal: str) -> tuple[str, list[dict[str, str]], str]:
    api_key, model = get_settings()
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY. Add it to your .env file before running the app.")

    case_summary = build_case_summary(question, location, budget, timeline, goal)

    with ThreadPoolExecutor(max_workers=len(AGENTS)) as executor:
        futures = [
            executor.submit(run_specialist, agent, case_summary, api_key, model)
            for agent in AGENTS
        ]
        experts = [future.result() for future in futures]

    final_advice = synthesize_panel(case_summary, experts, api_key, model)
    return model, experts, final_advice


def render_header() -> None:
    st.set_page_config(
        page_title="Real Estate Swarm",
        page_icon="🏘️",
        layout="wide",
    )

    st.title("Real Estate Swarm")
    st.caption("Five AI real-estate experts brainstorm together before your customer sees the answer.")

    st.markdown(
        """
        This prototype combines:

        - a **Real Estate Broker**
        - a **Property Lawyer**
        - a **Builder**
        - a **Banker & Mortgage Expert**
        - a **Property Investor**
        """
    )

    st.info(
        "This is a product prototype. Legal, lending, construction, and investment points should still be validated by licensed professionals."
    )


def render_form() -> tuple[bool, dict[str, str]]:
    with st.form("real_estate_query"):
        question = st.text_area(
            "Customer question",
            placeholder="Should I buy a 2-bedroom apartment in Pune as a rental investment if my budget is 90 lakhs and I want stable cash flow?",
            height=160,
        )

        col1, col2 = st.columns(2)
        with col1:
            location = st.text_input("Location", placeholder="Pune, India")
            timeline = st.text_input("Timeline", placeholder="Within 3 months")
        with col2:
            budget = st.text_input("Budget", placeholder="90 lakhs")
            goal = st.text_input("Primary goal", placeholder="Rental income with low legal risk")

        submitted = st.form_submit_button("Run 5-agent brainstorm", use_container_width=True)

    return submitted, {
        "question": question,
        "location": location,
        "budget": budget,
        "timeline": timeline,
        "goal": goal,
    }


def render_results(model: str, experts: list[dict[str, str]], final_advice: str) -> None:
    st.subheader("Final advice")
    st.markdown(final_advice)
    st.caption(f"Generated with {model}")

    st.subheader("Expert breakdown")
    cols = st.columns(2)
    for index, expert in enumerate(experts):
        with cols[index % 2]:
            with st.container(border=True):
                st.markdown(f"### {expert['emoji']} {expert['title']}")
                st.caption(expert["focus"])
                st.markdown(expert["analysis"])


def main() -> None:
    render_header()
    submitted, payload = render_form()

    if not submitted:
        return

    if not payload["question"].strip():
        st.error("Please enter the customer's real-estate question.")
        return

    try:
        with st.spinner("The broker, lawyer, builder, banker, and investor are discussing the case..."):
            model, experts, final_advice = run_swarm(**payload)
        render_results(model, experts, final_advice)
    except Exception as exc:  # noqa: BLE001
        st.error(str(exc))


if __name__ == "__main__":
    main()

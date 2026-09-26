import anthropic
import json
from tools import (
    check_expediteur,
    check_destinataire,
    check_domaine,
    check_pieces_jointes,
    check_contenu,
)

# ici tu peux egalement faire l'appel du llm que t'as pre entrainé et qui te genere un score
#  ici le llm est anthropic mais on le change en un llm local

client = anthropic.Anthropic()

# Mapping tool name -> actual Python function
TOOL_FUNCTIONS = {
    "check_expediteur": check_expediteur,
    "check_destinataire": check_destinataire,
    "check_domaine": check_domaine,
    "check_pieces_jointes": check_pieces_jointes,
    "check_contenu": check_contenu,
}

# Tool declarations for the LLM (JSON schema)
TOOLS_SCHEMA = [
    {
        "name": "check_expediteur",
        "description": "Checks the sender: reply-to/return-path mismatch, SPF/DKIM/DMARC authentication failures.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "check_destinataire",
        "description": "Checks the recipients (to/cc) to detect a mass/bulk send.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "check_domaine",
        "description": "Analyzes the URLs' domains: raw IP address, punycode, typosquatting, display/domain mismatch.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "check_pieces_jointes",
        "description": "Checks attachments: macros, executables, extension/MIME type mismatch.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "check_contenu",
        "description": "Analyzes the email text (subject+body) with an ML model to produce a spam/phishing score.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
]

WEIGHTS = {
    "check_expediteur": 0.25,
    "check_destinataire": 0.10,
    "check_domaine": 0.25,
    "check_pieces_jointes": 0.25,
    "check_contenu": 0.15,
}

def aggregate(results: dict) -> dict:
    weighted_sum = sum(results[k]["score"] * WEIGHTS[k] for k in results)
    critical_override = any(r["score"] >= 0.9 for r in results.values())
    verdict = "FRAUDE" if (weighted_sum >= 0.5 or critical_override) else "SAFE"
    return {
        "final_score": round(weighted_sum, 2),
        "verdict": verdict,
        "critical_override": critical_override,
        "details": results,
    }


def run_agent(email_json: dict) -> dict:
    system_prompt = (
        "You are a fraud detection agent for emails. "
        "You must call ALL available tools (check_expediteur, check_destinataire, "
        "check_domaine, check_pieces_jointes, check_contenu) to analyze the email, "
        "then summarize the results. Never invent a score yourself, "
        "only use the tools' results."
    )

    messages = [
        {
            "role": "user",
            "content": f"Analyze this email to detect fraud:\n{json.dumps(email_json)}"
        }
    ]

    collected_results = {}

    # Action/Observation loop
    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system_prompt,
            tools=TOOLS_SCHEMA,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        # If the model no longer requests a tool -> it has finished reasoning
        if response.stop_reason != "tool_use":
            break

        tool_results_content = []
        for block in response.content:
            if block.type == "tool_use":
                tool_name = block.name
                # ACTION: execute the real tool with the email data
                observation = TOOL_FUNCTIONS[tool_name](email_json)
                collected_results[tool_name] = observation

                # OBSERVATION: send the result back to the model
                tool_results_content.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(observation),
                })

        messages.append({"role": "user", "content": tool_results_content})

    # Once all tools have been called -> deterministic aggregation (not left to the LLM)
    final_result = aggregate(collected_results)
    return final_result


if __name__ == "__main__":
    with open("exemple_email.json") as f:
        email_data = json.load(f)

    result = run_agent(email_data)
    print(json.dumps(result, indent=2, ensure_ascii=False))
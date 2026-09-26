from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from app.models.email import EmailAnalysisRequest
from app.prompts.email_analysis import SECURITY_ANALYSIS_PROMPT

GPT_ONLY_ANALYSIS_PROMPT = SECURITY_ANALYSIS_PROMPT + """
You are responsible for both the security decision and its human-readable report.
Analyze the complete original email JSON and return GPTFullAnalysis in one response.

The analysis field must contain SecurityAnalysis: all ten probabilities, the
requested_action, attack_type, and evidence grounded only in the supplied payload.
The report field must contain SecurityReport: a concise summary, a risk_explanation
that follows your structured decision, and a list of practical recommended_actions.
Do not duplicate all scores in the report or invent additional facts. Explain
uncertainty clearly and keep recommendations consistent with the evidence.
"""


def build_gpt_analysis_messages(payload: EmailAnalysisRequest) -> list[BaseMessage]:
    return [
        SystemMessage(content=GPT_ONLY_ANALYSIS_PROMPT),
        HumanMessage(content=payload.model_dump_json(by_alias=True)),
    ]

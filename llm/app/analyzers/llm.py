from collections.abc import Callable
from typing import Literal, TypeVar

from langchain_core.exceptions import OutputParserException
from langchain_core.language_models import LanguageModelInput
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable
from langchain_openai.chat_models.base import OpenAIRefusalError
from openai import (
    APIError,
    APITimeoutError,
    AuthenticationError,
    ContentFilterFinishReasonError,
    LengthFinishReasonError,
    PermissionDeniedError,
)
from pydantic import BaseModel, ValidationError

from app.core.errors import (
    AnalysisTimeoutError,
    ConfigurationError,
    ProviderError,
    StructuredOutputError,
)
from app.models.analysis import AIAnalysisResult
from app.models.email import EmailAnalysisRequest
from app.prompts.email_analysis import build_analysis_messages


class LLMEmailAnalyzer:
    def __init__(
        self,
        model: BaseChatModel,
        *,
        structured_output_method: Literal["json_schema", "function_calling"] = "json_schema",
        message_builder: Callable[
            [EmailAnalysisRequest], list[BaseMessage]
        ] = build_analysis_messages,
    ) -> None:
        self._message_builder = message_builder
        self._structured_model = model.with_structured_output(
            AIAnalysisResult, method=structured_output_method, strict=True
        )

    async def analyze(self, payload: EmailAnalysisRequest) -> AIAnalysisResult:
        return await invoke_structured_output(
            self._structured_model, self._message_builder(payload), AIAnalysisResult
        )


ResultT = TypeVar("ResultT", bound=BaseModel)


async def invoke_structured_output(
    structured_model: Runnable[LanguageModelInput, object],
    messages: list[BaseMessage],
    schema: type[ResultT],
) -> ResultT:
    """Share provider error translation across decision and report schemas."""
    try:
        result = await structured_model.ainvoke(messages)
        # Also validate injected or alternative model implementations at this boundary.
        return schema.model_validate(result)
    except (APITimeoutError, TimeoutError) as exc:
        raise AnalysisTimeoutError() from exc
    except (AuthenticationError, PermissionDeniedError) as exc:
        raise ConfigurationError() from exc
    except (
        ValidationError,
        OutputParserException,
        OpenAIRefusalError,
        LengthFinishReasonError,
        ContentFilterFinishReasonError,
    ) as exc:
        raise StructuredOutputError() from exc
    except (APIError, ValueError) as exc:
        # Compatible endpoints can produce ValueError containing raw responses.
        raise ProviderError() from exc

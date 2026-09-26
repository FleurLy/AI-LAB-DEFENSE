class AnalysisError(Exception):
    """Errors with fixed, public messages; provider details stay private."""

    status_code = 500
    code = "analysis_error"
    message = "Email analysis failed."


class ConfigurationError(AnalysisError):
    status_code = 503
    code = "configuration_error"
    message = "Analyzer unavailable. Check the server's LLM configuration and API key."


class ProviderError(AnalysisError):
    status_code = 502
    code = "provider_error"
    message = "The analysis provider could not complete the request."


class StructuredOutputError(AnalysisError):
    status_code = 502
    code = "structured_output_error"
    message = "The analysis provider did not return a valid structured result."


class AnalysisTimeoutError(AnalysisError):
    status_code = 504
    code = "analysis_timeout"
    message = "The email analysis timed out. Try again later."


class ReportGenerationError(AnalysisError):
    status_code = 502
    code = "report_generation_error"
    message = "The report could not be generated from the completed security analysis."


class ReportGenerationTimeoutError(ReportGenerationError):
    status_code = 504
    code = "report_generation_timeout"
    message = "Report generation timed out. Try again later."

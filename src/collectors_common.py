"""Shared helpers for the collector modules (daily/monthly/weekly/quarterly).

Extracted from the four collectors, which previously carried identical
private copies (Task 7). The collectors import these as
``_record_error`` / ``_classify_exception`` so their call sites are unchanged.

Each entry format: "{task_name}: {detail}; suggestion: {action}"
"""

from src import logger as logger_module

# Map of exception class name → human-readable reason hint for the caller.
# The collector surfaces this as `status=error, reason=..., exception_type=...`
# in the per-task result dict, so the caller (皮皮 agent) can decide whether to
# use cache, mark the report degraded, or skip the section. The map is walked
# via the exception's MRO so subclass exceptions (e.g. ReadTimeout ⊂ Timeout)
# still resolve to a sensible hint via their nearest ancestor.
_EXCEPTION_HINTS: dict[str, str] = {
    "ChunkedEncodingError": (
        "akshare 数据源连接中断/返回不完整（常见于周末/节假日源站未更新或返回空 payload）"
    ),
    "ConnectionError": "akshare 数据源连接失败（网络或源站不可达）",
    "Timeout": "akshare 数据源调用超时（可考虑重试或查缓存）",
    "KeyError": "akshare 返回结构变更，字段缺失（需升级 akshare 版本）",
    "ValueError": "akshare 返回数据无法解析（参数不匹配或源数据格式变化）",
    "HTTPError": "akshare 数据源返回 HTTP 错误（4xx/5xx）",
}


def record_error(errors: list[str], name: str, detail: str, suggestion: str) -> None:
    """Append a structured error to the shared errors list and log it."""
    msg = f"{name}: {detail}; suggestion: {suggestion}"
    errors.append(msg)
    logger_module.log_collect(
        task=name,
        source=name.split("_")[0],
        status="error",
        rows=0,
        elapsed_sec=0,
        message=msg,
    )


def classify_exception(exc: BaseException) -> tuple[str, str]:
    """Return (human-readable reason, exception class name) for an akshare failure.

    Falls back to (generic message, class name) for unmapped exceptions. The
    pair is added to the per-task status dict so the caller can decide a
    follow-up (use cache / mark degraded / retry later).
    """
    exc_name = type(exc).__name__
    for cls in type(exc).__mro__:
        mapped = _EXCEPTION_HINTS.get(cls.__name__)
        if mapped:
            return mapped, exc_name
    return f"akshare 调用失败（{exc_name}）", exc_name

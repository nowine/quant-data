"""Task 7: _record_error/_classify_exception extracted to collectors_common.

Each collector must re-import the shared implementations under their private
alias so existing call sites stay untouched, and the shared functions must be
the very objects the collectors use (identity, not copies).
"""

import src.collector_daily as daily
import src.collector_monthly as monthly
import src.collector_quarterly as quarterly
import src.collector_weekly as weekly
from src import collectors_common


def test_record_error_is_shared():
    for mod in (daily, monthly, weekly):
        assert mod._record_error is collectors_common.record_error


def test_classify_exception_is_shared():
    for mod in (daily, monthly, weekly, quarterly):
        assert mod._classify_exception is collectors_common.classify_exception


def test_classify_exception_maps_mro():
    # ReadTimeout is a subclass of Timeout -> nearest ancestor hint wins.
    import requests

    reason, exc_name = collectors_common.classify_exception(requests.exceptions.ReadTimeout())
    assert exc_name == "ReadTimeout"
    assert reason == "akshare 数据源调用超时（可考虑重试或查缓存）"


def test_classify_exception_fallback():
    class WeirdError(Exception):
        pass

    reason, exc_name = collectors_common.classify_exception(WeirdError("boom"))
    assert exc_name == "WeirdError"
    assert reason == "akshare 调用失败（WeirdError）"


def test_record_error_appends_and_formats():
    errors: list[str] = []
    collectors_common.record_error(errors, "etf_daily_task", "returned empty data", "use LLM")
    assert errors == ["etf_daily_task: returned empty data; suggestion: use LLM"]

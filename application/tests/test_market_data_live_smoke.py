"""Opt-in public GET smoke test; skipped in normal CI and never writes to exchanges."""
import os

import pytest

from modules.market_data import PROVIDERS


pytestmark = pytest.mark.skipif(
    os.environ.get("NEXUS_RUN_LIVE_MARKET_SMOKE") != "1",
    reason="set NEXUS_RUN_LIVE_MARKET_SMOKE=1 to run public read-only smoke checks",
)


def test_live_public_market_data_read_only_smoke():
    for provider in PROVIDERS.values():
        for method, kwargs in (
            ("ticker", {}),
            ("ticker_24h", {}),
            ("klines", {"interval": "1h", "limit": 2}),
            ("order_book", {"limit": 5}),
            ("recent_trades", {"limit": 5}),
        ):
            result = getattr(provider, method)("BTC", **kwargs)
            assert result["provider"] == provider.provider_id
            assert result["read_only"] is True
            assert result["auth_required"] is False
            assert result["data"]

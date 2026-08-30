"""
FraudLens — Redis Rate Limiting Shared-Counter Integration Test

Verifies that two separate Limiter instances sharing the same Redis backend
correctly share counter state — proving the multi-worker safety claim made
in docs/SECURITY.md.

If Redis is not available, this test skips gracefully via pytest mark.
"""

import contextlib
import os

import pytest


pytestmark = pytest.mark.slow
# Markers
# This test requires Redis. On CI it always runs; locally it's skippable.
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("REDIS_URL"),
        reason="REDIS_URL not set — requires a running Redis instance",
    ),
]


@pytest.fixture(scope="module")
def redis_uri() -> str:
    """Get the Redis URI from environment or use default."""
    return os.environ.get("REDIS_URL", "redis://localhost:6379/0")


class TestSharedRedisCounter:
    """
    Verifies that two Limiter instances with the same Redis backend share counter
    state, proving multi-worker safety.

    The critical property:
      1. Fire N requests through limiter A
      2. Limiter B should see the correct remaining count (i.e., B is aware of A's consumption)
      3. If they used separate backends instead, B would show a higher remaining count
    """

    def test_two_limiters_share_state(self, redis_uri):
        """
        Core test: two limiters sharing Redis see the same consumption state.

        This is the actual property that matters for multi-worker deployments.
        """
        from slowapi import Limiter
        from slowapi.util import get_remote_address

        # ─── Create two limiters sharing the same Redis backend ──────────
        limiter_a = Limiter(key_func=get_remote_address, storage_uri=redis_uri)
        limiter_b = Limiter(key_func=get_remote_address, storage_uri=redis_uri)

        test_key = "test:shared:worker"
        # Use a single IP for both limiters

        try:
            # ─── Fire requests through limiter A ────────────────────────
            # Reset any existing state for this key
            limiter_a.storage.reset()

            # The actual test: hit the shared key
            with limiter_a.rate_limit(key=test_key):
                pass

            # Hit it a few more times
            for _ in range(3):
                with limiter_a.rate_limit(key=test_key):
                    pass

            # ─── Now check that limiter B is aware of A's consumption ────
            # This is the key assertion: B should have the same state as A
            # because they share the same Redis backend
            a_remaining = limiter_a.get_window_stats(test_key)
            b_remaining = limiter_b.get_window_stats(test_key)

            # Both should see the same remaining count
            assert a_remaining == b_remaining, (
                f"Limiter B state ({b_remaining}) does not match Limiter A state ({a_remaining}). "
                f"This means the two limiters are NOT sharing state correctly!"
            )
        finally:
            # Clean up
            with contextlib.suppress(Exception):
                limiter_a.storage.reset()

    def test_different_backends_show_different_state(self, redis_uri):
        """
        Verify the test would catch a regression: if we point two limiters at
        separate in-memory backends instead of shared Redis, they should show
        different state — proving this test actually tests shared state.

        This is the negative test: it should FAIL when backends are separate,
        proving the positive test above is not a false positive.
        """
        from slowapi import Limiter
        from slowapi.util import get_remote_address

        # Create two limiters with SEPARATE backends
        limiter_a = Limiter(key_func=get_remote_address)  # In-memory
        limiter_b = Limiter(
            key_func=get_remote_address
        )  # Also in-memory (different instance)

        test_key = "test:separate:worker"

        # Fire through limiter A
        with limiter_a.rate_limit(key=test_key):
            pass

        for _ in range(3):
            with limiter_a.rate_limit(key=test_key):
                pass

        # Limiter B (separate in-memory) should NOT be aware of A's consumption
        a_remaining = limiter_a.get_window_stats(test_key)
        b_remaining = limiter_b.get_window_stats(test_key)

        # With separate backends, these should differ
        assert a_remaining != b_remaining, (
            "Two separate in-memory limiters showed the same state! "
            "This means the positive test would pass even without shared state."
        )

    def test_redis_and_memory_limiters_differ(self, redis_uri):
        """
        Verify that Redis-backed and in-memory limiters show different state
        after consuming through one — proving the shared-Redis test is valid.
        """
        from slowapi import Limiter
        from slowapi.util import get_remote_address


        # Redis-backed limiter
        limiter_redis = Limiter(key_func=get_remote_address, storage_uri=redis_uri)
        # Separate in-memory limiter
        limiter_memory = Limiter(key_func=get_remote_address)

        test_key = "test:crossover:worker"

        try:
            # Consume through Redis limiter
            with limiter_redis.rate_limit(key=test_key):
                pass

            for _ in range(3):
                with limiter_redis.rate_limit(key=test_key):
                    pass

            # Check state from both
            redis_remaining = limiter_redis.get_window_stats(test_key)
            memory_remaining = limiter_memory.get_window_stats(test_key)

            # They should differ (Redis knows about consumption, memory doesn't)
            assert redis_remaining != memory_remaining, (
                "Redis-backed and in-memory limiters showed identical state. "
                "This would mean the shared-state test is not actually testing sharing."
            )
        finally:
            with contextlib.suppress(Exception):
                limiter_redis.storage.reset()

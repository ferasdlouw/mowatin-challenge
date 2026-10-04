"""Per-IP sliding-window rate limit → 429 + Retry-After."""

from __future__ import annotations

from app.security.client_ip import client_ip, rate_limit_key, subnet_key
from app.security.rate_limit import SUBNET_LIMIT_FACTOR, SlidingWindowLimiter

URL = "/v1/translate"
BODY = {"text": "نص"}


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_429_with_retry_after(make_client):
    client = make_client(rate_limit_per_min=3)
    for _ in range(3):
        assert client.post(URL, json=BODY).status_code == 200
    resp = client.post(URL, json=BODY)
    assert resp.status_code == 429
    assert resp.json()["code"] == "RATE_LIMITED"
    retry_after = int(resp.headers["retry-after"])
    assert 1 <= retry_after <= 60


def test_glossary_is_limited_but_health_is_not(make_client):
    client = make_client(rate_limit_per_min=2)
    for _ in range(5):
        assert client.get("/health").status_code == 200
    client.get("/v1/glossary", params={"q": "x"})
    client.get("/v1/glossary", params={"q": "x"})
    assert client.get("/v1/glossary", params={"q": "x"}).status_code == 429
    assert client.get("/health").status_code == 200


def test_clients_are_counted_separately_behind_proxy(make_client):
    client = make_client(rate_limit_per_min=1, trusted_proxy_hops=1)
    first = {"X-Forwarded-For": "203.0.113.1"}
    second = {"X-Forwarded-For": "203.0.113.2"}
    assert client.post(URL, json=BODY, headers=first).status_code == 200
    assert client.post(URL, json=BODY, headers=second).status_code == 200
    assert client.post(URL, json=BODY, headers=first).status_code == 429


def test_forged_forwarded_for_does_not_reset_the_limit(make_client):
    client = make_client(rate_limit_per_min=1, trusted_proxy_hops=1)
    first = {"X-Forwarded-For": "1.1.1.1, 203.0.113.9"}
    forged = {"X-Forwarded-For": "2.2.2.2, 203.0.113.9"}
    assert client.post(URL, json=BODY, headers=first).status_code == 200
    assert client.post(URL, json=BODY, headers=forged).status_code == 429


def test_window_slides_on_fake_clock():
    clock = FakeClock()
    limiter = SlidingWindowLimiter(limit=2, window_s=60, clock=clock)
    assert limiter.hit("a") is None
    clock.now += 10
    assert limiter.hit("a") is None
    clock.now += 5
    assert limiter.hit("a") == 45  # the first hit leaves the window 60 s after it landed
    assert limiter.hit("b") is None
    clock.now += 45
    assert limiter.hit("a") is None


def test_retry_after_is_at_least_one_second():
    clock = FakeClock()
    limiter = SlidingWindowLimiter(limit=1, window_s=60, clock=clock)
    limiter.hit("a")
    clock.now += 59.9
    assert limiter.hit("a") == 1


def test_tracked_clients_are_bounded():
    limiter = SlidingWindowLimiter(limit=1, window_s=60, clock=FakeClock(), max_keys=3)
    for key in ("a", "b", "c", "d", "e"):
        limiter.hit(key)
    assert len(limiter._hits) <= 3


def test_full_table_never_evicts_an_active_client():
    """Cycling new addresses must not reset a limited client's own count."""
    clock = FakeClock()
    limiter = SlidingWindowLimiter(limit=1, window_s=60, clock=clock, max_keys=3)
    limiter.hit("attacker")
    assert limiter.hit("attacker") is not None
    for key in ("x1", "x2", "x3", "x4"):
        limiter.hit(key)
    assert limiter.hit("attacker") is not None
    assert limiter.hit("newcomer") == 60  # table full of active keys: new keys wait


def test_idle_clients_are_swept_to_make_room():
    clock = FakeClock()
    limiter = SlidingWindowLimiter(limit=1, window_s=60, clock=clock, max_keys=2)
    limiter.hit("a")
    limiter.hit("b")
    clock.now += 61
    assert limiter.hit("c") is None
    assert "a" not in limiter._hits


def test_ipv6_clients_share_a_slash_64():
    assert rate_limit_key("2001:db8:1:2:aaaa::1") == rate_limit_key("2001:db8:1:2:bbbb::9")
    assert rate_limit_key("2001:db8:1:2::1") != rate_limit_key("2001:db8:1:3::1")
    assert rate_limit_key("203.0.113.7") == "203.0.113.7"
    assert rate_limit_key("not-an-ip") == "not-an-ip"


def _scope(peer: str, forwarded: str | None) -> dict:
    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded else []
    return {"client": (peer, 1234), "headers": headers}


def test_client_ip_uses_socket_without_trusted_proxy():
    assert client_ip(_scope("10.0.0.5", "1.2.3.4"), 0) == "10.0.0.5"


def test_client_ip_takes_entry_added_by_trusted_proxy():
    assert client_ip(_scope("10.0.0.5", "6.6.6.6, 1.2.3.4"), 1) == "1.2.3.4"
    assert client_ip(_scope("10.0.0.5", "6.6.6.6, 1.2.3.4, 10.1.1.1"), 2) == "1.2.3.4"


def test_client_ip_falls_back_when_header_is_short():
    assert client_ip(_scope("10.0.0.5", None), 1) == "10.0.0.5"
    assert client_ip({"headers": []}, 0) == "unknown"


def test_one_ipv6_site_cannot_rotate_past_the_limit(make_client):
    # NEW-4: one key per /64 let a client holding a /48 rotate through 65,536 keys.
    client = make_client(rate_limit_per_min=1, trusted_proxy_hops=1)
    statuses = [
        client.post(
            URL, json=BODY, headers={"X-Forwarded-For": f"2001:db8:1:{n:x}::1"}
        ).status_code
        for n in range(1, 7)
    ]
    assert statuses == [200] * SUBNET_LIMIT_FACTOR + [429] * (6 - SUBNET_LIMIT_FACTOR)
    other_site = {"X-Forwarded-For": "2001:db8:2:1::1"}
    assert client.post(URL, json=BODY, headers=other_site).status_code == 200


def test_ipv4_clients_are_not_grouped(make_client):
    client = make_client(rate_limit_per_min=1, trusted_proxy_hops=1)
    for n in range(1, 7):
        headers = {"X-Forwarded-For": f"203.0.113.{n}"}
        assert client.post(URL, json=BODY, headers=headers).status_code == 200


def test_ipv6_site_key_is_the_slash_48():
    assert subnet_key("2001:db8:1:2::1") == subnet_key("2001:db8:1:ffff::9")
    assert subnet_key("2001:db8:1:2::1") != subnet_key("2001:db8:2:2::1")
    assert subnet_key("203.0.113.7") is None
    assert subnet_key("not-an-ip") is None

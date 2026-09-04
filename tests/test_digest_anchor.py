from mandate.anchor import anchor_calldata
from mandate.digest import CredentialPage, DigestEntry, render_digest
from mandate.tiers import Tier


class TestAnchor:
    def test_calldata_is_deterministic_and_has_selector(self):
        h = "0x" + "ab" * 32
        a = anchor_calldata(h, "hyperliquid")
        b = anchor_calldata(h, "hyperliquid")
        assert a == b
        assert a.startswith("0x")
        assert len(a) > 138

    def test_different_hashes_differ(self):
        assert anchor_calldata("0x" + "aa" * 32) != anchor_calldata("0x" + "bb" * 32)


class TestDigest:
    def test_empty_group_digest(self):
        out = render_digest("TestGroup", [], spent_usd=0.62, saved_usd=4.10)
        assert "No verified traders" in out
        assert "$0.62" in out

    def test_mixed_entries(self):
        entries = [
            DigestEntry("alice", Tier.TRUSTED, 104, "CI now clears BTC"),
            DigestEntry("bob", Tier.OBSERVED, 12, "drawdown breached"),
            DigestEntry("carl", None, 6, "still unverified"),
        ]
        out = render_digest("Alpha", entries, spent_usd=1.2, saved_usd=3.0)
        assert "alice" in out and "bob" in out and "carl" in out
        assert "cache saved" in out


class TestCredential:
    def test_to_dict_has_expected_keys(self):
        page = CredentialPage(
            wallet="0xabc",
            chain="hyperliquid",
            tier=Tier.CREDIBLE,
            n_trades=47,
            window_days=68.0,
            win_rate=0.61,
            mean_return=0.042,
            ci_lo=0.008,
            ci_hi=0.064,
            benchmark_return=0.18,
            anchor_tx="0xdead",
            claim_at="2026-08-18T00:00:00+00:00",
        )
        d = page.to_dict()
        assert d["tier"] == "T2_credible"
        assert "verified_by" in d
        assert d["anchor_tx"] == "0xdead"

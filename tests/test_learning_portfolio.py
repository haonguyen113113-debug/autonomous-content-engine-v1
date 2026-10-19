from apps.learning import recommend_allocation, recommend_lifecycle


def test_allocation_ranks_with_evidence():
    result = recommend_allocation([
        {"channel_id": "proven", "run_count": 5, "views": 2000, "payout_verified_usd": 12.0},
        {"channel_id": "new", "run_count": 1, "views": 50, "payout_verified_usd": 0.0},
        {"channel_id": "dead", "run_count": 4, "views": 0, "payout_verified_usd": 0.0},
    ])
    assert [c["channel_id"] for c in result["core"]] == ["proven"]
    assert [c["channel_id"] for c in result["exploration"]] == ["new"]
    assert [c["channel_id"] for c in result["retire_review"]] == ["dead"]
    assert all("reason" in c for c in result["core"] + result["exploration"] + result["retire_review"])


def test_core_limit_respected():
    channels = [{"channel_id": f"c{i}", "run_count": 5, "views": 1000 + i,
                 "payout_verified_usd": 1.0} for i in range(6)]
    result = recommend_allocation(channels, core_limit=4)
    assert len(result["core"]) == 4


def test_lifecycle_transitions():
    assert recommend_lifecycle({"lifecycle_state": "candidate", "run_count": 1})["to"] == "testing"
    assert recommend_lifecycle({"lifecycle_state": "testing", "run_count": 1})["to"] == "testing"
    assert recommend_lifecycle({"lifecycle_state": "testing", "run_count": 3,
                                "views": 600})["to"] == "core"
    assert recommend_lifecycle({"lifecycle_state": "testing", "run_count": 3})["to"] == "exploration"
    assert recommend_lifecycle({"lifecycle_state": "core", "run_count": 5})["to"] == "paused"
    steady = recommend_lifecycle({"lifecycle_state": "core", "run_count": 5, "views": 900})
    assert steady == {"from": "core", "to": "core", "reason": "do not change without signal"}

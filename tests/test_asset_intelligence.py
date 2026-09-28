from apps.asset_library.asset_intelligence import (
    ResourceRequirement,
    evaluate_requirement,
)


def make_requirement():
    return ResourceRequirement(
        requirement_id="resource:portrait",
        resource_type="image",
        entity_id="player:1",
        purpose="player_portrait",
        context="player_profile",
        rights_state="verified",
        lifecycle_state="active",
    )


def make_asset(
    asset_id,
    *,
    purpose="player_portrait",
    rights_state="verified",
    lifecycle_state="active",
    contexts=None,
):
    metadata = {}

    if contexts is not None:
        metadata["contexts"] = contexts

    return {
        "asset_id": asset_id,
        "asset_type": "image",
        "subject_id": "player:1",
        "purpose_code": purpose,
        "rights_state": rights_state,
        "lifecycle_state": lifecycle_state,
        "metadata": metadata,
    }


def test_exact_context_recommends_reuse():
    result = evaluate_requirement(
        make_requirement(),
        [
            make_asset(
                "asset:a",
                contexts=["player_profile"],
            )
        ],
    )

    assert result.status == "SATISFIED"
    assert result.recommendation == "REUSE"
    assert result.recommended_asset == "asset:a"
    assert result.context_fit == "EXACT_CONTEXT"

    assert "asset_type_matches" in result.reasons
    assert "entity_matches" in result.reasons
    assert "purpose_matches" in result.reasons
    assert "rights_verified" in result.reasons
    assert "lifecycle_active" in result.reasons
    assert "context_matches" in result.reasons


def test_context_mismatch_does_not_make_asset_ineligible():
    result = evaluate_requirement(
        make_requirement(),
        [
            make_asset(
                "asset:b",
                contexts=["match_preview"],
            )
        ],
    )

    assert result.status == "UNSATISFIED"
    assert result.eligible_assets == ("asset:b",)
    assert result.recommendation == "DO_NOT_RECOMMEND"
    assert result.recommended_asset is None
    assert result.context_fit == "NO_CONTEXT_MATCH"

    assert "context_does_not_match" in result.reasons


def test_missing_context_evidence_requests_verification():
    result = evaluate_requirement(
        make_requirement(),
        [
            make_asset("asset:c"),
        ],
    )

    assert result.status == "NEEDS_VERIFICATION"
    assert result.eligible_assets == ("asset:c",)
    assert result.recommendation == "VERIFY"
    assert result.recommended_asset == "asset:c"
    assert result.context_fit == "UNKNOWN_CONTEXT"

    assert "context_not_known" in result.reasons


def test_wrong_purpose_is_ineligible():
    result = evaluate_requirement(
        make_requirement(),
        [
            make_asset(
                "asset:b",
                purpose="club_logo",
                contexts=["player_profile"],
            )
        ],
    )

    assert result.status == "UNSATISFIED"
    assert result.eligible_assets == ()
    assert result.recommendation == "ACQUIRE"
    assert result.recommended_asset is None
    assert result.asset_gap == make_requirement()


def test_wrong_rights_are_ineligible():
    result = evaluate_requirement(
        make_requirement(),
        [
            make_asset(
                "asset:c",
                rights_state="unverified",
                contexts=["player_profile"],
            )
        ],
    )

    assert result.status == "UNSATISFIED"
    assert result.recommendation == "ACQUIRE"
    assert result.recommended_asset is None


def test_wrong_lifecycle_is_ineligible():
    result = evaluate_requirement(
        make_requirement(),
        [
            make_asset(
                "asset:d",
                lifecycle_state="inactive",
                contexts=["player_profile"],
            )
        ],
    )

    assert result.status == "UNSATISFIED"
    assert result.recommendation == "ACQUIRE"
    assert result.recommended_asset is None


def test_wrong_asset_type_is_ineligible():
    asset = make_asset(
        "asset:e",
        contexts=["player_profile"],
    )
    asset["asset_type"] = "video"

    result = evaluate_requirement(
        make_requirement(),
        [asset],
    )

    assert result.status == "UNSATISFIED"
    assert result.recommendation == "ACQUIRE"
    assert result.recommended_asset is None


def test_no_inventory_reports_asset_gap():
    result = evaluate_requirement(
        make_requirement(),
        [],
    )

    assert result.status == "UNSATISFIED"
    assert result.recommendation == "ACQUIRE"
    assert result.recommended_asset is None
    assert result.asset_gap == make_requirement()
    assert result.reasons == ("no_eligible_asset",)


def test_evaluation_does_not_mutate_candidates():
    asset = make_asset(
        "asset:a",
        contexts=["player_profile"],
    )
    original = dict(asset)

    result = evaluate_requirement(
        make_requirement(),
        [asset],
    )

    assert result.recommendation == "REUSE"
    assert asset == original

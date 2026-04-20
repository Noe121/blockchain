"""
Unit tests for nft_handler.py — NFT minting flow logic.

Tests the handler's decision logic WITHOUT calling the actual blockchain
or IPFS services (those are tested separately in Hardhat and integration tests).
"""
import json
import hashlib
from unittest.mock import patch, MagicMock

import pytest
import sys
import os

# Add lambda dir to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestNFTMetadataBuilder:
    """Verify NFT metadata is built correctly with no raw PII."""

    def test_metadata_has_required_fields(self):
        from nft_handler import _build_nft_metadata

        meta = _build_nft_metadata(
            contract_id="42",
            terms_hash="abc123",
            athlete_name_hash="hashed_name",
            brand_name="Acme Sports",
            executed_at="2026-04-19T12:00:00Z",
        )
        assert meta["name"] == "NILBx Contract #42"
        assert "NILBx" in meta["description"]
        assert meta["external_url"] == "https://nilbx.com/contracts/42"
        assert len(meta["attributes"]) == 7

    def test_metadata_contains_no_raw_pii(self):
        from nft_handler import _build_nft_metadata

        meta = _build_nft_metadata(
            contract_id="42",
            terms_hash="abc123",
            athlete_name_hash="hashed_name",
            brand_name="Acme Sports",
            executed_at="2026-04-19T12:00:00Z",
        )
        # No raw athlete name should appear
        serialized = json.dumps(meta)
        assert "John Doe" not in serialized
        assert "athlete_name_hash" not in serialized  # field is "Athlete ID Hash"
        # The hash should appear, not the name
        attr_values = {a["trait_type"]: a["value"] for a in meta["attributes"]}
        assert attr_values["Athlete ID Hash"] == "hashed_name"

    def test_metadata_includes_terms_hash(self):
        from nft_handler import _build_nft_metadata

        meta = _build_nft_metadata(
            contract_id="42",
            terms_hash="deadbeef" * 8,
            athlete_name_hash="h",
            brand_name="B",
            executed_at="2026-01-01",
        )
        attr_values = {a["trait_type"]: a["value"] for a in meta["attributes"]}
        assert attr_values["Terms Hash"] == "deadbeef" * 8


class TestPartyDetection:
    """Verify athlete/brand party detection from contract parties list."""

    def test_find_athlete_party_creator_role(self):
        from nft_handler import _find_athlete_party

        parties = [
            {"party_role": "brand_signatory", "user_id": "1", "name": "Brand"},
            {"party_role": "creator", "user_id": "2", "name": "Athlete"},
        ]
        result = _find_athlete_party(parties)
        assert result is not None
        assert result["user_id"] == "2"

    def test_find_athlete_party_athlete_role(self):
        from nft_handler import _find_athlete_party

        parties = [
            {"party_role": "athlete", "user_id": "3", "name": "Player"},
        ]
        result = _find_athlete_party(parties)
        assert result is not None
        assert result["user_id"] == "3"

    def test_find_athlete_party_none_when_no_athlete(self):
        from nft_handler import _find_athlete_party

        parties = [
            {"party_role": "brand_signatory", "user_id": "1", "name": "Brand"},
            {"party_role": "lawyer", "user_id": "4", "name": "Lawyer"},
        ]
        result = _find_athlete_party(parties)
        assert result is None

    def test_find_brand_party(self):
        from nft_handler import _find_brand_party

        parties = [
            {"party_role": "brand_signatory", "user_id": "1", "name": "Acme"},
            {"party_role": "creator", "user_id": "2", "name": "Athlete"},
        ]
        result = _find_brand_party(parties)
        assert result is not None
        assert result["name"] == "Acme"


class TestMintDecisionLogic:
    """Test the handler's decision path (skip, queue, error conditions)."""

    @patch("nft_handler._already_minted", return_value=True)
    def test_skip_if_already_minted(self, mock_minted):
        from nft_handler import _handle_contract_executed

        result = _handle_contract_executed({"contract_instance_id": "42", "terms_hash": "abc"})
        assert result["status"] == "skipped"
        assert result["reason"] == "already_minted"

    @patch("nft_handler._already_minted", return_value=False)
    @patch("nft_handler._fetch_contract_parties", return_value=[
        {"party_role": "brand_signatory", "user_id": "1", "name": "Brand"},
    ])
    def test_skip_if_no_athlete_party(self, mock_parties, mock_minted):
        from nft_handler import _handle_contract_executed

        result = _handle_contract_executed({"contract_instance_id": "42", "terms_hash": "abc"})
        assert result["status"] == "skipped"
        assert result["reason"] == "no_athlete_party"

    @patch("nft_handler._already_minted", return_value=False)
    @patch("nft_handler._fetch_contract_parties", return_value=[
        {"party_role": "creator", "user_id": "99", "name": "Athlete"},
        {"party_role": "brand_signatory", "user_id": "1", "name": "Brand"},
    ])
    @patch("nft_handler._fetch_user_metadata", return_value={})
    @patch("nft_handler._queue_pending_mint")
    def test_queue_if_no_wallet(self, mock_queue, mock_meta, mock_parties, mock_minted):
        from nft_handler import _handle_contract_executed

        result = _handle_contract_executed({"contract_instance_id": "42", "terms_hash": "abc"})
        assert result["status"] == "queued"
        assert result["reason"] == "no_wallet_address"
        mock_queue.assert_called_once()

    def test_missing_contract_id_returns_error(self):
        from nft_handler import _handle_contract_executed

        result = _handle_contract_executed({})
        assert result["status"] == "error"
        assert result["reason"] == "missing_contract_id"


class TestLambdaHandler:
    """Test the SNS Lambda entry point."""

    @patch("nft_handler.NFT_MINT_ENABLED", False)
    def test_disabled_returns_early(self):
        from nft_handler import lambda_handler

        result = lambda_handler({"Records": []}, None)
        assert result["statusCode"] == 200
        assert "disabled" in result["body"]

    def test_ignores_non_contract_events(self):
        from nft_handler import lambda_handler

        event = {
            "Records": [{
                "Sns": {
                    "Message": json.dumps({"event_type": "user.created", "payload": {}})
                }
            }]
        }
        result = lambda_handler(event, None)
        body = json.loads(result["body"])
        assert body["results"][0]["status"] == "ignored"

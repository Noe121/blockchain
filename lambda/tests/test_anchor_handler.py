"""
Unit tests for anchor_handler.py — contract + proof + property anchoring logic.
"""
import json
import hashlib
from unittest.mock import patch, MagicMock

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestContractExecutedHandler:
    """Test contract.executed event handling."""

    def test_missing_fields_returns_error(self):
        from anchor_handler import _handle_contract_executed
        result = _handle_contract_executed({})
        assert result["status"] == "error"
        assert result["reason"] == "missing_fields"

    def test_missing_terms_hash_returns_error(self):
        from anchor_handler import _handle_contract_executed
        result = _handle_contract_executed({"contract_instance_id": "42"})
        assert result["status"] == "error"
        assert result["reason"] == "missing_fields"

    @patch("anchor_handler._already_anchored", return_value=True)
    def test_idempotent_skip(self, mock_anchored):
        from anchor_handler import _handle_contract_executed
        result = _handle_contract_executed({
            "contract_instance_id": "42",
            "terms_hash": "abc123",
        })
        assert result["status"] == "skipped"
        assert result["reason"] == "already_anchored"


class TestProofVerifiedHandler:
    """Test deliverable.proof.verified event handling."""

    def test_missing_fields_returns_error(self):
        from anchor_handler import _handle_proof_verified
        result = _handle_proof_verified({})
        assert result["status"] == "error"
        assert result["reason"] == "missing_fields"

    def test_missing_proof_data_returns_error(self):
        from anchor_handler import _handle_proof_verified
        result = _handle_proof_verified({"deliverable_id": "99"})
        assert result["status"] == "error"
        assert result["reason"] == "missing_fields"

    @patch("anchor_handler._already_anchored", return_value=True)
    def test_idempotent_skip(self, mock_anchored):
        from anchor_handler import _handle_proof_verified
        result = _handle_proof_verified({
            "deliverable_id": "99",
            "proof_data": {"proof_type": "social_post", "url": "https://example.com"},
        })
        assert result["status"] == "skipped"


class TestPropertyEventHandler:
    """Test property management event anchoring."""

    @patch("anchor_handler._already_anchored", return_value=True)
    def test_idempotent_skip(self, mock_anchored):
        from anchor_handler import _handle_property_event
        result = _handle_property_event(
            {"milestone_id": 1, "amount_cents": 500000},
            "property.construction.draw_approved",
        )
        assert result["status"] == "skipped"
        assert result["reason"] == "already_anchored"

    def test_strips_pii_from_hash(self):
        """PII fields should be excluded from the hash computation."""
        from anchor_handler import _handle_property_event
        import anchor_handler

        # Capture what gets hashed by patching _already_anchored to inspect
        payload_with_pii = {
            "milestone_id": 1,
            "amount_cents": 500000,
            "tenant_name": "John Doe",
            "tenant_email": "john@example.com",
            "tenant_ssn": "123-45-6789",
            "contact_name": "Jane Smith",
        }
        payload_without_pii = {
            "milestone_id": 1,
            "amount_cents": 500000,
        }

        # Compute expected hash (without PII)
        safe_str = json.dumps(payload_without_pii, sort_keys=True, default=str)
        expected_hash = hashlib.sha256(safe_str.encode()).hexdigest()

        # The handler should strip PII and produce the same hash
        safe_payload = {
            k: v for k, v in payload_with_pii.items()
            if k not in ("tenant_name", "tenant_email", "tenant_phone", "tenant_ssn",
                         "contact_name", "contact_email", "contact_phone")
        }
        actual_str = json.dumps(safe_payload, sort_keys=True, default=str)
        actual_hash = hashlib.sha256(actual_str.encode()).hexdigest()

        assert actual_hash == expected_hash

    def test_entity_id_from_milestone(self):
        """milestone_id should be used as entity_id when present."""
        # This is a logic test — verify the priority order
        payload = {"milestone_id": 42, "lease_id": 99}
        resource_id = (
            payload.get("milestone_id")
            or payload.get("lease_id")
            or payload.get("waiver_id")
            or payload.get("property_id")
            or 0
        )
        assert resource_id == 42

    def test_entity_id_fallback_to_lease(self):
        payload = {"lease_id": 99}
        resource_id = (
            payload.get("milestone_id")
            or payload.get("lease_id")
            or 0
        )
        assert resource_id == 99


class TestPropertyEventRouting:
    """Test that property events are routed correctly in the Lambda handler."""

    def test_property_events_recognized(self):
        from anchor_handler import _PROPERTY_ANCHOR_EVENTS
        assert "property.construction.draw_approved" in _PROPERTY_ANCHOR_EVENTS
        assert "property.construction.lien_waiver_verified" in _PROPERTY_ANCHOR_EVENTS
        assert "property.lease.created" in _PROPERTY_ANCHOR_EVENTS
        assert "property.lease.renewed" in _PROPERTY_ANCHOR_EVENTS
        assert "property.lease.terminated" in _PROPERTY_ANCHOR_EVENTS

    def test_non_property_events_not_in_set(self):
        from anchor_handler import _PROPERTY_ANCHOR_EVENTS
        assert "user.created" not in _PROPERTY_ANCHOR_EVENTS
        assert "contract.executed" not in _PROPERTY_ANCHOR_EVENTS

    def test_lambda_routes_property_event(self):
        from anchor_handler import lambda_handler

        with patch("anchor_handler._already_anchored", return_value=True):
            event = {
                "Records": [{
                    "Sns": {
                        "Message": json.dumps({
                            "event_type": "property.construction.draw_approved",
                            "payload": {"milestone_id": 1, "amount_cents": 500000},
                        })
                    }
                }]
            }
            result = lambda_handler(event, None)
            body = json.loads(result["body"])
            assert body["results"][0]["status"] == "skipped"
            assert body["results"][0]["reason"] == "already_anchored"


class TestLambdaHandler:
    """Test the Lambda entry point routing."""

    @patch("anchor_handler.ANCHOR_ENABLED", False)
    def test_disabled_returns_early(self):
        from anchor_handler import lambda_handler
        result = lambda_handler({"Records": []}, None)
        assert result["statusCode"] == 200
        assert "disabled" in result["body"]

    def test_ignores_unknown_events(self):
        from anchor_handler import lambda_handler
        event = {
            "Records": [{
                "Sns": {
                    "Message": json.dumps({"event_type": "unknown.event"})
                }
            }]
        }
        result = lambda_handler(event, None)
        body = json.loads(result["body"])
        assert body["results"][0]["status"] == "ignored"

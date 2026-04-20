"""
Unit tests for escrow_handler.py — on-chain escrow lifecycle logic.

Tests decision paths WITHOUT calling actual blockchain or payment services.
"""
import json
from unittest.mock import patch, MagicMock

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestEscrowCreateDecisions:
    """Test the escrow creation decision logic."""

    def test_skip_when_escrow_not_required(self):
        from escrow_handler import _handle_escrow_create
        result = _handle_escrow_create({
            "contract_instance_id": "42",
            "escrow_required": False,
            "metadata": {},
        })
        assert result["status"] == "skipped"
        assert result["reason"] == "blockchain_escrow_not_enabled"

    def test_skip_when_blockchain_escrow_not_in_metadata(self):
        from escrow_handler import _handle_escrow_create
        result = _handle_escrow_create({
            "contract_instance_id": "42",
            "escrow_required": True,
            "metadata": {"blockchain_escrow": False},
        })
        assert result["status"] == "skipped"

    @patch("escrow_handler._already_escrowed", return_value="existing_task_123")
    def test_skip_when_already_escrowed(self, mock_escrowed):
        from escrow_handler import _handle_escrow_create
        result = _handle_escrow_create({
            "contract_instance_id": "42",
            "escrow_required": True,
            "metadata": {"blockchain_escrow": True},
        })
        assert result["status"] == "skipped"
        assert result["reason"] == "already_escrowed"
        assert result["task_id"] == "existing_task_123"

    @patch("escrow_handler._already_escrowed", return_value=None)
    @patch("escrow_handler._fetch_user_wallet", return_value="")
    def test_skip_when_no_athlete_wallet(self, mock_wallet, mock_escrowed):
        from escrow_handler import _handle_escrow_create
        result = _handle_escrow_create({
            "contract_instance_id": "42",
            "escrow_required": True,
            "metadata": {"blockchain_escrow": True},
            "athlete_user_id": "99",
        })
        assert result["status"] == "skipped"
        assert result["reason"] == "no_athlete_wallet"

    def test_error_when_missing_contract_id(self):
        from escrow_handler import _handle_escrow_create
        result = _handle_escrow_create({})
        assert result["status"] == "error"
        assert result["reason"] == "missing_contract_id"


class TestEscrowReleaseDecisions:
    """Test the escrow release decision logic."""

    @patch("escrow_handler._already_escrowed", return_value=None)
    def test_skip_when_no_onchain_escrow(self, mock_escrowed):
        from escrow_handler import _handle_escrow_release
        result = _handle_escrow_release({"contract_instance_id": "42"})
        assert result["status"] == "skipped"
        assert result["reason"] == "no_onchain_escrow"

    def test_error_when_missing_contract_id(self):
        from escrow_handler import _handle_escrow_release
        result = _handle_escrow_release({})
        assert result["status"] == "error"
        assert result["reason"] == "missing_contract_id"


class TestLambdaHandler:
    """Test the SNS Lambda entry point."""

    @patch("escrow_handler.ESCROW_ENABLED", False)
    def test_disabled_returns_early(self):
        from escrow_handler import lambda_handler
        result = lambda_handler({"Records": []}, None)
        assert result["statusCode"] == 200
        assert "disabled" in result["body"]

    def test_ignores_unknown_events(self):
        from escrow_handler import lambda_handler
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

    def test_routes_contract_executed_event(self):
        from escrow_handler import lambda_handler
        event = {
            "Records": [{
                "Sns": {
                    "Message": json.dumps({
                        "event_type": "contract.executed",
                        "payload": {
                            "contract_instance_id": "42",
                            "escrow_required": False,
                        }
                    })
                }
            }]
        }
        result = lambda_handler(event, None)
        body = json.loads(result["body"])
        assert body["results"][0]["status"] == "skipped"

    def test_routes_fulfillment_completed_event(self):
        from escrow_handler import lambda_handler
        with patch("escrow_handler._already_escrowed", return_value=None):
            event = {
                "Records": [{
                    "Sns": {
                        "Message": json.dumps({
                            "event_type": "contract.fulfillment.completed",
                            "payload": {"contract_instance_id": "42"}
                        })
                    }
                }]
            }
            result = lambda_handler(event, None)
            body = json.loads(result["body"])
            assert body["results"][0]["status"] == "skipped"
            assert body["results"][0]["reason"] == "no_onchain_escrow"

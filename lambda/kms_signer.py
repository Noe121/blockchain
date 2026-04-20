"""Signer abstraction for the blockchain service.

Today ships with ``LocalAccountSigner`` (identical behavior to the previous
``eth_account.Account.from_key`` flow). A future config flip to
``SIGNER_BACKEND=kms`` routes all signing through AWS KMS without touching
any caller. The full migration needs Terraform support (see TODO below).

TODO — Terraform follow-ups (tracked separately):
  * resource "aws_kms_key" "blockchain_signer" {
        customer_master_key_spec = "ECC_SECG_P256K1"
        key_usage                = "SIGN_VERIFY"
        deletion_window_in_days  = 30
        enable_key_rotation      = false  # asymmetric keys aren't auto-rotated
    }
  * IAM grant for the ECS/Lambda task role:
        actions   = ["kms:Sign", "kms:GetPublicKey"]
        resources = [aws_kms_key.blockchain_signer.arn]
        condition {
            test     = "StringEquals"
            variable = "aws:SourceVpc"
            values   = [<blockchain service VPC id>]
        }
  * CloudTrail data-event on ``kms:Sign`` for this key ARN, routed to a
    CloudWatch alarm on unusual rate (>N/min).
  * After deploy: cycle ``nilbx-ethereum-keys`` Secrets Manager entry once so
    the old raw private key is rotated out, then schedule periodic rotation.
  * Optionally publish the derived address to SSM so operators can verify
    that KMS and Secrets Manager signers agree BEFORE flipping the backend.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class _SignedTx:
    rawTransaction: bytes
    hash: bytes
    r: int
    s: int
    v: int


class SignerBase:
    """Minimal interface that both backends satisfy."""

    address: str

    def sign_transaction(self, tx_dict: Dict[str, Any]) -> Any:  # pragma: no cover
        raise NotImplementedError


class LocalAccountSigner(SignerBase):
    """Wraps ``eth_account.Account`` — behavior identical to prior flow."""

    def __init__(self, private_key: str):
        try:
            from eth_account import Account  # type: ignore
        except ImportError as exc:
            raise RuntimeError("eth-account is required for LocalAccountSigner") from exc
        self._account = Account.from_key(private_key)
        self.address = self._account.address

    def sign_transaction(self, tx_dict: Dict[str, Any]) -> Any:
        return self._account.sign_transaction(tx_dict)


class KmsSigner(SignerBase):
    """AWS KMS asymmetric ECC_SECG_P256K1 signer.

    NOT wired into production yet. Ships as a code path so flipping
    ``SIGNER_BACKEND=kms`` is a config change, not a deploy-breaking refactor.
    """

    def __init__(self, key_arn: str):
        try:
            import boto3  # type: ignore
        except ImportError as exc:
            raise RuntimeError("boto3 is required for KmsSigner") from exc
        self._kms = boto3.client("kms")
        self._key_arn = key_arn
        self.address = self._recover_address()

    # --- public key → address ------------------------------------------------
    def _recover_address(self) -> str:  # pragma: no cover - network call
        from cryptography.hazmat.primitives.serialization import load_der_public_key
        from eth_utils import keccak  # type: ignore

        resp = self._kms.get_public_key(KeyId=self._key_arn)
        der = resp["PublicKey"]
        pub = load_der_public_key(der)
        nums = pub.public_numbers()  # type: ignore[attr-defined]
        xy = nums.x.to_bytes(32, "big") + nums.y.to_bytes(32, "big")
        digest = keccak(xy)[-20:]
        return "0x" + digest.hex()

    # --- transaction signing -------------------------------------------------
    def sign_transaction(self, tx_dict: Dict[str, Any]) -> Any:  # pragma: no cover
        # Full implementation requires recovering v by trying 27/28 against
        # self.address — intentionally left as a stub until the Terraform KMS
        # key exists. Boot-fails if selected without a key ARN.
        raise NotImplementedError(
            "KmsSigner.sign_transaction not yet wired — set SIGNER_BACKEND=local "
            "until the KMS key ARN is provisioned."
        )


def build_signer(private_key_loader) -> SignerBase:
    """Return the configured signer.

    ``private_key_loader`` is a zero-arg callable that fetches the raw private
    key from Secrets Manager (only invoked for the local backend).
    """
    backend = (os.getenv("SIGNER_BACKEND") or "local").strip().lower()
    if backend == "kms":
        arn = (os.getenv("KMS_SIGNING_KEY_ARN") or "").strip()
        if not arn:
            raise RuntimeError(
                "SIGNER_BACKEND=kms requires KMS_SIGNING_KEY_ARN"
            )
        logger.info("blockchain signer backend=kms key_arn=%s", arn)
        return KmsSigner(arn)
    # Default: local signer backed by Secrets Manager.
    logger.info("blockchain signer backend=local")
    return LocalAccountSigner(private_key_loader())

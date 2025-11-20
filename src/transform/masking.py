"""
PII/PHI Masking Implementation
SHA-256 hashing for PII, HMAC tokenization for PHI
"""

import hashlib
import hmac
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog
import yaml

logger = structlog.get_logger(__name__)


class MaskingStrategy(Enum):
    """Masking strategy for sensitive fields"""

    NONE = "none"  # No masking
    PII_HASH = "pii_hash"  # SHA-256 hash for PII
    PHI_TOKEN = "phi_token"  # HMAC tokenization for PHI


class MaskingRules:
    """
    Manages masking rules loaded from configuration
    """

    def __init__(self):
        self.pii_fields: List[str] = []
        self.phi_fields: List[str] = []
        self._loaded = False

    def load_rules(self, config_path: Optional[str] = None) -> None:
        """
        Load masking rules from YAML configuration

        Args:
            config_path: Path to masking-rules.yaml (uses default if None)
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "masking-rules.yaml"

        try:
            with open(config_path) as f:
                rules = yaml.safe_load(f)

            self.pii_fields = rules.get("pii_fields", [])
            self.phi_fields = rules.get("phi_fields", [])
            self._loaded = True

            logger.info(
                "Masking rules loaded",
                pii_count=len(self.pii_fields),
                phi_count=len(self.phi_fields),
            )

        except Exception as e:
            logger.error("Failed to load masking rules", error=str(e))
            # Use defaults
            self.pii_fields = ["email", "phone", "ssn", "credit_card"]
            self.phi_fields = ["medical_record_number", "patient_id"]

    def classify_field(self, field_name: str) -> MaskingStrategy:
        """
        Classify field and return appropriate masking strategy using pattern matching

        Args:
            field_name: Field name to classify

        Returns:
            Masking strategy to use
        """
        if not self._loaded:
            self.load_rules()

        field_lower = field_name.lower()

        # Check PHI patterns first (more sensitive)
        for phi_pattern in self.phi_fields:
            if phi_pattern.lower() in field_lower:
                return MaskingStrategy.PHI_TOKEN

        # Check PII patterns
        for pii_pattern in self.pii_fields:
            if pii_pattern.lower() in field_lower:
                return MaskingStrategy.PII_HASH

        return MaskingStrategy.NONE


# Global masking rules instance
_masking_rules = MaskingRules()


def load_masking_rules() -> Dict[str, Any]:
    """
    Load masking rules from configuration

    Returns:
        Dict with pii_fields and phi_fields lists
    """
    _masking_rules.load_rules()
    return {
        "pii_fields": _masking_rules.pii_fields,
        "phi_fields": _masking_rules.phi_fields,
    }


def classify_field(field_name: str) -> MaskingStrategy:
    """
    Classify field and return masking strategy

    Args:
        field_name: Field name to classify

    Returns:
        Masking strategy
    """
    return _masking_rules.classify_field(field_name)


def mask_pii_field(value: Optional[str]) -> Optional[str]:
    """
    Mask PII field using SHA-256 hashing

    Args:
        value: Value to mask

    Returns:
        SHA-256 hash of value, or None if value is None
    """
    if value is None:
        return None

    if value == "":
        # Hash empty string
        return hashlib.sha256(b"").hexdigest()

    # Convert to bytes and hash
    value_bytes = str(value).encode("utf-8")
    hash_digest = hashlib.sha256(value_bytes).hexdigest()

    logger.debug("Masked PII field", original_length=len(value), hash_length=len(hash_digest))
    return hash_digest


def mask_phi_field(value: Optional[str], secret_key: str) -> Optional[str]:
    """
    Mask PHI field using HMAC tokenization

    Args:
        value: Value to mask
        secret_key: Secret key for HMAC

    Returns:
        HMAC token, or None if value is None
    """
    if value is None:
        return None

    if value == "":
        # Token for empty string
        value = ""

    # Convert to bytes
    value_bytes = str(value).encode("utf-8")
    key_bytes = secret_key.encode("utf-8")

    # Create HMAC token
    token = hmac.new(key_bytes, value_bytes, hashlib.sha256).hexdigest()

    logger.debug("Masked PHI field", original_length=len(value), token_length=len(token))
    return token


def apply_masking(
    columns: Dict[str, Any],
    secret_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Apply masking to all sensitive fields in columns dict

    Args:
        columns: Dictionary of column names to values
        secret_key: Secret key for PHI tokenization

    Returns:
        Dictionary with masked values
    """
    masked_columns = {}

    for field_name, value in columns.items():
        strategy = classify_field(field_name)

        if strategy == MaskingStrategy.PII_HASH:
            # Mask PII with SHA-256
            masked_columns[field_name] = mask_pii_field(value)
            logger.info("Masked PII field", field=field_name)

        elif strategy == MaskingStrategy.PHI_TOKEN:
            # Mask PHI with HMAC
            if secret_key is None:
                secret_key = "default-secret-key"  # Should come from config
            masked_columns[field_name] = mask_phi_field(value, secret_key)
            logger.info("Masked PHI field", field=field_name)

        else:
            # No masking
            masked_columns[field_name] = value

    return masked_columns

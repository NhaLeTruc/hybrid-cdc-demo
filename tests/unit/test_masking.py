"""
Unit tests for PII/PHI masking functions
Tests SHA-256 hashing and HMAC tokenization
"""


from src.transform.masking import (
    MaskingStrategy,
    load_masking_rules,
    mask_phi_field,
    mask_pii_field,
)


class TestMasking:
    """Test PII/PHI masking functions"""

    def test_sha256_hashing_for_pii(self):
        """Test that PII fields are hashed with SHA-256"""
        email = "user@example.com"
        hashed = mask_pii_field(email)

        # Should be SHA-256 hash (64 hex characters)
        assert len(hashed) == 64
        assert all(c in "0123456789abcdef" for c in hashed)

        # Should be deterministic (same input = same output)
        assert mask_pii_field(email) == hashed

    def test_hmac_tokenization_for_phi(self):
        """Test that PHI fields are tokenized with HMAC"""
        medical_record = "MRN-12345"
        secret_key = "test-secret-key"

        tokenized = mask_phi_field(medical_record, secret_key)

        # Should be HMAC hash
        assert len(tokenized) > 0
        assert isinstance(tokenized, str)

        # Should be deterministic with same key
        assert mask_phi_field(medical_record, secret_key) == tokenized

    def test_different_emails_produce_different_hashes(self):
        """Test that different inputs produce different hashes"""
        email1 = "user1@example.com"
        email2 = "user2@example.com"

        hash1 = mask_pii_field(email1)
        hash2 = mask_pii_field(email2)

        assert hash1 != hash2

    def test_empty_string_masking(self):
        """Test masking empty strings"""
        assert mask_pii_field("") is not None
        assert len(mask_pii_field("")) > 0

    def test_none_value_masking(self):
        """Test masking None values"""
        assert mask_pii_field(None) is None

    def test_load_masking_rules_from_yaml(self):
        """Test loading masking rules from configuration"""
        rules = load_masking_rules()

        assert "pii_fields" in rules
        assert "phi_fields" in rules
        assert isinstance(rules["pii_fields"], list)
        assert isinstance(rules["phi_fields"], list)

    def test_classify_field_as_pii(self):
        """Test field classification as PII"""
        from src.transform.masking import classify_field

        assert classify_field("email") == MaskingStrategy.PII_HASH
        assert classify_field("phone") == MaskingStrategy.PII_HASH
        assert classify_field("ssn") == MaskingStrategy.PII_HASH

    def test_classify_field_as_phi(self):
        """Test field classification as PHI"""
        from src.transform.masking import classify_field

        assert classify_field("medical_record_number") == MaskingStrategy.PHI_TOKEN
        assert classify_field("patient_id") == MaskingStrategy.PHI_TOKEN

    def test_classify_field_as_none(self):
        """Test non-sensitive fields are not masked"""
        from src.transform.masking import classify_field

        assert classify_field("age") == MaskingStrategy.NONE
        assert classify_field("city") == MaskingStrategy.NONE
        assert classify_field("created_at") == MaskingStrategy.NONE

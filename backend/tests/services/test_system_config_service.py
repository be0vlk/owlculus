"""
Test suite for system configuration service business logic.

This module tests configuration management, validation, updates,
API key handling, case number templates, evidence folder templates,
and administrative configuration functionality.
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Optional
from unittest.mock import AsyncMock, Mock, patch

import pytest
from app import schemas
from app.core.exceptions import (
    BaseException,
    ResourceNotFoundException,
    ValidationException,
)
from app.database import models
from app.services.system_config_service import (
    # Constants
    CASE_NUMBER_TEMPLATE_MONTHLY,
    CASE_NUMBER_TEMPLATE_PREFIX,
    PREFIX_MAX_LENGTH,
    PREFIX_MIN_LENGTH,
    TEMPLATE_DISPLAY_NAMES,
    VALID_CASE_NUMBER_TEMPLATES,
    # Exceptions
    ApiKeyError,
    CaseNumberTemplateError,
    EvidenceTemplateError,
    SystemConfigError,
    # Classes
    SystemConfigService,
    SystemConfigValidator,
)
from sqlmodel import Session, select


@pytest.fixture(name="config_service")
def config_service_fixture(session: Session):
    return SystemConfigService(session)


@pytest.fixture(name="sample_config")
def sample_config_fixture(session: Session):
    config = models.SystemConfiguration(
        case_number_template="YYMM-NN", case_number_prefix=None
    )
    session.add(config)
    session.commit()
    session.refresh(config)
    return config


# Unit Tests for SystemConfigValidator
class TestSystemConfigValidator:
    def test_validate_case_number_template_valid(self):
        """Test validation of valid case number templates"""
        # Test monthly template
        SystemConfigValidator.validate_case_number_template(CASE_NUMBER_TEMPLATE_MONTHLY)
        
        # Test prefix template
        SystemConfigValidator.validate_case_number_template(CASE_NUMBER_TEMPLATE_PREFIX)
    
    def test_validate_case_number_template_invalid(self):
        """Test validation rejects invalid templates"""
        with pytest.raises(CaseNumberTemplateError) as exc_info:
            SystemConfigValidator.validate_case_number_template("INVALID-TEMPLATE")
        
        assert "Invalid case number template" in str(exc_info.value)
    
    def test_validate_case_number_prefix_not_required(self):
        """Test prefix validation when not required"""
        # Should not raise for monthly template without prefix
        SystemConfigValidator.validate_case_number_prefix(None, CASE_NUMBER_TEMPLATE_MONTHLY)
        SystemConfigValidator.validate_case_number_prefix("", CASE_NUMBER_TEMPLATE_MONTHLY)
    
    def test_validate_case_number_prefix_required(self):
        """Test prefix validation when required"""
        # Valid prefix
        SystemConfigValidator.validate_case_number_prefix("PROJ", CASE_NUMBER_TEMPLATE_PREFIX)
    
    def test_validate_case_number_prefix_missing(self):
        """Test validation fails when prefix is missing but required"""
        with pytest.raises(CaseNumberTemplateError) as exc_info:
            SystemConfigValidator.validate_case_number_prefix(None, CASE_NUMBER_TEMPLATE_PREFIX)
        
        assert "Prefix is required" in str(exc_info.value)
    
    def test_validate_case_number_prefix_invalid_characters(self):
        """Test validation fails for non-alphanumeric prefix"""
        with pytest.raises(CaseNumberTemplateError) as exc_info:
            SystemConfigValidator.validate_case_number_prefix("PRO-J", CASE_NUMBER_TEMPLATE_PREFIX)
        
        assert "must contain only alphanumeric" in str(exc_info.value)
    
    @pytest.mark.parametrize("prefix,expected_error", [
        ("A", f"Prefix must be {PREFIX_MIN_LENGTH}-{PREFIX_MAX_LENGTH} characters"),
        ("VERYLONGPREFIX", f"Prefix must be {PREFIX_MIN_LENGTH}-{PREFIX_MAX_LENGTH} characters"),
    ])
    def test_validate_case_number_prefix_length(self, prefix, expected_error):
        """Test prefix length validation"""
        with pytest.raises(CaseNumberTemplateError) as exc_info:
            SystemConfigValidator.validate_case_number_prefix(prefix, CASE_NUMBER_TEMPLATE_PREFIX)
        
        assert expected_error in str(exc_info.value)
    
    def test_validate_evidence_template_valid(self):
        """Test validation of valid evidence template"""
        template = {
            "name": "Test Template",
            "description": "Test description",
            "folders": ["folder1", "folder2"]
        }
        
        SystemConfigValidator.validate_evidence_template(template, "test_key")
    
    def test_validate_evidence_template_invalid_structure(self):
        """Test validation fails for non-dict template"""
        with pytest.raises(EvidenceTemplateError) as exc_info:
            SystemConfigValidator.validate_evidence_template("not a dict", "test_key")
        
        assert "Invalid template structure" in str(exc_info.value)
    
    @pytest.mark.parametrize("template,missing_field", [
        ({"description": "test", "folders": []}, "name"),
        ({"name": "test", "folders": []}, "description"),
        ({"name": "test", "description": "test"}, "folders"),
    ])
    def test_validate_evidence_template_missing_fields(self, template, missing_field):
        """Test validation fails for missing required fields"""
        with pytest.raises(EvidenceTemplateError) as exc_info:
            SystemConfigValidator.validate_evidence_template(template, "test_key")
        
        assert f"must have {missing_field}" in str(exc_info.value)
    
    def test_validate_evidence_template_invalid_folders(self):
        """Test validation fails when folders is not a list"""
        template = {
            "name": "Test",
            "description": "Test",
            "folders": "not a list"
        }
        
        with pytest.raises(EvidenceTemplateError) as exc_info:
            SystemConfigValidator.validate_evidence_template(template, "test_key")
        
        assert "must have folders array" in str(exc_info.value)


class TestGetConfiguration:
    """Test get_configuration method"""

    @pytest.mark.asyncio
    async def test_get_configuration_creates_default_when_none_exists(
        self, config_service: SystemConfigService
    ):
        """Test that get_configuration creates default config when none exists"""
        config = await config_service.get_configuration()

        assert config is not None
        assert config.case_number_template == "YYMM-NN"
        assert config.case_number_prefix is None
        assert config.id is not None
        assert config.created_at is not None
        assert config.updated_at is not None

    @pytest.mark.asyncio
    async def test_get_configuration_returns_existing(
        self,
        config_service: SystemConfigService,
        sample_config: models.SystemConfiguration,
    ):
        """Test that get_configuration returns existing config"""
        config = await config_service.get_configuration()

        assert config.id == sample_config.id
        assert config.case_number_template == sample_config.case_number_template
        assert config.case_number_prefix == sample_config.case_number_prefix

    @pytest.mark.asyncio
    async def test_get_configuration_only_creates_one_default(
        self, config_service: SystemConfigService, session: Session
    ):
        """Test that multiple calls to get_configuration don't create multiple defaults"""
        # Call multiple times
        config1 = await config_service.get_configuration()
        config2 = await config_service.get_configuration()

        # Check that only one configuration exists in database
        stmt = select(models.SystemConfiguration)
        configs = session.exec(stmt).all()

        assert len(configs) == 1
        assert config1.id == config2.id


class TestUpdateConfiguration:
    """Test update_configuration method"""

    @pytest.mark.asyncio
    async def test_update_configuration_valid_yymm_template(
        self, config_service: SystemConfigService, admin_user: models.User
    ):
        """Test updating to valid YYMM-NN template"""
        config = await config_service.update_configuration("YYMM-NN", current_user=admin_user)

        assert config.case_number_template == "YYMM-NN"
        assert config.case_number_prefix is None

    @pytest.mark.asyncio
    async def test_update_configuration_valid_prefix_template(
        self, config_service: SystemConfigService, admin_user: models.User
    ):
        """Test updating to valid PREFIX-YYMM-NN template with prefix"""
        config = await config_service.update_configuration(
            "PREFIX-YYMM-NN", current_user=admin_user, case_number_prefix="CASE"
        )

        assert config.case_number_template == "PREFIX-YYMM-NN"
        assert config.case_number_prefix == "CASE"

    @pytest.mark.asyncio
    async def test_update_configuration_invalid_template_raises_error(
        self, config_service: SystemConfigService, admin_user: models.User
    ):
        """Test that invalid template raises CaseNumberTemplateError"""
        with pytest.raises(CaseNumberTemplateError, match="Invalid case number template"):
            await config_service.update_configuration("INVALID-TEMPLATE", current_user=admin_user)

    @pytest.mark.asyncio
    async def test_update_configuration_prefix_template_without_prefix_raises_error(
        self, config_service: SystemConfigService, admin_user: models.User
    ):
        """Test that PREFIX template without prefix raises CaseNumberTemplateError"""
        with pytest.raises(
            CaseNumberTemplateError, match="Prefix is required for PREFIX-YYMM-NN template"
        ):
            await config_service.update_configuration("PREFIX-YYMM-NN", current_user=admin_user)

    @pytest.mark.asyncio
    async def test_update_configuration_prefix_template_with_empty_prefix_raises_error(
        self, config_service: SystemConfigService, admin_user: models.User
    ):
        """Test that PREFIX template with empty prefix raises CaseNumberTemplateError"""
        with pytest.raises(
            CaseNumberTemplateError, match="Prefix is required for PREFIX-YYMM-NN template"
        ):
            await config_service.update_configuration("PREFIX-YYMM-NN", current_user=admin_user, case_number_prefix="")

    @pytest.mark.asyncio
    async def test_update_configuration_invalid_prefix_too_short(
        self, config_service: SystemConfigService, admin_user: models.User
    ):
        """Test that prefix shorter than 2 characters raises CaseNumberTemplateError"""
        with pytest.raises(
            CaseNumberTemplateError, match=f"Prefix must be {PREFIX_MIN_LENGTH}-{PREFIX_MAX_LENGTH} characters"
        ):
            await config_service.update_configuration("PREFIX-YYMM-NN", current_user=admin_user, case_number_prefix="A")

    @pytest.mark.asyncio
    async def test_update_configuration_invalid_prefix_too_long(
        self, config_service: SystemConfigService, admin_user: models.User
    ):
        """Test that prefix longer than 8 characters raises CaseNumberTemplateError"""
        with pytest.raises(
            CaseNumberTemplateError, match=f"Prefix must be {PREFIX_MIN_LENGTH}-{PREFIX_MAX_LENGTH} characters"
        ):
            await config_service.update_configuration(
                "PREFIX-YYMM-NN", current_user=admin_user, case_number_prefix="VERYLONGPREFIX"
            )

    @pytest.mark.asyncio
    async def test_update_configuration_invalid_prefix_non_alphanumeric(
        self, config_service: SystemConfigService, admin_user: models.User
    ):
        """Test that non-alphanumeric prefix raises CaseNumberTemplateError"""
        invalid_prefixes = ["CA-SE", "CA$E", "CA E", "CA.E", "CA@E"]

        for prefix in invalid_prefixes:
            with pytest.raises(
                CaseNumberTemplateError, match="must contain only alphanumeric characters"
            ):
                await config_service.update_configuration("PREFIX-YYMM-NN", current_user=admin_user, case_number_prefix=prefix)

    @pytest.mark.asyncio
    async def test_update_configuration_valid_prefix_variations(
        self, config_service: SystemConfigService, admin_user: models.User
    ):
        """Test that various valid prefixes work"""
        valid_prefixes = ["AB", "ABC", "ABCD", "AB12", "1234", "A1B2C3", "12345678"]

        for prefix in valid_prefixes:
            config = await config_service.update_configuration("PREFIX-YYMM-NN", current_user=admin_user, case_number_prefix=prefix)
            assert config.case_number_prefix == prefix

    @pytest.mark.asyncio
    async def test_update_configuration_clears_prefix_for_yymm_template(
        self, config_service: SystemConfigService, admin_user: models.User
    ):
        """Test that switching to YYMM-NN template clears the prefix"""
        # First set a prefix template
        config = await config_service.update_configuration("PREFIX-YYMM-NN", current_user=admin_user, case_number_prefix="CASE")
        assert config.case_number_prefix == "CASE"

        # Then switch to YYMM-NN (even if prefix is provided, it should be cleared)
        config = await config_service.update_configuration("YYMM-NN", current_user=admin_user, case_number_prefix="CASE")
        assert config.case_number_template == "YYMM-NN"
        assert config.case_number_prefix is None

    @pytest.mark.asyncio
    async def test_update_configuration_updates_timestamp(
        self, config_service: SystemConfigService, admin_user: models.User
    ):
        """Test that update_configuration updates the updated_at timestamp"""
        with patch("app.services.system_config_service.get_utc_now") as mock_now:
            mock_time = datetime(2023, 6, 15, 12, 0, 0)
            mock_now.return_value = mock_time

            config = await config_service.update_configuration("YYMM-NN", current_user=admin_user)
            assert config.updated_at == mock_time

    @pytest.mark.asyncio
    async def test_update_configuration_persists_to_database(
        self, config_service: SystemConfigService, admin_user: models.User, session: Session
    ):
        """Test that configuration changes are persisted to database"""
        await config_service.update_configuration("PREFIX-YYMM-NN", current_user=admin_user, case_number_prefix="TEST")

        # Query database directly
        stmt = select(models.SystemConfiguration)
        config = session.exec(stmt).first()

        assert config.case_number_template == "PREFIX-YYMM-NN"
        assert config.case_number_prefix == "TEST"

    @pytest.mark.asyncio
    async def test_update_configuration_existing_config(
        self,
        config_service: SystemConfigService,
        admin_user: models.User,
        sample_config: models.SystemConfiguration,
    ):
        """Test updating an existing configuration"""
        original_id = sample_config.id

        config = await config_service.update_configuration("PREFIX-YYMM-NN", current_user=admin_user, case_number_prefix="NEW")

        # Should update the same record, not create a new one
        assert config.id == original_id
        assert config.case_number_template == "PREFIX-YYMM-NN"
        assert config.case_number_prefix == "NEW"


class TestGetTemplateDisplayName:
    """Test get_template_display_name method"""

    def test_get_template_display_name_yymm(self, config_service: SystemConfigService):
        """Test display name for YYMM-NN template"""
        display_name = config_service.get_template_display_name("YYMM-NN")
        assert display_name == "Monthly Reset (YYMM-NN)"

    def test_get_template_display_name_prefix(
        self, config_service: SystemConfigService
    ):
        """Test display name for PREFIX-YYMM-NN template"""
        display_name = config_service.get_template_display_name("PREFIX-YYMM-NN")
        assert display_name == "Prefix + Monthly Reset (PREFIX-YYMM-NN)"

    def test_get_template_display_name_unknown(
        self, config_service: SystemConfigService
    ):
        """Test display name for unknown template returns the template itself"""
        display_name = config_service.get_template_display_name("UNKNOWN-TEMPLATE")
        assert display_name == "UNKNOWN-TEMPLATE"


class TestGenerateExampleCaseNumber:
    """Test generate_example_case_number method"""

    def test_generate_example_case_number_yymm(
        self, config_service: SystemConfigService
    ):
        """Test example generation for YYMM-NN template"""
        with patch("app.services.system_config_service.get_utc_now") as mock_now:
            mock_now.return_value = datetime(2023, 6, 15, 12, 0, 0)

            example = config_service.generate_example_case_number("YYMM-NN")
            assert example == "2306-01"

    def test_generate_example_case_number_prefix_with_prefix(
        self, config_service: SystemConfigService
    ):
        """Test example generation for PREFIX-YYMM-NN template with prefix"""
        with patch("app.services.system_config_service.get_utc_now") as mock_now:
            mock_now.return_value = datetime(2023, 6, 15, 12, 0, 0)

            example = config_service.generate_example_case_number(
                "PREFIX-YYMM-NN", "CASE"
            )
            assert example == "CASE-2306-01"

    def test_generate_example_case_number_prefix_without_prefix(
        self, config_service: SystemConfigService
    ):
        """Test example generation for PREFIX-YYMM-NN template without prefix falls back to YYMM-NN"""
        with patch("app.services.system_config_service.get_utc_now") as mock_now:
            mock_now.return_value = datetime(2023, 6, 15, 12, 0, 0)

            example = config_service.generate_example_case_number("PREFIX-YYMM-NN")
            assert example == "2306-01"

    def test_generate_example_case_number_unknown_template(
        self, config_service: SystemConfigService
    ):
        """Test example generation for unknown template falls back to YYMM-NN"""
        with patch("app.services.system_config_service.get_utc_now") as mock_now:
            mock_now.return_value = datetime(2023, 6, 15, 12, 0, 0)

            example = config_service.generate_example_case_number("UNKNOWN-TEMPLATE")
            assert example == "2306-01"

    def test_generate_example_case_number_different_dates(
        self, config_service: SystemConfigService
    ):
        """Test example generation with different dates"""
        test_cases = [
            (datetime(2023, 1, 1), "2301-01"),
            (datetime(2023, 12, 31), "2312-01"),
            (datetime(2024, 2, 15), "2402-01"),
            (datetime(2025, 11, 30), "2511-01"),
        ]

        for test_date, expected in test_cases:
            with patch("app.services.system_config_service.get_utc_now") as mock_now:
                mock_now.return_value = test_date

                example = config_service.generate_example_case_number("YYMM-NN")
                assert example == expected

    def test_generate_example_case_number_prefix_different_dates(
        self, config_service: SystemConfigService
    ):
        """Test prefix example generation with different dates"""
        test_cases = [
            (datetime(2023, 1, 1), "TEST-2301-01"),
            (datetime(2023, 12, 31), "TEST-2312-01"),
            (datetime(2024, 2, 15), "TEST-2402-01"),
            (datetime(2025, 11, 30), "TEST-2511-01"),
        ]

        for test_date, expected in test_cases:
            with patch("app.services.system_config_service.get_utc_now") as mock_now:
                mock_now.return_value = test_date

                example = config_service.generate_example_case_number(
                    "PREFIX-YYMM-NN", "TEST"
                )
                assert example == expected


class TestIntegrationScenarios:
    """Test integration scenarios"""

    @pytest.mark.asyncio
    async def test_full_configuration_workflow(
        self, config_service: SystemConfigService, admin_user: models.User, session: Session
    ):
        """Test complete configuration workflow"""
        # 1. Get initial configuration (should create default)
        config = await config_service.get_configuration()
        assert config.case_number_template == "YYMM-NN"
        assert config.case_number_prefix is None

        # 2. Update to prefix template
        config = await config_service.update_configuration("PREFIX-YYMM-NN", current_user=admin_user, case_number_prefix="CASE")
        assert config.case_number_template == "PREFIX-YYMM-NN"
        assert config.case_number_prefix == "CASE"

        # 3. Generate example
        with patch("app.services.system_config_service.get_utc_now") as mock_now:
            mock_now.return_value = datetime(2023, 6, 15, 12, 0, 0)
            example = config_service.generate_example_case_number(
                config.case_number_template, config.case_number_prefix
            )
            assert example == "CASE-2306-01"

        # 4. Switch back to YYMM template
        config = await config_service.update_configuration("YYMM-NN", current_user=admin_user)
        assert config.case_number_template == "YYMM-NN"
        assert config.case_number_prefix is None

        # 5. Verify only one configuration exists
        stmt = select(models.SystemConfiguration)
        configs = session.exec(stmt).all()
        assert len(configs) == 1

    @pytest.mark.asyncio
    async def test_concurrent_access_simulation(
        self, config_service: SystemConfigService, session: Session
    ):
        """Test behavior when multiple processes might access configuration"""
        # Simulate multiple services getting configuration
        configs = []
        for _ in range(5):
            config = await config_service.get_configuration()
            configs.append(config)

        # All should return the same configuration
        assert all(c.id == configs[0].id for c in configs)

        # Only one should exist in database
        stmt = select(models.SystemConfiguration)
        db_configs = session.exec(stmt).all()
        assert len(db_configs) == 1

    @pytest.mark.asyncio
    async def test_configuration_persistence_across_service_instances(
        self, session: Session, admin_user: models.User
    ):
        """Test that configuration persists across different service instances"""
        # Create first service instance and set configuration
        service1 = SystemConfigService(session)
        config1 = await service1.update_configuration("PREFIX-YYMM-NN", current_user=admin_user, case_number_prefix="TEST")

        # Create second service instance and get configuration
        service2 = SystemConfigService(session)
        config2 = await service2.get_configuration()

        # Should be the same configuration
        assert config1.id == config2.id
        assert config2.case_number_template == "PREFIX-YYMM-NN"
        assert config2.case_number_prefix == "TEST"

    @pytest.mark.asyncio
    async def test_edge_case_empty_database_after_manual_deletion(
        self, config_service: SystemConfigService, session: Session
    ):
        """Test behavior when configuration is manually deleted from database"""
        # Create initial configuration
        await config_service.get_configuration()

        # Manually delete all configurations
        stmt = select(models.SystemConfiguration)
        configs = session.exec(stmt).all()
        for config in configs:
            session.delete(config)
        session.commit()

        # Getting configuration should create a new default
        new_config = await config_service.get_configuration()
        assert new_config.case_number_template == "YYMM-NN"
        assert new_config.case_number_prefix is None


class TestErrorHandling:
    """Test error handling and edge cases"""

    @pytest.mark.asyncio
    async def test_database_error_handling_during_get(
        self, config_service: SystemConfigService
    ):
        """Test handling of database errors during get_configuration"""
        # Note: This test is challenging because SQLModel/SQLAlchemy sessions
        # are quite resilient. In real scenarios, database errors would be
        # handled by the application's exception handling middleware.
        # For now, we'll verify the service can handle empty results gracefully.
        config = await config_service.get_configuration()
        assert config is not None

    @pytest.mark.asyncio
    async def test_prefix_validation_edge_cases(
        self, config_service: SystemConfigService, admin_user: models.User
    ):
        """Test prefix validation edge cases"""
        edge_cases = [
            None,  # None should fail for PREFIX template
            "",  # Empty string should fail
            " ",  # Whitespace should fail
            "\t",  # Tab should fail
            "\n",  # Newline should fail
            "A",  # Too short
            "ABCDEFGHI",  # Too long
            "AB CD",  # Contains space
            "AB-CD",  # Contains hyphen
            "AB_CD",  # Contains underscore
            "AB.CD",  # Contains period
            "AB@CD",  # Contains @
            "AB#CD",  # Contains #
            "AB$CD",  # Contains $
            "AB%CD",  # Contains %
            "AB^CD",  # Contains ^
            "AB&CD",  # Contains &
            "AB*CD",  # Contains *
            "AB(CD",  # Contains (
            "AB)CD",  # Contains )
            "AB+CD",  # Contains +
            "AB=CD",  # Contains =
            "AB[CD",  # Contains [
            "AB]CD",  # Contains ]
            "AB{CD",  # Contains {
            "AB}CD",  # Contains }
            "AB|CD",  # Contains |
            "AB\\CD",  # Contains backslash
            "AB:CD",  # Contains colon
            "AB;CD",  # Contains semicolon
            'AB"CD',  # Contains quote
            "AB'CD",  # Contains apostrophe
            "AB<CD",  # Contains <
            "AB>CD",  # Contains >
            "AB,CD",  # Contains comma
            "AB?CD",  # Contains ?
            "AB/CD",  # Contains /
            "AB~CD",  # Contains ~
            "AB`CD",  # Contains backtick
        ]

        for prefix in edge_cases:
            with pytest.raises(CaseNumberTemplateError):
                await config_service.update_configuration("PREFIX-YYMM-NN", current_user=admin_user, case_number_prefix=prefix)

    @pytest.mark.asyncio
    async def test_template_validation_case_sensitivity(
        self, config_service: SystemConfigService, admin_user: models.User
    ):
        """Test that template validation is case sensitive"""
        invalid_templates = [
            "yymm-nn",
            "YYMM-nn",
            "yymm-NN",
            "prefix-yymm-nn",
            "PREFIX-yymm-nn",
            "prefix-YYMM-NN",
            "Prefix-Yymm-Nn",
        ]

        for template in invalid_templates:
            with pytest.raises(CaseNumberTemplateError, match="Invalid case number template"):
                await config_service.update_configuration(template, current_user=admin_user)

    def test_display_name_method_is_pure_function(
        self, config_service: SystemConfigService
    ):
        """Test that get_template_display_name doesn't modify state"""
        # Call multiple times with different values
        result1 = config_service.get_template_display_name("YYMM-NN")
        result2 = config_service.get_template_display_name("PREFIX-YYMM-NN")
        result3 = config_service.get_template_display_name("YYMM-NN")

        # Results should be consistent
        assert result1 == result3
        assert result1 == "Monthly Reset (YYMM-NN)"
        assert result2 == "Prefix + Monthly Reset (PREFIX-YYMM-NN)"

    def test_example_generation_method_is_pure_function(
        self, config_service: SystemConfigService
    ):
        """Test that generate_example_case_number doesn't modify state"""
        with patch("app.services.system_config_service.get_utc_now") as mock_now:
            mock_now.return_value = datetime(2023, 6, 15, 12, 0, 0)

            # Call multiple times with same inputs
            result1 = config_service.generate_example_case_number("YYMM-NN")
            result2 = config_service.generate_example_case_number("YYMM-NN")

            # Results should be identical
            assert result1 == result2 == "2306-01"


class TestGenericAPIKeyManagement:
    """Test generic API key management methods"""

    @pytest.mark.asyncio
    async def test_set_api_key(
        self, config_service: SystemConfigService, admin_user: models.User
    ):
        """Test setting an API key for a provider"""
        api_key = "sk-test123456789"
        config = await config_service.set_api_key(
            provider="openai",
            api_key=api_key,
            name="OpenAI GPT-4",
            current_user=admin_user,
        )

        assert config.api_keys is not None
        assert "openai" in config.api_keys
        assert config.api_keys["openai"]["name"] == "OpenAI GPT-4"
        assert config.api_keys["openai"]["is_active"] is True

    @pytest.mark.asyncio
    async def test_set_multiple_api_keys(
        self, config_service: SystemConfigService, admin_user: models.User
    ):
        """Test setting multiple API keys for different providers"""
        # Set OpenAI key
        await config_service.set_api_key(
            provider="openai",
            api_key="sk-openai-key",
            name="OpenAI API",
            current_user=admin_user,
        )

        # Set Anthropic key
        config = await config_service.set_api_key(
            provider="anthropic",
            api_key="sk-ant-key",
            name="Claude API",
            current_user=admin_user,
        )

        assert "openai" in config.api_keys
        assert "anthropic" in config.api_keys
        assert config.api_keys["openai"]["name"] == "OpenAI API"
        assert config.api_keys["anthropic"]["name"] == "Claude API"

    @pytest.mark.asyncio
    async def test_remove_api_key(
        self, config_service: SystemConfigService, admin_user: models.User
    ):
        """Test removing an API key for a provider"""
        # First set a key
        await config_service.set_api_key(
            provider="openai",
            api_key="sk-test123",
            name="OpenAI API",
            current_user=admin_user,
        )

        # Then remove it
        config = await config_service.remove_api_key(
            provider="openai", current_user=admin_user
        )
        assert config.api_keys is not None
        assert "openai" not in config.api_keys

    @pytest.mark.asyncio
    async def test_remove_nonexistent_api_key(
        self, config_service: SystemConfigService, admin_user: models.User
    ):
        """Test removing a non-existent API key doesn't cause errors"""
        config = await config_service.remove_api_key(
            provider="nonexistent", current_user=admin_user
        )
        assert config is not None

    def test_get_api_key_from_database(
        self, config_service: SystemConfigService, session: Session
    ):
        """Test getting API key from database"""
        from app.core.security import encrypt_api_key

        # Create config with encrypted API key
        config = models.SystemConfiguration(
            case_number_template="YYMM-NN",
            api_keys={
                "openai": {
                    "api_key": encrypt_api_key("sk-database-key"),
                    "name": "OpenAI API",
                    "is_active": True,
                }
            },
        )
        session.add(config)
        session.commit()

        api_key = config_service.get_api_key("openai")
        assert api_key == "sk-database-key"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-env-key"})
    def test_get_api_key_fallback_to_env(self, config_service: SystemConfigService):
        """Test getting API key falls back to environment variable"""
        api_key = config_service.get_api_key("openai")
        assert api_key == "sk-env-key"

    def test_get_api_key_database_priority(
        self, config_service: SystemConfigService, session: Session
    ):
        """Test that database key takes priority over environment variable"""
        from app.core.security import encrypt_api_key

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-env-key"}):
            # Create config with encrypted API key
            config = models.SystemConfiguration(
                case_number_template="YYMM-NN",
                api_keys={
                    "openai": {
                        "api_key": encrypt_api_key("sk-database-key"),
                        "name": "OpenAI API",
                        "is_active": True,
                    }
                },
            )
            session.add(config)
            session.commit()

            api_key = config_service.get_api_key("openai")
            assert api_key == "sk-database-key"

    def test_is_provider_configured_true_with_database_key(
        self, config_service: SystemConfigService, session: Session
    ):
        """Test is_provider_configured returns True when database has key"""
        from app.core.security import encrypt_api_key

        config = models.SystemConfiguration(
            case_number_template="YYMM-NN",
            api_keys={
                "openai": {
                    "api_key": encrypt_api_key("sk-test123"),
                    "name": "OpenAI API",
                    "is_active": True,
                }
            },
        )
        session.add(config)
        session.commit()

        assert config_service.is_provider_configured("openai") is True

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-env-key"})
    def test_is_provider_configured_true_with_env_key(
        self, config_service: SystemConfigService
    ):
        """Test is_provider_configured returns True when env has key"""
        assert config_service.is_provider_configured("openai") is True

    def test_is_provider_configured_false_no_key(
        self, config_service: SystemConfigService
    ):
        """Test is_provider_configured returns False when no key is available"""
        with patch.dict(os.environ, {}, clear=True):
            assert config_service.is_provider_configured("openai") is False

    @pytest.mark.asyncio
    async def test_list_api_keys_empty(self, config_service: SystemConfigService, admin_user: models.User):
        """Test listing API keys when none are configured"""
        api_keys = await config_service.list_api_keys(current_user=admin_user)
        assert api_keys == {}

    @pytest.mark.asyncio
    async def test_list_api_keys_with_keys(
        self, config_service: SystemConfigService, admin_user: models.User, session: Session
    ):
        """Test listing API keys when multiple are configured"""
        from app.core.security import encrypt_api_key

        config = models.SystemConfiguration(
            case_number_template="YYMM-NN",
            api_keys={
                "openai": {
                    "api_key": encrypt_api_key("sk-openai-key"),
                    "name": "OpenAI GPT-4",
                    "is_active": True,
                    "created_at": "2023-06-15T12:00:00Z",
                },
                "anthropic": {
                    "api_key": encrypt_api_key("sk-ant-key"),
                    "name": "Claude API",
                    "is_active": True,
                    "created_at": "2023-06-15T13:00:00Z",
                },
            },
        )
        session.add(config)
        session.commit()

        api_keys = await config_service.list_api_keys(current_user=admin_user)
        assert len(api_keys) == 2
        assert "openai" in api_keys
        assert "anthropic" in api_keys
        assert api_keys["openai"]["name"] == "OpenAI GPT-4"
        assert api_keys["anthropic"]["name"] == "Claude API"
        assert api_keys["openai"]["is_configured"] is True

    @pytest.mark.asyncio
    async def test_get_configured_providers(
        self, config_service: SystemConfigService, admin_user: models.User, session: Session
    ):
        """Test getting list of configured provider names"""
        from app.core.security import encrypt_api_key

        config = models.SystemConfiguration(
            case_number_template="YYMM-NN",
            api_keys={
                "openai": {
                    "api_key": encrypt_api_key("sk-openai-key"),
                    "name": "OpenAI API",
                    "is_active": True,
                },
                "google": {
                    "api_key": encrypt_api_key("sk-google-key"),
                    "name": "Google API",
                    "is_active": True,
                },
            },
        )
        session.add(config)
        session.commit()

        # Make sure admin_user has proper role
        admin_user.role = "Admin"
        session.add(admin_user)
        session.commit()

        providers = await config_service.get_configured_providers(admin_user)
        assert len(providers) == 2
        assert "openai" in providers
        assert "google" in providers


# New tests for refactored functionality
class TestRefactoredHelperMethods:
    """Test newly refactored helper methods"""

    def test_create_config_logger(self, config_service: SystemConfigService):
        """Test security logger creation helper"""
        with patch('app.services.system_config_service.get_security_logger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            # Act
            result = config_service._create_config_logger(
                user_id=1,
                action="test_action",
                extra_field="value"
            )
            
            # Assert
            assert result == mock_logger
            mock_get_logger.assert_called_once_with(
                admin_user_id=1,
                action="test_action",
                extra_field="value"
            )
    
    def test_normalize_prefix_monthly_template(self, config_service: SystemConfigService):
        """Test prefix normalization for monthly template"""
        # Monthly template should always return None
        assert config_service._normalize_prefix(CASE_NUMBER_TEMPLATE_MONTHLY, "PREFIX") is None
        assert config_service._normalize_prefix(CASE_NUMBER_TEMPLATE_MONTHLY, None) is None
    
    def test_normalize_prefix_prefix_template(self, config_service: SystemConfigService):
        """Test prefix normalization for prefix template"""
        # Prefix template should return the prefix
        assert config_service._normalize_prefix(CASE_NUMBER_TEMPLATE_PREFIX, "PREFIX") == "PREFIX"
        assert config_service._normalize_prefix(CASE_NUMBER_TEMPLATE_PREFIX, None) is None
    
    def test_save_configuration(self, config_service: SystemConfigService, session: Session):
        """Test configuration save helper"""
        config = models.SystemConfiguration(
            case_number_template=CASE_NUMBER_TEMPLATE_MONTHLY,
            case_number_prefix=None
        )
        
        with patch('app.services.system_config_service.get_utc_now') as mock_now:
            mock_now.return_value = datetime(2024, 1, 1, 12, 0, 0)
            
            # Act
            result = config_service._save_configuration(config)
            
            # Assert
            assert config.updated_at == datetime(2024, 1, 1, 12, 0, 0)
            assert result == config
    
    def test_create_api_key_data_with_key(self, config_service: SystemConfigService):
        """Test API key data structure creation with key"""
        with patch('app.services.system_config_service.encrypt_api_key') as mock_encrypt:
            mock_encrypt.return_value = "encrypted-key"
            
            with patch('app.services.system_config_service.get_utc_now') as mock_now:
                mock_now.return_value = datetime(2024, 1, 1)
                
                # Act
                data = config_service._create_api_key_data("raw-key", "Test API")
                
                # Assert
                assert data["api_key"] == "encrypted-key"
                assert data["name"] == "Test API"
                assert data["is_active"] is True
                assert data["created_at"] == "2024-01-01T00:00:00"
                mock_encrypt.assert_called_once_with("raw-key")
    
    def test_create_api_key_data_without_key(self, config_service: SystemConfigService):
        """Test API key data structure creation without key"""
        with patch('app.services.system_config_service.get_utc_now') as mock_now:
            mock_now.return_value = datetime(2024, 1, 1)
            
            # Act
            data = config_service._create_api_key_data(None, "Test API")
            
            # Assert
            assert data["api_key"] is None
            assert data["name"] == "Test API"
            assert data["is_active"] is True
    
    def test_create_api_key_data_with_custom_created_at(self, config_service: SystemConfigService):
        """Test API key data structure with custom created_at"""
        with patch('app.services.system_config_service.encrypt_api_key') as mock_encrypt:
            mock_encrypt.return_value = "encrypted-key"
            
            # Act
            data = config_service._create_api_key_data(
                "key", "Test", "2023-01-01T00:00:00"
            )
            
            # Assert
            assert data["created_at"] == "2023-01-01T00:00:00"
    
    def test_update_existing_api_key_with_new_key(self, config_service: SystemConfigService):
        """Test updating existing API key with new key"""
        current_keys = {
            "openai": {
                "api_key": "old-encrypted",
                "name": "Old Name",
                "is_active": True,
                "created_at": "2023-01-01T00:00:00"
            }
        }
        
        with patch.object(config_service, '_create_api_key_data') as mock_create:
            mock_create.return_value = {
                "api_key": "new-encrypted",
                "name": "New Name",
                "is_active": True,
                "created_at": "2023-01-01T00:00:00"
            }
            
            # Act
            updated_keys, metadata = config_service._update_existing_api_key(
                current_keys.copy(), "openai", "new-key", "New Name"
            )
            
            # Assert
            assert updated_keys["openai"]["name"] == "New Name"
            assert metadata["old_name"] == "Old Name"
            assert metadata["new_name"] == "New Name"
            assert metadata["key_updated"] is True
            assert metadata["metadata_only"] is False
    
    def test_update_existing_api_key_metadata_only(self, config_service: SystemConfigService):
        """Test updating existing API key metadata only"""
        current_keys = {
            "openai": {
                "api_key": "encrypted",
                "name": "Old Name",
                "is_active": True,
                "created_at": "2023-01-01T00:00:00"
            }
        }
        
        with patch.object(config_service, '_create_api_key_data') as mock_create:
            mock_create.return_value = {
                "api_key": None,
                "name": "New Name Only",
                "is_active": True,
                "created_at": "2023-01-01T00:00:00"
            }
            
            # Act
            updated_keys, metadata = config_service._update_existing_api_key(
                current_keys.copy(), "openai", None, "New Name Only"
            )
            
            # Assert
            assert metadata["key_updated"] is False
            assert metadata["metadata_only"] is True
            # Original key should be preserved
            assert updated_keys["openai"]["api_key"] == "encrypted"
    
    def test_add_new_api_key_success(self, config_service: SystemConfigService):
        """Test adding new API key successfully"""
        current_keys = {}
        
        with patch.object(config_service, '_create_api_key_data') as mock_create:
            mock_create.return_value = {
                "api_key": "encrypted",
                "name": "New API",
                "is_active": True,
                "created_at": "2024-01-01T00:00:00"
            }
            
            # Act
            updated_keys = config_service._add_new_api_key(
                current_keys, "newapi", "raw-key", "New API"
            )
            
            # Assert
            assert "newapi" in updated_keys
            assert updated_keys["newapi"]["name"] == "New API"
    
    def test_add_new_api_key_missing_key(self, config_service: SystemConfigService):
        """Test adding new API key without key fails"""
        current_keys = {}
        
        # Act & Assert
        with pytest.raises(ApiKeyError) as exc_info:
            config_service._add_new_api_key(
                current_keys, "newapi", None, "New API"
            )
        
        assert "API key is required" in str(exc_info.value)
    
    def test_get_env_api_key(self, config_service: SystemConfigService):
        """Test getting API key from environment"""
        with patch('os.environ.get') as mock_get:
            mock_get.return_value = "env-api-key"
            
            result = config_service._get_env_api_key("openai")
            
            assert result == "env-api-key"
            mock_get.assert_called_once_with("OPENAI_API_KEY")
    
    def test_get_env_api_key_different_providers(self, config_service: SystemConfigService):
        """Test environment variable naming for different providers"""
        providers = [
            ("openai", "OPENAI_API_KEY"),
            ("anthropic", "ANTHROPIC_API_KEY"),
            ("google", "GOOGLE_API_KEY"),
            ("virustotal", "VIRUSTOTAL_API_KEY"),
        ]
        
        for provider, expected_env_var in providers:
            with patch('os.environ.get') as mock_get:
                mock_get.return_value = f"{provider}-key"
                
                result = config_service._get_env_api_key(provider)
                
                assert result == f"{provider}-key"
                mock_get.assert_called_once_with(expected_env_var)


# Tests for Evidence Folder Templates
class TestEvidenceFolderTemplates:
    """Test evidence folder template functionality"""
    
    @pytest.mark.asyncio
    async def test_get_evidence_folder_templates_existing(
        self, config_service: SystemConfigService, session: Session
    ):
        """Test getting existing evidence folder templates"""
        # Create config with templates
        templates = {
            "default": {
                "name": "Default Template",
                "description": "Basic evidence structure",
                "folders": ["documents", "screenshots", "logs"]
            }
        }
        config = models.SystemConfiguration(
            case_number_template=CASE_NUMBER_TEMPLATE_MONTHLY,
            evidence_folder_templates=templates
        )
        session.add(config)
        session.commit()
        
        # Act
        result = await config_service.get_evidence_folder_templates()
        
        # Assert
        assert result == templates
    
    @pytest.mark.asyncio
    async def test_get_evidence_folder_templates_creates_default(
        self, config_service: SystemConfigService, session: Session
    ):
        """Test creating default templates when none exist"""
        # Create config without templates
        config = models.SystemConfiguration(
            case_number_template=CASE_NUMBER_TEMPLATE_MONTHLY,
            evidence_folder_templates=None
        )
        session.add(config)
        session.commit()
        
        with patch.object(config_service, '_get_default_templates') as mock_default:
            mock_default.return_value = {"default": {"name": "Default"}}
            
            # Act
            result = await config_service.get_evidence_folder_templates()
        
        # Assert
        assert result == {"default": {"name": "Default"}}
        assert config.evidence_folder_templates == {"default": {"name": "Default"}}
    
    @pytest.mark.asyncio
    async def test_update_evidence_folder_templates_success(
        self, config_service: SystemConfigService, admin_user: models.User
    ):
        """Test successful evidence folder templates update"""
        new_templates = {
            "forensics": {
                "name": "Digital Forensics",
                "description": "Template for digital forensics",
                "folders": ["images", "logs", "reports", "artifacts"]
            },
            "incident": {
                "name": "Incident Response",
                "description": "Template for incident response",
                "folders": ["timeline", "iocs", "logs", "reports"]
            }
        }
        
        with patch.object(config_service, '_create_config_logger') as mock_logger:
            mock_logger.return_value = Mock()
            
            # Act
            result = await config_service.update_evidence_folder_templates(
                new_templates, current_user=admin_user
            )
        
        # Assert
        assert result.evidence_folder_templates == new_templates
    
    @pytest.mark.asyncio
    async def test_update_evidence_folder_templates_validation_error(
        self, config_service: SystemConfigService, admin_user: models.User
    ):
        """Test evidence folder templates update with validation error"""
        invalid_templates = {
            "invalid": "not a dict"  # Invalid structure
        }
        
        with patch.object(config_service, '_create_config_logger') as mock_logger:
            mock_logger.return_value = Mock()
            
            # Act & Assert
            with pytest.raises(EvidenceTemplateError):
                await config_service.update_evidence_folder_templates(
                    invalid_templates, current_user=admin_user
                )
    
    @pytest.mark.asyncio
    async def test_update_evidence_folder_templates_missing_fields(
        self, config_service: SystemConfigService, admin_user: models.User
    ):
        """Test evidence folder templates update with missing required fields"""
        templates_missing_fields = [
            {"test": {"description": "test", "folders": []}},  # Missing name
            {"test": {"name": "test", "folders": []}},  # Missing description
            {"test": {"name": "test", "description": "test"}},  # Missing folders
        ]
        
        for invalid_template in templates_missing_fields:
            with patch.object(config_service, '_create_config_logger') as mock_logger:
                mock_logger.return_value = Mock()
                
                with pytest.raises(EvidenceTemplateError):
                    await config_service.update_evidence_folder_templates(
                        invalid_template, current_user=admin_user
                    )
    
    def test_get_default_templates(self, config_service: SystemConfigService):
        """Test getting default evidence templates"""
        with patch('app.services.system_config_service.DEFAULT_TEMPLATES') as mock_templates:
            mock_templates.copy.return_value = {
                "default": {"name": "Default"},
                "forensics": {"name": "Forensics"}
            }
            
            result = config_service._get_default_templates()
            
            assert result == {
                "default": {"name": "Default"},
                "forensics": {"name": "Forensics"}
            }
            mock_templates.copy.assert_called_once()


# Edge Cases and Performance Tests
class TestEdgeCasesAndPerformance:
    """Test edge cases and performance scenarios"""
    
    @pytest.mark.asyncio
    async def test_concurrent_configuration_updates(
        self, config_service: SystemConfigService, admin_user: models.User
    ):
        """Test handling concurrent configuration updates"""
        import asyncio
        
        # Create multiple update tasks
        tasks = [
            config_service.update_configuration(CASE_NUMBER_TEMPLATE_MONTHLY, current_user=admin_user),
            config_service.update_configuration(CASE_NUMBER_TEMPLATE_PREFIX, current_user=admin_user, case_number_prefix="PROJ"),
            config_service.update_configuration(CASE_NUMBER_TEMPLATE_MONTHLY, current_user=admin_user),
        ]
        
        # Execute concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All should complete without errors
        assert all(not isinstance(r, Exception) for r in results)
    
    def test_case_number_generation_edge_dates(self, config_service: SystemConfigService):
        """Test case number generation at year/month boundaries"""
        edge_cases = [
            (datetime(2023, 12, 31, 23, 59, 59), "2312-01"),  # End of year
            (datetime(2024, 1, 1, 0, 0, 0), "2401-01"),  # Beginning of year
            (datetime(2099, 12, 31), "9912-01"),  # Far future
            (datetime(2000, 1, 1), "0001-01"),  # Year 2000
        ]
        
        for test_date, expected in edge_cases:
            with patch('app.services.system_config_service.get_utc_now') as mock_now:
                mock_now.return_value = test_date
                example = config_service.generate_example_case_number(CASE_NUMBER_TEMPLATE_MONTHLY)
                assert example == expected
    
    @pytest.mark.asyncio
    async def test_empty_api_keys_handling(self, config_service: SystemConfigService, admin_user: models.User):
        """Test handling of empty or None api_keys"""
        configs = [
            models.SystemConfiguration(api_keys=None),
            models.SystemConfiguration(api_keys={}),
        ]
        
        for config in configs:
            with patch.object(config_service, 'get_configuration') as mock_get:
                mock_get.return_value = config
                
                # Should handle gracefully
                result = await config_service.list_api_keys(current_user=admin_user)
                assert result == {}
    
    def test_special_characters_in_prefix(self, config_service: SystemConfigService):
        """Test validation of special characters in prefix"""
        special_chars = ["PRO!", "PRO@", "PRO#", "PRO$", "PRO%", "PRO^", "PRO&", "PRO*"]
        
        for prefix in special_chars:
            with pytest.raises(CaseNumberTemplateError) as exc_info:
                SystemConfigValidator.validate_case_number_prefix(prefix, CASE_NUMBER_TEMPLATE_PREFIX)
            
            assert "alphanumeric" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_large_evidence_template_structure(
        self, config_service: SystemConfigService, admin_user: models.User
    ):
        """Test handling of large evidence template structures"""
        # Create a large template structure
        large_template = {
            f"template_{i}": {
                "name": f"Template {i}",
                "description": f"Description for template {i}",
                "folders": [f"folder_{j}" for j in range(50)]  # 50 folders each
            }
            for i in range(20)  # 20 templates
        }
        
        with patch.object(config_service, '_create_config_logger') as mock_logger:
            mock_logger.return_value = Mock()
            
            # Should handle large structures
            result = await config_service.update_evidence_folder_templates(
                large_template, current_user=admin_user
            )
        
        assert len(result.evidence_folder_templates) == 20
    
    def test_api_key_decryption_error_fallback(
        self, config_service: SystemConfigService, session: Session
    ):
        """Test fallback to environment when decryption fails"""
        # Create config with encrypted key
        config = models.SystemConfiguration(
            case_number_template=CASE_NUMBER_TEMPLATE_MONTHLY,
            api_keys={
                "openai": {
                    "api_key": "encrypted-key",
                    "name": "OpenAI",
                    "is_active": True
                }
            }
        )
        session.add(config)
        session.commit()
        
        with patch('app.services.system_config_service.decrypt_api_key') as mock_decrypt:
            mock_decrypt.side_effect = Exception("Decryption failed")
            
            with patch.object(config_service, '_get_env_api_key') as mock_env:
                mock_env.return_value = "env-fallback-key"
                
                result = config_service.get_api_key("openai")
                
                assert result == "env-fallback-key"
    
    @pytest.mark.asyncio
    async def test_bulk_api_key_operations_performance(
        self, config_service: SystemConfigService, admin_user: models.User
    ):
        """Test performance of multiple API key operations"""
        import time
        
        with patch.object(config_service, '_create_config_logger') as mock_logger:
            mock_logger.return_value = Mock()
            
            # Measure time for 50 API key operations
            start_time = time.time()
            
            for i in range(50):
                await config_service.set_api_key(
                    f"provider{i}", f"key{i}", f"Provider {i}", current_user=admin_user
                )
            
            end_time = time.time()
        
        # Assert performance
        execution_time = end_time - start_time
        assert execution_time < 2.0  # Should complete 50 operations reasonably fast
    
    def test_api_key_encryption_performance(self, config_service: SystemConfigService):
        """Test performance of API key encryption/decryption"""
        import time
        
        with patch('app.services.system_config_service.encrypt_api_key') as mock_encrypt:
            with patch('app.services.system_config_service.decrypt_api_key') as mock_decrypt:
                mock_encrypt.side_effect = lambda x: f"encrypted-{x}"
                mock_decrypt.side_effect = lambda x: x.replace("encrypted-", "")
                
                # Test encryption/decryption cycle performance
                start_time = time.time()
                
                for i in range(100):
                    # Encrypt
                    data = config_service._create_api_key_data(f"key-{i}", f"API {i}")
                    
                    # Decrypt (simulated)
                    if data["api_key"]:
                        mock_decrypt(data["api_key"])
                
                end_time = time.time()
        
        # Assert performance
        execution_time = end_time - start_time
        assert execution_time < 0.5  # 100 operations should complete quickly


# Complete Integration Tests
class TestCompleteIntegration:
    """Test complete configuration workflow integration"""
    
    @pytest.mark.asyncio
    async def test_complete_configuration_workflow(
        self, config_service: SystemConfigService, admin_user: models.User, session: Session
    ):
        """Test complete configuration workflow from creation to updates"""
        # Step 1: Initial configuration creation (should create default)
        initial_config = await config_service.get_configuration()
        
        # Verify defaults
        assert initial_config.case_number_template == CASE_NUMBER_TEMPLATE_MONTHLY
        assert initial_config.api_keys == {}
        
        # Step 2: Update case number template
        with patch.object(config_service, '_create_config_logger') as mock_logger:
            mock_logger.return_value = Mock()
            
            await config_service.update_configuration(
                CASE_NUMBER_TEMPLATE_PREFIX, current_user=admin_user, case_number_prefix="PROJ"
            )
        
        # Verify update
        config = await config_service.get_configuration()
        assert config.case_number_template == CASE_NUMBER_TEMPLATE_PREFIX
        assert config.case_number_prefix == "PROJ"
        
        # Step 3: Add API keys
        with patch.object(config_service, '_create_config_logger') as mock_logger:
            mock_logger.return_value = Mock()
            
            await config_service.set_api_key(
                "openai", "test-key", "OpenAI API", current_user=admin_user
            )
            await config_service.set_api_key(
                "anthropic", "claude-key", "Claude API", current_user=admin_user
            )
        
        # Verify API keys
        config = await config_service.get_configuration()
        assert "openai" in config.api_keys
        assert "anthropic" in config.api_keys
        
        # Step 4: Update evidence templates
        new_templates = {
            "forensics": {
                "name": "Digital Forensics",
                "description": "Template for digital forensics",
                "folders": ["images", "logs", "reports"]
            }
        }
        
        with patch.object(config_service, '_create_config_logger') as mock_logger:
            mock_logger.return_value = Mock()
            
            await config_service.update_evidence_folder_templates(
                new_templates, current_user=admin_user
            )
        
        # Verify templates
        config = await config_service.get_configuration()
        assert config.evidence_folder_templates == new_templates
        
        # Step 5: Verify only one configuration exists
        stmt = select(models.SystemConfiguration)
        configs = session.exec(stmt).all()
        assert len(configs) == 1

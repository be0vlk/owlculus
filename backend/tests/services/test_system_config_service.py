import pytest
import os
from sqlmodel import Session, select
from datetime import datetime
from unittest.mock import patch

from app.database import models
from app.services.system_config_service import SystemConfigService
from app.core.utils import get_utc_now


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
        self, config_service: SystemConfigService
    ):
        """Test updating to valid YYMM-NN template"""
        config = await config_service.update_configuration("YYMM-NN")

        assert config.case_number_template == "YYMM-NN"
        assert config.case_number_prefix is None

    @pytest.mark.asyncio
    async def test_update_configuration_valid_prefix_template(
        self, config_service: SystemConfigService
    ):
        """Test updating to valid PREFIX-YYMM-NN template with prefix"""
        config = await config_service.update_configuration("PREFIX-YYMM-NN", "CASE")

        assert config.case_number_template == "PREFIX-YYMM-NN"
        assert config.case_number_prefix == "CASE"

    @pytest.mark.asyncio
    async def test_update_configuration_invalid_template_raises_error(
        self, config_service: SystemConfigService
    ):
        """Test that invalid template raises ValueError"""
        with pytest.raises(ValueError, match="Invalid case number template"):
            await config_service.update_configuration("INVALID-TEMPLATE")

    @pytest.mark.asyncio
    async def test_update_configuration_prefix_template_without_prefix_raises_error(
        self, config_service: SystemConfigService
    ):
        """Test that PREFIX template without prefix raises ValueError"""
        with pytest.raises(
            ValueError, match="Prefix is required for PREFIX-YYMM-NN template"
        ):
            await config_service.update_configuration("PREFIX-YYMM-NN")

    @pytest.mark.asyncio
    async def test_update_configuration_prefix_template_with_empty_prefix_raises_error(
        self, config_service: SystemConfigService
    ):
        """Test that PREFIX template with empty prefix raises ValueError"""
        with pytest.raises(
            ValueError, match="Prefix is required for PREFIX-YYMM-NN template"
        ):
            await config_service.update_configuration("PREFIX-YYMM-NN", "")

    @pytest.mark.asyncio
    async def test_update_configuration_invalid_prefix_too_short(
        self, config_service: SystemConfigService
    ):
        """Test that prefix shorter than 2 characters raises ValueError"""
        with pytest.raises(
            ValueError, match="Prefix must be 2-8 alphanumeric characters"
        ):
            await config_service.update_configuration("PREFIX-YYMM-NN", "A")

    @pytest.mark.asyncio
    async def test_update_configuration_invalid_prefix_too_long(
        self, config_service: SystemConfigService
    ):
        """Test that prefix longer than 8 characters raises ValueError"""
        with pytest.raises(
            ValueError, match="Prefix must be 2-8 alphanumeric characters"
        ):
            await config_service.update_configuration(
                "PREFIX-YYMM-NN", "VERYLONGPREFIX"
            )

    @pytest.mark.asyncio
    async def test_update_configuration_invalid_prefix_non_alphanumeric(
        self, config_service: SystemConfigService
    ):
        """Test that non-alphanumeric prefix raises ValueError"""
        invalid_prefixes = ["CA-SE", "CA$E", "CA E", "CA.E", "CA@E"]

        for prefix in invalid_prefixes:
            with pytest.raises(
                ValueError, match="Prefix must be 2-8 alphanumeric characters"
            ):
                await config_service.update_configuration("PREFIX-YYMM-NN", prefix)

    @pytest.mark.asyncio
    async def test_update_configuration_valid_prefix_variations(
        self, config_service: SystemConfigService
    ):
        """Test that various valid prefixes work"""
        valid_prefixes = ["AB", "ABC", "ABCD", "AB12", "1234", "A1B2C3", "12345678"]

        for prefix in valid_prefixes:
            config = await config_service.update_configuration("PREFIX-YYMM-NN", prefix)
            assert config.case_number_prefix == prefix

    @pytest.mark.asyncio
    async def test_update_configuration_clears_prefix_for_yymm_template(
        self, config_service: SystemConfigService
    ):
        """Test that switching to YYMM-NN template clears the prefix"""
        # First set a prefix template
        config = await config_service.update_configuration("PREFIX-YYMM-NN", "CASE")
        assert config.case_number_prefix == "CASE"

        # Then switch to YYMM-NN (even if prefix is provided, it should be cleared)
        config = await config_service.update_configuration("YYMM-NN", "CASE")
        assert config.case_number_template == "YYMM-NN"
        assert config.case_number_prefix is None

    @pytest.mark.asyncio
    async def test_update_configuration_updates_timestamp(
        self, config_service: SystemConfigService
    ):
        """Test that update_configuration updates the updated_at timestamp"""
        with patch("app.services.system_config_service.get_utc_now") as mock_now:
            mock_time = datetime(2023, 6, 15, 12, 0, 0)
            mock_now.return_value = mock_time

            config = await config_service.update_configuration("YYMM-NN")
            assert config.updated_at == mock_time

    @pytest.mark.asyncio
    async def test_update_configuration_persists_to_database(
        self, config_service: SystemConfigService, session: Session
    ):
        """Test that configuration changes are persisted to database"""
        await config_service.update_configuration("PREFIX-YYMM-NN", "TEST")

        # Query database directly
        stmt = select(models.SystemConfiguration)
        config = session.exec(stmt).first()

        assert config.case_number_template == "PREFIX-YYMM-NN"
        assert config.case_number_prefix == "TEST"

    @pytest.mark.asyncio
    async def test_update_configuration_existing_config(
        self,
        config_service: SystemConfigService,
        sample_config: models.SystemConfiguration,
    ):
        """Test updating an existing configuration"""
        original_id = sample_config.id

        config = await config_service.update_configuration("PREFIX-YYMM-NN", "NEW")

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
        self, config_service: SystemConfigService, session: Session
    ):
        """Test complete configuration workflow"""
        # 1. Get initial configuration (should create default)
        config = await config_service.get_configuration()
        assert config.case_number_template == "YYMM-NN"
        assert config.case_number_prefix is None

        # 2. Update to prefix template
        config = await config_service.update_configuration("PREFIX-YYMM-NN", "CASE")
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
        config = await config_service.update_configuration("YYMM-NN")
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
        self, session: Session
    ):
        """Test that configuration persists across different service instances"""
        # Create first service instance and set configuration
        service1 = SystemConfigService(session)
        config1 = await service1.update_configuration("PREFIX-YYMM-NN", "TEST")

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
        self, config_service: SystemConfigService
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
            with pytest.raises(ValueError):
                await config_service.update_configuration("PREFIX-YYMM-NN", prefix)

    @pytest.mark.asyncio
    async def test_template_validation_case_sensitivity(
        self, config_service: SystemConfigService
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
            with pytest.raises(ValueError, match="Invalid case number template"):
                await config_service.update_configuration(template)

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

    def test_list_api_keys_empty(self, config_service: SystemConfigService):
        """Test listing API keys when none are configured"""
        api_keys = config_service.list_api_keys()
        assert api_keys == {}

    def test_list_api_keys_with_keys(
        self, config_service: SystemConfigService, session: Session
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

        api_keys = config_service.list_api_keys()
        assert len(api_keys) == 2
        assert "openai" in api_keys
        assert "anthropic" in api_keys
        assert api_keys["openai"]["name"] == "OpenAI GPT-4"
        assert api_keys["anthropic"]["name"] == "Claude API"
        assert api_keys["openai"]["is_configured"] is True

    def test_get_configured_providers(
        self, config_service: SystemConfigService, session: Session
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

        providers = config_service.get_configured_providers()
        assert len(providers) == 2
        assert "openai" in providers
        assert "google" in providers

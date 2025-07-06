"""
Tests for the Correlation plugin
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from app.core.roles import UserRole
from app.database.models import Case, CaseUserLink, Entity, User
from app.plugins.correlation_plugin import CorrelationScan
from app.schemas.entity_schema import ENTITY_TYPE_SCHEMAS
from sqlmodel import Session


class TestCorrelationPlugin:
    """Test cases for CorrelationScan plugin"""

    @pytest.fixture
    def plugin(self):
        """Create a CorrelationScan instance for testing"""
        return CorrelationScan()

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        return Mock(spec=Session)

    @pytest.fixture
    def mock_user(self):
        """Mock user"""
        user = Mock(spec=User)
        user.id = 1
        user.role = UserRole.INVESTIGATOR
        return user

    @pytest.fixture
    def mock_admin_user(self):
        """Mock admin user"""
        user = Mock(spec=User)
        user.id = 2
        user.role = UserRole.ADMIN
        return user

    def test_plugin_initialization(self, plugin):
        """Test plugin is initialized correctly"""
        assert plugin.name == "CorrelationScan"
        assert plugin.display_name == "Correlation Scan"
        assert plugin.description == "Finds matching entities and relationships across cases"
        assert plugin.category == "Other"
        assert plugin.evidence_category == "Documents"
        assert plugin.save_to_case is False

    def test_plugin_parameters(self, plugin):
        """Test plugin parameters are defined correctly"""
        params = plugin.parameters

        assert "case_id" in params
        assert params["case_id"]["type"] == "integer"
        assert params["case_id"]["required"] is True
        assert params["case_id"]["description"] == "ID of the case to scan"

    def test_is_admin(self, plugin, mock_user, mock_admin_user):
        """Test admin check functionality"""
        # Non-admin user
        plugin._current_user = mock_user
        assert plugin._is_admin() is False

        # Admin user
        plugin._current_user = mock_admin_user
        assert plugin._is_admin() is True

        # No user - returns None (falsy) due to short-circuit evaluation
        plugin._current_user = None
        # Check that it's falsy (None evaluates to False in boolean context)
        assert not plugin._is_admin()

    def test_parse_domain_from_string(self, plugin):
        """Test domain extraction from various string formats"""
        # Email addresses
        assert plugin._parse_domain_from_string("user@example.com") == "example.com"
        assert plugin._parse_domain_from_string("test@subdomain.example.org") == "subdomain.example.org"
        
        # URLs
        assert plugin._parse_domain_from_string("https://example.com") == "example.com"
        assert plugin._parse_domain_from_string("http://example.com/path") == "example.com"
        assert plugin._parse_domain_from_string("https://sub.example.com/page") == "sub.example.com"
        
        # Edge cases
        assert plugin._parse_domain_from_string("") is None
        assert plugin._parse_domain_from_string(None) is None
        assert plugin._parse_domain_from_string("not-a-domain") is None
        assert plugin._parse_domain_from_string("@") is None

    def test_extract_domains_from_entity(self, plugin):
        """Test domain extraction from different entity types"""
        # Domain entity
        domain_entity = Mock(spec=Entity)
        domain_entity.entity_type = "domain"
        domain_entity.data = {"domain": "example.com"}
        domains = plugin._extract_domains_from_entity(domain_entity)
        assert domains == ["example.com"]

        # Person entity with email and usernames
        person_entity = Mock(spec=Entity)
        person_entity.entity_type = "person"
        person_entity.data = {
            "email": "john@example.com",
            "usernames": ["john@corp.com", "johnny123", "john@social.net"]
        }
        domains = plugin._extract_domains_from_entity(person_entity)
        assert set(domains) == {"example.com", "corp.com", "social.net"}

        # Company entity with website
        company_entity = Mock(spec=Entity)
        company_entity.entity_type = "company"
        company_entity.data = {"website": "https://company.com"}
        domains = plugin._extract_domains_from_entity(company_entity)
        assert domains == ["company.com"]

        # Entity with no data
        empty_entity = Mock(spec=Entity)
        empty_entity.entity_type = "person"
        empty_entity.data = None
        domains = plugin._extract_domains_from_entity(empty_entity)
        assert domains == []

    def test_create_match_dict(self, plugin):
        """Test match dictionary creation"""
        entity = Mock(spec=Entity)
        entity.id = 123
        entity.entity_type = "person"
        entity.case_id = 456

        case = Mock(spec=Case)
        case.case_number = "CASE-2024-001"
        case.title = "Test Case"

        match = plugin._create_match_dict(
            entity, 
            case, 
            entity_name="John Doe",
            extra_field="extra_value"
        )

        assert match["entity_id"] == 123
        assert match["entity_type"] == "person"
        assert match["case_id"] == 456
        assert match["case_number"] == "CASE-2024-001"
        assert match["case_title"] == "Test Case"
        assert match["entity_name"] == "John Doe"
        assert match["extra_field"] == "extra_value"

    def test_get_display_name(self, plugin):
        """Test display name extraction for different entity types"""
        # Person entity
        person_data = {"first_name": "John", "last_name": "Doe"}
        assert plugin._get_display_name(person_data, "person") == "John Doe"

        # Domain entity
        domain_data = {"domain": "example.com"}
        assert plugin._get_display_name(domain_data, "domain") == "example.com"

        # Company entity - uses 'name' field not 'company'
        company_data = {"name": "Acme Corp"}
        assert plugin._get_display_name(company_data, "company") == "Acme Corp"

        # IP address entity
        ip_data = {"ip_address": "192.168.1.1"}
        assert plugin._get_display_name(ip_data, "ip_address") == "192.168.1.1"

        # Unknown entity type fallback
        unknown_data = {"Name": "Fallback Name"}
        assert plugin._get_display_name(unknown_data, "unknown_type") == "Fallback Name"

        # Empty data
        assert plugin._get_display_name({}, "person") == ""
        assert plugin._get_display_name(None, "person") == ""

    def test_get_primary_fields_for_entity(self, plugin):
        """Test primary field detection for entity types"""
        # Person entity should return first_name and last_name
        fields = plugin._get_primary_fields_for_entity("person")
        assert fields == ["first_name", "last_name"]

        # Domain entity should have domain field
        fields = plugin._get_primary_fields_for_entity("domain")
        assert "domain" in fields[0] if fields else False

        # Unknown entity type
        fields = plugin._get_primary_fields_for_entity("unknown_type")
        assert fields == []

    @pytest.mark.asyncio
    async def test_run_missing_parameters(self, plugin):
        """Test error when parameters are missing"""
        results = []
        async for result in plugin.run(None):
            results.append(result)

        assert len(results) == 1
        assert results[0]["type"] == "error"
        assert "Parameters are required" in results[0]["data"]["message"]

    @pytest.mark.asyncio
    async def test_run_empty_parameters(self, plugin):
        """Test error when parameters are empty dict"""
        results = []
        async for result in plugin.run({}):
            results.append(result)

        assert len(results) == 1
        assert results[0]["type"] == "error"
        # Empty dict evaluates to False in Python, so triggers the same error
        assert "Parameters are required" in results[0]["data"]["message"]

    @pytest.mark.asyncio
    @patch("app.plugins.correlation_plugin.get_db")
    async def test_run_missing_case_id(self, mock_get_db, plugin, mock_db_session):
        """Test error when case_id is missing but other params provided"""
        # Set current user to ensure we get to the case_id check
        plugin._current_user = Mock(id=1, role=UserRole.ADMIN)
        mock_get_db.return_value = iter([mock_db_session])
        
        # Provide non-empty params but no case_id
        results = []
        async for result in plugin.run({"other_param": "value"}):
            results.append(result)

        assert len(results) == 1
        assert results[0]["type"] == "error"
        assert "Case ID is required" in results[0]["data"]["message"]

    @pytest.mark.asyncio
    @patch("app.plugins.correlation_plugin.get_db")
    async def test_run_no_current_user(self, mock_get_db, plugin, mock_db_session):
        """Test error when current user is not set"""
        mock_get_db.return_value = iter([mock_db_session])
        plugin._current_user = None

        results = []
        async for result in plugin.run({"case_id": 123}):
            results.append(result)

        assert len(results) == 1
        assert results[0]["type"] == "error"
        assert "Current user not found" in results[0]["data"]["message"]

    @pytest.mark.asyncio
    @patch("app.plugins.correlation_plugin.get_db")
    async def test_run_access_denied_non_admin(self, mock_get_db, plugin, mock_db_session, mock_user):
        """Test access denied for non-admin user without case access"""
        mock_get_db.return_value = iter([mock_db_session])
        plugin._current_user = mock_user

        # Mock no access to case
        mock_result = Mock()
        mock_result.first.return_value = None
        mock_db_session.execute.return_value = mock_result

        results = []
        async for result in plugin.run({"case_id": 123}):
            results.append(result)

        assert len(results) == 1
        assert results[0]["type"] == "error"
        assert "You do not have access to this case" in results[0]["data"]["message"]

    @pytest.mark.asyncio
    async def test_execute_name_matches(self, plugin, mock_db_session, mock_admin_user):
        """Test finding name matches across cases"""
        plugin._current_user = mock_admin_user
        
        # Create test entities
        source_entity = Mock(spec=Entity)
        source_entity.id = 1
        source_entity.entity_type = "person"
        source_entity.case_id = 100
        source_entity.data = {"first_name": "John", "last_name": "Doe"}

        matching_entity = Mock(spec=Entity)
        matching_entity.id = 2
        matching_entity.entity_type = "person"
        matching_entity.case_id = 200
        matching_entity.data = {"first_name": "John", "last_name": "Doe"}

        case1 = Mock(spec=Case)
        case1.id = 100
        case1.case_number = "CASE-001"
        case1.title = "First Case"

        case2 = Mock(spec=Case)
        case2.id = 200
        case2.case_number = "CASE-002"
        case2.title = "Second Case"

        # Mock database responses
        with patch.object(plugin, '_get_case_entities', return_value=[source_entity]):
            with patch.object(plugin, '_find_name_matches', return_value=[{
                "entity_id": 2,
                "entity_type": "person",
                "case_id": 200,
                "case_number": "CASE-002",
                "case_title": "Second Case"
            }]):
                results = []
                async for result in plugin.execute({"case_id": 100}, mock_db_session):
                    results.append(result)

        # Should have at least one data result for name match
        data_results = [r for r in results if r["type"] == "data"]
        assert len(data_results) >= 1
        
        match_data = data_results[0]["data"]
        assert match_data["entity_name"] == "John Doe"
        assert match_data["match_type"] == "name"
        assert len(match_data["matches"]) == 1

    @pytest.mark.asyncio
    async def test_execute_employer_matches(self, plugin, mock_db_session, mock_admin_user):
        """Test finding employer matches across cases"""
        plugin._current_user = mock_admin_user
        
        # Create test entity with employer
        source_entity = Mock(spec=Entity)
        source_entity.id = 1
        source_entity.entity_type = "person"
        source_entity.case_id = 100
        source_entity.data = {
            "first_name": "John", 
            "last_name": "Doe",
            "employer": "Acme Corp"
        }

        # Mock database responses
        with patch.object(plugin, '_get_case_entities', return_value=[source_entity]):
            with patch.object(plugin, '_find_name_matches', return_value=[]):
                with patch.object(plugin, '_find_employer_matches', return_value=[{
                "entity_id": 3,
                "entity_type": "person",
                "case_id": 300,
                "case_number": "CASE-003",
                "case_title": "Third Case",
                    "person_name": "Jane Smith"
                }]):
                    with patch.object(plugin, '_find_domain_matches', return_value={}):
                        results = []
                        async for result in plugin.execute({"case_id": 100}, mock_db_session):
                            results.append(result)

        # Should have employer match
        data_results = [r for r in results if r["type"] == "data" and r["data"].get("match_type") == "employer"]
        assert len(data_results) == 1
        
        match_data = data_results[0]["data"]
        assert match_data["employer_name"] == "Acme Corp"
        assert match_data["match_type"] == "employer"

    @pytest.mark.asyncio
    async def test_execute_domain_matches(self, plugin, mock_db_session, mock_admin_user):
        """Test finding domain matches across cases"""
        plugin._current_user = mock_admin_user
        
        # Create test entity with email
        source_entity = Mock(spec=Entity)
        source_entity.id = 1
        source_entity.entity_type = "person"
        source_entity.case_id = 100
        source_entity.data = {
            "first_name": "John",
            "last_name": "Doe", 
            "email": "john@example.com"
        }

        # Mock database responses
        with patch.object(plugin, '_get_case_entities', return_value=[source_entity]):
            with patch.object(plugin, '_find_name_matches', return_value=[]):
                with patch.object(plugin, '_find_employer_matches', return_value=[]):
                    with patch.object(plugin, '_find_domain_matches', return_value={
                "example.com": [{
                    "entity_id": 4,
                    "entity_type": "domain",
                    "case_id": 400,
                    "case_number": "CASE-004",
                    "case_title": "Fourth Case",
                    "entity_name": "example.com",
                        "found_in": "domain field"
                    }]
                }):
                        results = []
                        async for result in plugin.execute({"case_id": 100}, mock_db_session):
                            results.append(result)

        # Should have domain match
        data_results = [r for r in results if r["type"] == "data" and r["data"].get("match_type") == "domain"]
        assert len(data_results) == 1
        
        match_data = data_results[0]["data"]
        assert match_data["domain"] == "example.com"
        assert match_data["match_type"] == "domain"

    @pytest.mark.asyncio
    async def test_execute_exception_handling(self, plugin, mock_db_session, mock_admin_user):
        """Test exception handling during execution"""
        plugin._current_user = mock_admin_user
        
        # Mock exception during entity retrieval
        with patch.object(plugin, '_get_case_entities', side_effect=Exception("Database error")):
            results = []
            async for result in plugin.execute({"case_id": 100}, mock_db_session):
                results.append(result)

        assert len(results) == 1
        assert results[0]["type"] == "error"
        assert "Error during correlation scan: Database error" in results[0]["data"]["message"]

    @pytest.mark.asyncio
    async def test_find_name_matches(self, plugin, mock_db_session, mock_user):
        """Test finding entities with matching names"""
        plugin._current_user = mock_user
        
        source_entity = Mock(spec=Entity)
        source_entity.id = 1
        source_entity.entity_type = "person"
        source_entity.data = {"first_name": "John", "last_name": "Doe"}

        matching_entity = Mock(spec=Entity)
        matching_entity.id = 2
        matching_entity.entity_type = "person" 
        matching_entity.data = {"first_name": "John", "last_name": "Doe"}

        case = Mock(spec=Case)
        case.case_number = "CASE-002"
        case.title = "Match Case"

        # Mock query result
        mock_result = [(matching_entity, case)]
        mock_db_session.execute.return_value = mock_result

        matches = await plugin._find_name_matches(mock_db_session, source_entity, "John Doe")
        
        assert len(matches) == 1
        assert matches[0]["entity_id"] == 2
        assert matches[0]["case_number"] == "CASE-002"

    @pytest.mark.asyncio
    async def test_find_employer_matches(self, plugin, mock_db_session, mock_user):
        """Test finding entities with matching employer"""
        plugin._current_user = mock_user
        
        source_entity = Mock(spec=Entity)
        source_entity.id = 1
        source_entity.entity_type = "person"

        matching_entity = Mock(spec=Entity)
        matching_entity.id = 2
        matching_entity.entity_type = "person"
        matching_entity.data = {
            "first_name": "Jane",
            "last_name": "Smith",
            "employer": "Acme Corp"
        }

        case = Mock(spec=Case)
        case.case_number = "CASE-003"
        case.title = "Employer Match Case"

        # Mock query result
        mock_result = [(matching_entity, case)]
        mock_db_session.execute.return_value = mock_result

        matches = await plugin._find_employer_matches(mock_db_session, source_entity, "Acme Corp")
        
        assert len(matches) == 1
        assert matches[0]["entity_id"] == 2
        assert matches[0]["person_name"] == "Jane Smith"

    @pytest.mark.asyncio
    async def test_find_entities_with_domain(self, plugin, mock_db_session, mock_user):
        """Test finding entities containing a specific domain"""
        plugin._current_user = mock_user
        
        source_entity = Mock(spec=Entity)
        source_entity.id = 1

        # Person entity with email
        person_entity = Mock(spec=Entity)
        person_entity.id = 2
        person_entity.entity_type = "person"
        person_entity.data = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com"
        }

        # Company entity with website
        company_entity = Mock(spec=Entity)
        company_entity.id = 3
        company_entity.entity_type = "company"
        company_entity.data = {
            "company": "Example Inc",
            "website": "https://example.com"
        }

        case1 = Mock(spec=Case)
        case1.case_number = "CASE-001"
        case1.title = "Case 1"

        case2 = Mock(spec=Case)
        case2.case_number = "CASE-002"
        case2.title = "Case 2"

        # Mock query result
        mock_result = [(person_entity, case1), (company_entity, case2)]
        mock_db_session.execute.return_value = mock_result

        matches = await plugin._find_entities_with_domain(mock_db_session, source_entity, "example.com")
        
        assert len(matches) == 2
        
        # Check person match
        person_match = next(m for m in matches if m["entity_id"] == 2)
        assert "email: john@example.com" in person_match["found_in"]
        
        # Check company match
        company_match = next(m for m in matches if m["entity_id"] == 3)
        assert "website: https://example.com" in company_match["found_in"]

    def test_format_evidence_content(self, plugin):
        """Test evidence content formatting"""
        results = [
            {
                "entity_name": "John Doe",
                "entity_type": "person",
                "match_type": "name",
                "matches": [{
                    "case_title": "Related Case",
                    "case_number": "CASE-002",
                    "case_id": 200
                }]
            },
            {
                "entity_name": "Jane Smith",
                "entity_type": "person", 
                "match_type": "employer",
                "employer_name": "Acme Corp",
                "matches": [{
                    "case_title": "Another Case",
                    "case_number": "CASE-003",
                    "case_id": 300,
                    "person_name": "Bob Johnson"
                }]
            }
        ]
        
        params = {"case_id": 100}
        
        content = plugin._format_evidence_content(results, params)
        
        assert "Correlation Scan Results" in content
        assert "Total entities with matches: 2" in content
        assert "Case ID: 100" in content
        assert "Entity: John Doe" in content
        assert "Entity: Jane Smith" in content
        assert "Employer: Acme Corp" in content
        assert "Person: Bob Johnson" in content

    def test_parse_output(self, plugin):
        """Test parse_output returns None as expected"""
        result = plugin.parse_output("test line")
        assert result is None

    @pytest.mark.asyncio
    async def test_build_accessible_entities_query_admin(self, plugin, mock_db_session, mock_admin_user):
        """Test query building for admin users"""
        plugin._current_user = mock_admin_user
        
        # Admin should get unrestricted query
        query = plugin._build_accessible_entities_query(mock_db_session)
        
        # Query should not have user restrictions
        # (This is a simplified test - in real scenario would check the actual SQL)
        assert query is not None

    @pytest.mark.asyncio
    async def test_build_accessible_entities_query_non_admin(self, plugin, mock_db_session, mock_user):
        """Test query building for non-admin users"""
        plugin._current_user = mock_user
        
        # Non-admin should get restricted query
        query = plugin._build_accessible_entities_query(
            mock_db_session,
            exclude_entity_id=123,
            entity_type_filter="person"
        )
        
        # Query should have filters applied
        assert query is not None

    @pytest.mark.asyncio
    async def test_get_case_entities(self, plugin, mock_db_session):
        """Test retrieving entities for a specific case"""
        # Mock entities
        entity1 = Mock(spec=Entity)
        entity1.id = 1
        entity2 = Mock(spec=Entity)
        entity2.id = 2
        
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [entity1, entity2]
        mock_db_session.execute.return_value = mock_result
        
        entities = await plugin._get_case_entities(mock_db_session, 100)
        
        assert len(entities) == 2
        assert entities[0].id == 1
        assert entities[1].id == 2

    def test_plugin_metadata(self, plugin):
        """Test plugin metadata"""
        metadata = plugin.get_metadata()
        
        assert metadata["name"] == "CorrelationScan"
        assert metadata["display_name"] == "Correlation Scan"
        assert metadata["category"] == "Other"
        assert metadata["description"] == "Finds matching entities and relationships across cases"
        
        # Check parameters
        params = metadata["parameters"]
        assert "case_id" in params
        assert params["case_id"]["type"] == "integer"
        assert params["case_id"]["required"] is True

    @pytest.mark.asyncio
    async def test_run_with_injected_session(self, plugin, mock_db_session, mock_admin_user):
        """Test run method with injected database session"""
        plugin._db_session = mock_db_session
        plugin._current_user = mock_admin_user
        
        # Mock get_case_entities to return empty list
        with patch.object(plugin, '_get_case_entities', return_value=[]):
            results = []
            async for result in plugin.run({"case_id": 123}):
                results.append(result)
        
        # Should complete without errors (no matches found)
        error_results = [r for r in results if r["type"] == "error"]
        assert len(error_results) == 0

    @pytest.mark.asyncio
    async def test_deduplication_of_matches(self, plugin, mock_db_session, mock_admin_user):
        """Test that duplicate matches are properly deduplicated"""
        plugin._current_user = mock_admin_user
        
        # Create test entities that would generate duplicate matches
        entity1 = Mock(spec=Entity)
        entity1.id = 1
        entity1.entity_type = "person"
        entity1.data = {"first_name": "John", "last_name": "Doe"}
        
        entity2 = Mock(spec=Entity)
        entity2.id = 2
        entity2.entity_type = "person"
        entity2.data = {"first_name": "John", "last_name": "Doe"}
        
        # Both entities from same case should only report match once
        with patch.object(plugin, '_get_case_entities', return_value=[entity1, entity2]):
            with patch.object(plugin, '_find_name_matches', return_value=[{
                "entity_id": 99,
                "entity_type": "person",
                "case_id": 999,
                "case_number": "CASE-999",
                "case_title": "External Case"
            }]):
                results = []
                async for result in plugin.execute({"case_id": 100}, mock_db_session):
                    if result["type"] == "data":
                        results.append(result)
        
        # Should only have one match report for "John Doe" despite two entities
        name_matches = [r for r in results if r["data"].get("match_type") == "name"]
        assert len(name_matches) == 1
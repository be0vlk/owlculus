# Hunt Development Guide

This guide explains how to create custom hunt flows in Owlculus. Hunts are automated workflows that orchestrate multiple OSINT plugins into reusable investigation patterns.

## Architecture Overview

Hunts in Owlculus are implemented as Python classes that inherit from `BaseHunt`. The system automatically discovers hunt definitions from the `/backend/app/hunts/definitions/` directory and provides a complete UI for executing and monitoring them.

### Key Components

1. **BaseHunt** (`/backend/app/hunts/base_hunt.py`) - Abstract base class all hunts inherit from
2. **HuntExecutor** (`/backend/app/hunts/hunt_executor.py`) - Orchestrates step execution with dependency management
3. **HuntContext** (`/backend/app/hunts/hunt_context.py`) - Manages data flow between steps
4. **HuntService** (`/backend/app/services/hunt_service.py`) - Service layer for hunt management
5. **Database Models** - Hunt, HuntExecution, and HuntStep track definitions and runs

## Creating a New Hunt

This process can be simplified by using the `create_hunt.py` script in the `scripts` directory, but I encourage you to read through this guide to understand the process.

### 1. Create Hunt Definition Class

Create a new Python file in `/backend/app/hunts/definitions/` that inherits from `BaseHunt`:

```python
from typing import List, Optional
from sqlmodel import Session
from ..base_hunt import BaseHunt, HuntStepDefinition

class YourHunt(BaseHunt):
    """Description of what your hunt does"""
    
    def __init__(self, db_session: Optional[Session] = None):
        super().__init__()
        self.display_name = "Your Hunt Display Name"
        self.description = "Detailed description of the hunt workflow"
        self.category = "category_name"  # domain, person, company, etc.
        
        # Define initial parameters users will provide
        self.initial_parameters = {
            "target": {
                "type": "string",
                "description": "Target to investigate",
                "required": True
            },
            "depth": {
                "type": "number", 
                "description": "Investigation depth",
                "default": 1,
                "required": False
            }
        }
    
    def get_steps(self) -> List[HuntStepDefinition]:
        """Define the workflow steps"""
        return [
            HuntStepDefinition(
                step_id="step1",
                plugin_name="PluginClassName",
                display_name="Step 1 Display Name",
                description="What this step does",
                parameter_mapping={
                    "plugin_param": "initial.target"
                },
                timeout_seconds=300
            ),
            HuntStepDefinition(
                step_id="step2",
                plugin_name="AnotherPlugin",
                display_name="Step 2",
                description="Analyzes results from step 1",
                parameter_mapping={
                    "input": "step1.results[0].data"
                },
                depends_on=["step1"],
                optional=True
            )
        ]
```

### 2. Understanding HuntStepDefinition

Each step in your hunt workflow is defined with these parameters:

- **step_id** (required): Unique identifier within the hunt
- **plugin_name** (required): Class name of the plugin to execute
- **display_name** (required): User-friendly name shown in UI
- **description** (required): Explanation of what the step does
- **parameter_mapping**: Maps hunt/step data to plugin parameters
- **static_parameters**: Fixed parameters passed to the plugin
- **depends_on**: List of step_ids that must complete first
- **optional**: Whether step failure should stop the hunt
- **timeout_seconds**: Maximum execution time (default: 300)
- **max_retries**: Retry attempts on failure (default: 3)
- **save_to_case**: Save results as evidence (default: True)

### 3. Parameter Mapping Syntax

The `parameter_mapping` field uses a simple dot notation to reference data:

```python
parameter_mapping={
    # Get from initial parameters
    "domain": "initial.domain_name",
    
    # Get from previous step output
    "ip": "dns_lookup.results[0].ip_address",
    
    # Get nested values
    "email": "whois_step.results[0].registrant.email",
    
    # Complex path traversal
    "hosts": "subdomain_enum.results[0].discovered_hosts"
}
```

Mapping prefixes:
- `initial.` - References initial hunt parameters
- `{step_id}.` - References output from a previous step

### 4. Dynamic Parameters Based on Configuration

Hunts can adapt their parameters based on available API keys:

```python
def __init__(self, db_session: Optional[Session] = None):
    super().__init__()
    # ... other initialization ...
    # db_session parameter enables dynamic parameter configuration based on API availability
    self.initial_parameters = self._build_parameters(db_session)

def _build_parameters(self, db_session: Optional[Session] = None) -> dict:
    """Build parameters dynamically"""
    params = {
        "target": {
            "type": "string",
            "required": True
        }
    }
    
    # Only add parameter if API key is configured
    if self._check_api_key_available(db_session, "shodan"):
        params["enable_shodan"] = {
            "type": "boolean",
            "description": "Use Shodan for enhanced scanning",
            "default": False
        }
    
    return params
```

## Hunt Execution Flow

1. **Discovery**: HuntService loads all hunt classes from definitions directory
2. **Registration**: Hunts are synced to database with their JSON definitions
3. **Execution Request**: User selects hunt and provides initial parameters
4. **Validation**: Hunt validates parameters using `validate_parameters()`
5. **Execution**: HuntExecutor manages the workflow:
   - Creates HuntExecution and HuntStep records
   - Resolves step dependencies
   - Executes steps in order (respecting dependencies)
   - Manages parameter resolution via HuntContext
   - Handles retries and timeouts
   - Updates progress in real-time

## Real Example: Domain Hunt

Here's how the actual DomainHunt is implemented:

```python
class DomainHunt(BaseHunt):
    """Comprehensive domain and infrastructure investigation"""
    
    def get_steps(self) -> List[HuntStepDefinition]:
        return [
            HuntStepDefinition(
                step_id="whois_lookup",
                plugin_name="WhoisPlugin",
                display_name="WHOIS lookup",
                description="Get domain registration information",
                parameter_mapping={"domain": "initial.domain"},
                timeout_seconds=120,
                optional=True
            ),
            HuntStepDefinition(
                step_id="dns_records",
                plugin_name="DnsLookupPlugin", 
                display_name="DNS records lookup",
                description="Retrieve all DNS records for the domain",
                parameter_mapping={"domain": "initial.domain"},
                timeout_seconds=180
            ),
            HuntStepDefinition(
                step_id="subdomain_enum",
                plugin_name="SubdomainEnumPlugin",
                display_name="Subdomain enumeration",
                description="Find subdomains of the target domain",
                parameter_mapping={
                    "domain": "initial.domain",
                    "concurrency": "initial.subdomain_concurrency"
                },
                timeout_seconds=600,
                optional=True
            ),
            HuntStepDefinition(
                step_id="ip_investigation_from_dns",
                plugin_name="ShodanPlugin",
                display_name="Investigate main domain IP",
                description="Analyze the IP address of the main domain",
                parameter_mapping={
                    # Extract IP from DNS A record
                    "query": "dns_records.results[0].results[0].records[0]"
                },
                static_parameters={"search_type": "ip", "limit": 10.0},
                depends_on=["dns_records"],
                timeout_seconds=90,
                optional=True
            )
        ]
```

## Available Plugins for Hunts

Currently available plugins include:
- **WhoisPlugin** - Domain registration information
- **DnsLookupPlugin** - DNS record retrieval  
- **SubdomainEnumPlugin** - Subdomain discovery and enumeration
- **ShodanPlugin** - IP address and service analysis
- **HolehePlugin** - Email account discovery across platforms
- **PeopleDataLabsPlugin** - Person information enrichment
- **VirusTotalPlugin** - Malware and reputation analysis
- **CorrelationPlugin** - Cross-case entity correlation

## Plugin Requirements for Hunts

Plugins used in hunts must:

1. **Inherit from BasePlugin** with proper parameter definitions
2. **Support async execution** via `execute()` method
3. **Return structured data** that can be referenced by subsequent steps
4. **Handle the `save_to_case` parameter** to store evidence
5. **Implement proper error handling** for resilient workflows

## Testing Your Hunt

1. **Manual Testing**:
   ```bash
   # Restart backend to load new hunt
   docker compose restart backend
   
   # Check hunt appears in API
   curl http://localhost:8000/api/hunts
   ```

2. **UI Testing**:
   - Navigate to Hunts dashboard
   - Your hunt should appear in the catalog
   - Test execution with sample data
   - Monitor real-time progress

3. **Unit Testing**:
   ```python
   # tests/hunts/test_your_hunt.py
   from app.hunts.definitions.your_hunt import YourHunt
   
   def test_hunt_parameters():
       hunt = YourHunt()
       params = {"target": "example.com"}
       validated = hunt.validate_parameters(params)
       assert validated["target"] == "example.com"
   
   def test_hunt_steps():
       hunt = YourHunt()
       steps = hunt.get_steps()
       assert len(steps) > 0
       assert all(step.step_id for step in steps)
   ```

## Best Practices

1. **Step Dependencies**: Only add dependencies when output from one step is needed by another
2. **Optional Steps**: Mark steps as optional if their failure shouldn't stop the investigation
3. **Timeouts**: Set realistic timeouts based on plugin behavior
4. **Parameter Validation**: Implement thorough validation in `validate_parameters()`
5. **Error Messages**: Provide clear descriptions to help users understand failures
6. **Evidence Storage**: Use `save_to_case=True` for steps that produce valuable evidence

## Frontend Integration

The frontend automatically:
- Generates forms for initial parameters based on type definitions
- Shows real-time progress via WebSocket connections
- Displays step results and errors
- Allows viewing execution history
- Provides access to saved evidence

No frontend changes needed when adding new hunts!

## Troubleshooting

1. **Hunt not appearing**: Check that your class inherits from BaseHunt and is in the definitions directory
2. **Parameter errors**: Verify parameter mapping syntax and that referenced steps exist
3. **Plugin not found**: Ensure plugin class name matches exactly
4. **Dependency issues**: Check that depends_on references valid step_ids

## Advanced Features

### Conditional Steps (Future Enhancement)
While not currently implemented, the architecture supports adding conditional execution:
```python
# Potential future syntax
HuntStepDefinition(
    step_id="detailed_scan",
    plugin_name="DeepScanner",
    condition="step1.risk_score > 7",  # Not yet implemented
    # ...
)
```

### Parallel Execution (Future Enhancement)
The executor could be enhanced to run independent steps in parallel:
```python
# Steps with no overlapping dependencies could run simultaneously
# This is a future optimization opportunity
```

## Contributing

When contributing hunt definitions:
1. Follow the naming convention: `{target_type}_hunt.py`
2. Provide comprehensive descriptions
3. Test with various input scenarios
4. Document any special requirements
5. Consider API key availability
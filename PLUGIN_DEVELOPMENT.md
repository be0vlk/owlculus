# Plugin Development Guide

## Quick Start: Plugin Generator Script

**The fastest way to create a new plugin is using the plugin generator script:**

### Interactive Mode (Recommended)
```bash
python scripts/create_plugin.py
```

This will guide you through:
- Plugin name and display name
- Description and categories
- Required Python dependencies
- Test file generation
- Frontend component creation (optional - automatic UI works for most plugins)

### Command Line Mode
```bash
# Create a basic plugin
python scripts/create_plugin.py my_plugin

# Create with dependencies and custom settings
python scripts/create_plugin.py whois \
  --category Network \
  --evidence-category "Network Assets" \
  --dependencies "python-whois" \
  --description "Query domain registration information"

# Create backend-only plugin (recommended - UI is automatic)
python scripts/create_plugin.py api_tool \
  --backend-only \
  --no-tests \
  --dependencies "requests,beautifulsoup4"
```

### Generator Features
- **Automatic File Creation**: Backend plugin, frontend components (optional), and test files
- **Automatic UI Generation**: GenericPluginParams and PluginResult handle 95% of UI needs
- **Dependency Management**: Automatically adds packages to `requirements.txt`
- **Category-Specific Templates**: Optimized templates based on plugin category
- **Comprehensive Tests**: Generates test scaffolding with multiple test cases
- **Best Practices**: Follows all plugin development patterns and conventions

### Generator Options
- `--category`: Person, Network, Company, Other
- `--evidence-category`: Social Media, Associates, Network Assets, Communications, Documents, Other
- `--dependencies`: Comma-separated list of Python packages
- `--backend-only`: Skip frontend component generation (recommended - UI is automatic)
- `--no-tests`: Skip test file generation
- `--force`: Overwrite existing files

---

## Plugin Architecture Overview

Owlculus uses a plugin system that consists of:
- **Backend Plugin**: Python class that handles the actual tool execution
- **Frontend Parameter Component**: Vue component for user input (usually not needed - automatic UI handles 95% of cases)
- **Frontend Result Component**: Vue component for displaying results (usually not needed - automatic fallback handles most cases)

The system automatically discovers and loads plugins based on naming conventions and provides automatic UI generation through `GenericPluginParams.vue` and `PluginResult.vue`.

## Automatic UI System

**Most plugins don't need custom frontend components!** Owlculus provides a sophisticated automatic UI generation system:

### GenericPluginParams.vue
Automatically generates parameter forms based on your backend plugin's parameter schema:
- **String parameters** → Text input fields with descriptions
- **Number/Float parameters** → Number input fields with validation
- **Boolean parameters** → Toggle switches
- **Required validation** → Automatic based on schema
- **Default values** → Pre-populated from schema
- **API key warnings** → Automatic validation and user guidance
- **Case selection** → Automatic for evidence saving

### PluginResult.vue
Provides intelligent fallback display for any result data structure:
- **Automatic component loading** → Tries to load custom result component first
- **Smart fallback** → Beautiful display for any JSON data structure
- **Error handling** → Consistent error message display
- **Empty states** → Proper "no results" messaging
- **Data formatting** → Intelligent formatting for different data types

### When to Create Custom Components
**Parameter Component**: Only needed for:
- Custom validation logic beyond required/optional
- Special UI elements (dropdowns, file uploads, multi-select)
- Custom parameter grouping or complex layouts
- Plugin-specific help text or examples

**Result Component**: Only needed for:
- Custom data visualization (charts, tables, graphs)
- Special formatting for specific data types  
- Custom actions (copy buttons, download links)
- Plugin-specific styling or layout requirements

**Recommendation**: Start with the automatic UI (use `--backend-only`) and only add custom components if the automatic system doesn't meet your specific needs.

## Manual Plugin Development

### 1. File Location and Naming
- **Location**: `/backend/app/plugins/`
- **Naming Convention**: `{plugin_name}_plugin.py`
- **Examples**: `holehe_plugin.py`, `dnslookup_plugin.py`

### 2. Basic Plugin Structure

```python
"""
Brief description of what your plugin does
"""

import asyncio
from typing import AsyncGenerator, Dict, Any, Optional
from .base_plugin import BasePlugin

class YourPluginNamePlugin(BasePlugin):
    """Plugin description for your tool"""

    def __init__(self):
        super().__init__(display_name="Your Display Name")
        self.description = "Brief 1-2 sentence description of what this plugin does"
        self.category = "Person"  # Person, Network, Company, Other (for UI organization)
        self.evidence_category = "Social Media"  # Evidence category for case storage
        self.save_to_case = False  # Whether to auto-save results as evidence (deprecated - use centralized system)
        self.parameters = {
            "required_param": {
                "type": "string",  # string, float, boolean
                "description": "Description for the parameter",
                "required": True,
            },
            "optional_param": {
                "type": "float",
                "description": "Optional parameter description",
                "default": 10.0,
                "required": False,
            },
            # Note: save_to_case parameter is automatically added by BasePlugin
        }

    def parse_output(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse command output - only needed for subprocess-based plugins"""
        # For direct API/library calls, return None
        return None

    async def run(
        self, params: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Main plugin execution method
        
        Args:
            params: User-provided parameters
            
        Yields:
            Structured data results
        """
        if not params or "required_param" not in params:
            yield {"type": "error", "data": {"message": "Required parameter missing"}}
            return

        # Extract parameters
        input_value = params["required_param"]
        timeout = params.get("optional_param", 10.0)

        # Your plugin logic here
        # Example: API calls, tool execution, data processing
        
        # Yield results as they become available
        yield {
            "type": "data",
            "data": {
                "result_field": "some_value",
                "timestamp": time.time(),
            },
        }

        # Evidence saving is handled automatically by BasePlugin
        # No manual implementation needed - just yield data results
```

### 3. Plugin Categories

#### UI Categories (for plugin organization):
- **Person**: Email lookups, social media checks, people search
- **Network**: DNS, IP analysis, network reconnaissance  
- **Company**: Business intelligence, corporate research
- **Other**: Miscellaneous tools

#### Evidence Categories (for case storage):
- **Social Media**: Social platform related evidence
- **Associates**: People/contacts related evidence  
- **Network Assets**: IP addresses, domains, network infrastructure
- **Communications**: Email, messages, communication records
- **Documents**: Files, reports, documentation
- **Other**: Default catch-all category

**Note**: The `category` field controls UI organization, while `evidence_category` determines where evidence is stored in the case.

### 4. Result Types
Your plugin should yield dictionaries with these `type` values:
- **`"data"`**: Actual results (what users care about)
- **`"error"`**: Error messages

### 5. Evidence Categories

Each plugin must specify both categories:

```python
self.category = "Network"           # UI organization (Person/Network/Company/Other)
self.evidence_category = "Network Assets"  # Evidence storage category
```

**Valid Evidence Categories**:
- `"Social Media"` - Social platform data
- `"Associates"` - People/contact information  
- `"Network Assets"` - Domains, IPs, network data
- `"Communications"` - Messages, emails
- `"Documents"` - Reports, files
- `"Other"` - Default fallback

**Category Validation**: The BasePlugin validates `evidence_category` on initialization and will raise an error for invalid categories.

### 6. Evidence Saving System

Owlculus automatically handles evidence saving for all plugins:

#### Automatic Features:
- **Parameter Injection**: `save_to_case` parameter is automatically added to all plugins
- **Result Collection**: All `"data"` type results are automatically collected during execution
- **Database Handling**: Database sessions and evidence creation are handled centrally
- **File Generation**: Evidence files are automatically created with timestamps

#### Default Evidence Format:
```
Plugin Name Results
==================================================

Total results: X
Execution time: 2024-01-15 10:30:45 UTC

Parameters:
--------------------
param1: value1
param2: value2

Results:
--------------------

Result #1:
{
  "field1": "value1",
  "field2": "value2"
}
```

#### Custom Evidence Formatting:
Override `_format_evidence_content()` in your plugin for custom formatting:

```python
def _format_evidence_content(self, results: List[Dict[str, Any]], params: Dict[str, Any]) -> str:
    """Custom formatting for evidence content"""
    content_lines = [
        f"{self.display_name} Investigation Results",
        "=" * 50,
        "",
        f"Target: {params.get('target', 'Unknown')}",
        f"Total findings: {len(results)}",
        "",
    ]
    
    for result in results:
        content_lines.extend([
            f"Finding: {result.get('description', 'N/A')}",
            f"Confidence: {result.get('confidence', 'Unknown')}",
            "",
        ])
    
    return "\n".join(content_lines)
```

### 6. API Key Requirements

Plugins can declare required API keys that will be automatically validated:

```python
class MyPlugin(BasePlugin):
    def __init__(self):
        super().__init__()
        self.api_key_requirements = ["provider_name"]  # e.g., ["openai", "shodan"]

    async def run(self, params: Optional[Dict[str, Any]] = None) -> AsyncGenerator[Dict[str, Any], None]:
        # Check API key requirements (automatically handled by BasePlugin)
        if hasattr(self, 'api_key_requirements') and self.api_key_requirements:
            missing_keys = self.check_api_key_requirements()
            if missing_keys:
                yield {
                    "type": "error",
                    "data": {
                        "message": f"API key{'s' if len(missing_keys) > 1 else ''} required for: {', '.join(missing_keys)}. "
                                  "Please add them in Admin → Configuration → API Keys"
                    }
                }
                return
        
        # Your plugin logic here...
```

The system will:
- Check if required API keys are configured before execution
- Show warnings in the UI when keys are missing
- Disable plugin execution until keys are configured
- Direct admins to the configuration page
- Provide simplified API key checking in generated plugins

### 7. Dependencies
Add any required packages to `/backend/requirements.txt`:
```txt
your-package-name==version
```

## Frontend Components (Usually Not Needed - Automatic UI Available)

### Automatic UI Generation (Recommended)

**Most plugins don't need custom frontend components!** The system provides automatic UI generation:

- **`GenericPluginParams.vue`**: Automatically generates parameter forms based on your backend plugin's parameter schema
- **`PluginResult.vue`**: Provides intelligent fallback display for any result data structure

**What's handled automatically:**
- Parameter form generation (string, number, boolean types)
- API key validation and warning messages
- Case selection for evidence saving
- Plugin description display
- Error handling and validation

### 1. Custom Parameter Component (Only If Needed)

**Location**: `/frontend/src/components/plugins/YourPluginNamePluginParams.vue`

**Only create this if you need:**
- Custom validation beyond basic required/optional
- Special UI elements (dropdowns, multi-select, file uploads)
- Custom parameter layout or grouping
- Plugin-specific help text or examples

```vue
<template>
  <!-- Most plugins should just use GenericPluginParams -->
  <GenericPluginParams
    :parameters="parameters"
    :model-value="modelValue"
    :plugin-name="'YourPluginNamePlugin'"
    @update:model-value="$emit('update:modelValue', $event)"
  />
  
  <!-- Only add custom fields if GenericPluginParams doesn't meet your needs -->
</template>

<script setup>
import GenericPluginParams from './GenericPluginParams.vue'

// Standard props for all plugin parameter components
defineProps({
  parameters: {
    type: Object,
    required: true
  },
  modelValue: {
    type: Object,
    required: true
  }
})

defineEmits(['update:modelValue'])

// GenericPluginParams automatically handles:
// - Parameter form generation based on backend schema
// - API key warnings and validation
// - Case selection for evidence saving
// - All standard parameter types (string, number, boolean)
</script>
```

### 2. Custom Result Component (Only If Needed)

**Location**: `/frontend/src/components/plugins/YourPluginNamePluginResult.vue`

**The automatic `PluginResult.vue` provides a good fallback display for all data types.** Only create a custom result component if you need:

- Custom formatting for specific data types
- Special visualization (charts, tables, graphs)
- Custom actions (copy buttons, links, downloads)
- Plugin-specific styling or layout

```vue
<template>
  <div class="d-flex flex-column ga-4">
    <!-- TODO: Customize your result display here -->
    <!-- 
      This component is optional! The automatic PluginResult.vue provides
      a good fallback display for most plugins. Only create this if you need
      special formatting or custom actions.
    -->
    
    <template v-for="(item, index) in parsedResults" :key="index">
      <!-- Data Results -->
      <v-card v-if="item.type === 'data'" elevation="2" rounded="lg">
        <v-card-title class="d-flex align-center">
          <v-icon icon="mdi-your-icon" class="mr-2" />
          {{ item.data.target || 'Plugin Results' }}
        </v-card-title>
        <v-card-text>
          <!-- Example: Display your plugin's specific data structure -->
          <pre class="text-caption">{{ JSON.stringify(item.data, null, 2) }}</pre>
        </v-card-text>
      </v-card>

      <!-- Error Messages -->
      <v-alert
        v-else-if="item.type === 'error'"
        type="error"
        variant="outlined"
      >
        {{ item.data.message }}
      </v-alert>
    </template>

    <!-- No Results -->
    <v-card v-if="!parsedResults.length" elevation="2" rounded="lg">
      <v-card-text class="text-center pa-8">
        <v-icon icon="mdi-magnify" size="48" color="grey-darken-1" class="mb-3" />
        <p class="text-body-2 text-medium-emphasis">
          No results available.
        </p>
      </v-card-text>
    </v-card>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  result: {
    type: [Object, Array],
    required: true,
  }
})

// Parse streaming results
const parsedResults = computed(() => {
  if (!props.result) return []
  
  if (Array.isArray(props.result)) {
    return props.result
  }
  
  if (props.result.type) {
    return [props.result]
  }
  
  return []
})
</script>
```

## Plugin Discovery and Registration

The system automatically:
1. **Scans** `/backend/app/plugins/` for `*_plugin.py` files
2. **Imports** classes that inherit from `BasePlugin`
3. **Discovers** frontend components by naming convention:
   - `{PluginName}PluginParams.vue` (parameters)
   - `{PluginName}PluginResult.vue` (results)

**Important**: Plugin name transformation removes "Plugin" suffix and capitalizes first letter.
- `HolehePlugin` → looks for `HolehePluginParams.vue`
- `DnsLookup` → looks for `DnsLookupPluginParams.vue`

## Development Workflow

### Recommended: Use Plugin Generator (Backend-Only)
```bash
# Interactive mode (recommended - defaults to backend-only)
python scripts/create_plugin.py

# Command line mode with backend-only (recommended)
python scripts/create_plugin.py my_tool --backend-only --dependencies "requests,beautifulsoup4"

# Only create frontend components if you need custom UI features
python scripts/create_plugin.py my_tool --dependencies "requests,beautifulsoup4"
```

The generator handles all the boilerplate and follows best practices automatically. **Most plugins should use `--backend-only` since the automatic UI generation handles 95% of use cases.**

### Manual Development (Alternative)

#### 1. Create Backend Plugin
```bash
# 1. Add dependencies to requirements.txt
echo "your-tool==1.0.0" >> backend/requirements.txt

# 2. Create plugin file
touch backend/app/plugins/mytool_plugin.py

# 3. Implement plugin class (see structure above)

# 4. Install dependencies in container
docker compose exec backend pip install your-tool
```

#### 2. Create Frontend Components (Usually Not Needed)
```bash
# Only create these if automatic UI doesn't meet your needs
# GenericPluginParams.vue handles 95% of parameter forms
# PluginResult.vue provides good fallback for all result types

# Create parameter component (only if you need custom UI)
touch frontend/src/components/plugins/MytoolPluginParams.vue

# Create result component (only if you need custom visualization)
touch frontend/src/components/plugins/MytoolPluginResult.vue
```

#### 3. Create Tests (Recommended)
```bash
# Create test file
touch backend/tests/plugins/test_mytool_plugin.py

# Implement test cases (see generated examples)
```

### Final Steps (Both Methods)
```bash
# Install new dependencies
docker compose exec backend pip install your-new-dependencies

# Restart backend to load new plugin
docker compose restart backend

# Run tests
docker compose exec backend pytest backend/tests/plugins/test_mytool_plugin.py

# Plugin should appear in the frontend automatically
# Navigate to Plugins dashboard to test
```

## Best Practices

### Backend
- **Keep descriptions concise** (1-2 sentences)
- **Set appropriate categories** - both UI category and evidence category
- **Use valid evidence categories** - BasePlugin validates evidence_category on initialization
- **Handle errors gracefully** - yield error results instead of throwing exceptions
- **Add delays** between API calls to be respectful (`await asyncio.sleep(0.1)`)
- **Only yield meaningful results** - filter out noise, no status/completion messages
- **Use appropriate timeouts** for external API calls
- **Evidence saving is automatic** - BasePlugin handles evidence saving automatically when `save_to_case=True`
- **Keep output clean** - users want results, not progress updates

### Frontend
- **Use automatic UI generation** - GenericPluginParams and PluginResult handle most cases
- **Only create custom components** when you need special UI features
- **Follow Vuetify patterns** for consistent UI when customizing
- **Provide clear parameter labels** and placeholders in custom components
- **Include validation** for required fields in custom components
- **Show copy functionality** for useful data in custom components
- **Handle empty results** gracefully in custom components
- **Use appropriate icons** from Material Design Icons

### Security
- **Never log sensitive data** (API keys, passwords)
- **Validate input parameters** properly
- **Use proper error handling** to avoid exposing system information
- **Follow principle of least privilege** for external tool access
- **Use the centralized API key system** instead of hardcoding keys or environment variables

## API Key Integration

Owlculus provides a centralized, secure API key management system that plugins should use instead of hardcoding keys or relying on environment variables.

### 1. Retrieving API Keys in Plugins

```python
from app.services.system_config_service import SystemConfigService

class ShodanPlugin(BasePlugin):
    """Example plugin that uses Shodan API"""

    def __init__(self):
        super().__init__(display_name="Shodan Search")
        self.description = "Search for hosts and services using Shodan"
        self.category = "Network"
        self.evidence_category = "Network Assets"
        # No need to define API key parameters - handled centrally

    async def run(self, params: Optional[Dict[str, Any]] = None) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute Shodan search"""
        # Get database session (this should be passed in via dependency injection in practice)
        from app.core.dependencies import get_db
        db = next(get_db())
        
        try:
            # Retrieve API key using the centralized system
            config_service = SystemConfigService(db)
            shodan_api_key = config_service.get_api_key("shodan")
            
            if not shodan_api_key:
                yield {
                    "type": "error", 
                    "data": {"message": "Shodan API key not configured. Please add it in Admin → Configuration → API Keys"}
                }
                return

            # Use the API key for your service
            import shodan
            api = shodan.Shodan(shodan_api_key)
            
            # Your plugin logic here...
            query = params.get("query", "")
            results = api.search(query)
            
            for result in results['matches']:
                yield {
                    "type": "data",
                    "data": {
                        "ip": result.get("ip_str"),
                        "port": result.get("port"),
                        "organization": result.get("org"),
                        "location": result.get("location", {}).get("country_name"),
                        "timestamp": result.get("timestamp")
                    }
                }
                
        except Exception as e:
            yield {
                "type": "error",
                "data": {"message": f"Shodan API error: {str(e)}"}
            }
        finally:
            db.close()
```

### 2. Supported API Key Providers

The system supports any API provider. Common examples:
- `openai` - OpenAI GPT APIs
- `anthropic` - Claude APIs  
- `shodan` - Shodan search API
- `virustotal` - VirusTotal API
- `censys` - Censys search API
- `hunter` - Hunter.io email finder
- `haveibeenpwned` - Have I Been Pwned API
- `whoisxml` - WhoisXML API

### 3. API Key Configuration

**For Administrators**: API keys are configured through the admin interface at:
- **Web UI**: Admin Dashboard → Configuration → API Keys
- **API Endpoints**: 
  - `PUT /api/admin/configuration/api-keys/{provider}` - Set/update key
  - `GET /api/admin/configuration/api-keys` - List configured keys
  - `DELETE /api/admin/configuration/api-keys/{provider}` - Remove key

**For Plugin Users**: If a plugin requires an API key that isn't configured, it will show a clear error message directing them to the admin configuration.

### 4. Environment Variable Fallback

The system automatically falls back to environment variables if no database key is configured:
- `SHODAN_API_KEY` → `shodan` provider
- `OPENAI_API_KEY` → `openai` provider  
- `VIRUSTOTAL_API_KEY` → `virustotal` provider

### 5. Best Practices for API Key Usage

```python
async def run(self, params: Optional[Dict[str, Any]] = None) -> AsyncGenerator[Dict[str, Any], None]:
    # ✅ GOOD: Use centralized API key system
    config_service = SystemConfigService(db)
    api_key = config_service.get_api_key("provider_name")
    
    if not api_key:
        yield {
            "type": "error", 
            "data": {"message": "Provider API key not configured. Please add it in Admin → Configuration → API Keys"}
        }
        return
    
    # ❌ BAD: Hardcoded API keys
    # api_key = "sk-hardcoded-key-123"
    
    # ❌ BAD: Direct environment variable access
    # api_key = os.environ.get("PROVIDER_API_KEY")
    
    # Use the API key...
```

### 6. Security Features

- **Encryption**: All API keys are encrypted at rest using Fernet encryption
- **Admin-only access**: Only admin users can view/modify API keys
- **Secure transport**: Keys are never exposed in logs or API responses
- **Environment fallback**: Graceful fallback to environment variables for backward compatibility

### 7. Plugin Development Workflow

1. **Develop your plugin** using the centralized API key system
2. **Test locally** by setting environment variables or using the admin interface
3. **Document required API keys** in your plugin's docstring or description
4. **Provide clear error messages** when API keys are missing

### Example Plugin with Multiple API Keys

```python
class MultiServicePlugin(BasePlugin):
    """Plugin that uses multiple external APIs"""
    
    async def run(self, params: Optional[Dict[str, Any]] = None) -> AsyncGenerator[Dict[str, Any], None]:
        config_service = SystemConfigService(db)
        
        # Check multiple API keys
        required_keys = {
            "shodan": "Shodan API key",
            "virustotal": "VirusTotal API key"
        }
        
        missing_keys = []
        api_keys = {}
        
        for provider, description in required_keys.items():
            key = config_service.get_api_key(provider)
            if not key:
                missing_keys.append(f"{description} ({provider})")
            else:
                api_keys[provider] = key
        
        if missing_keys:
            yield {
                "type": "error",
                "data": {
                    "message": f"Missing API keys: {', '.join(missing_keys)}. "
                              "Please configure them in Admin → Configuration → API Keys"
                }
            }
            return
        
        # Use the API keys...
        # Your multi-service logic here
```

## Examples

Study these existing plugins for reference:
- **Simple API Plugin**: `holehe_plugin.py` - Direct library usage with automatic evidence saving
- **DNS Tool Plugin**: `dnslookup_plugin.py` - Network tools with mode selection using default evidence format
- **Database Plugin**: `correlation_plugin.py` - Case analysis with custom evidence formatting

## Troubleshooting

### Plugin Not Appearing
- Check file naming: `*_plugin.py` in `/backend/app/plugins/`
- Ensure class inherits from `BasePlugin`
- Restart backend container: `docker compose restart backend`

### Frontend Components Not Loading
- Check naming: `{PluginName}PluginParams.vue` and `{PluginName}PluginResult.vue`
- Ensure correct path: `/frontend/src/components/plugins/`
- Check browser console for import errors

### Dependencies Not Available
- Add to `requirements.txt`
- Install in container: `docker compose exec backend pip install package-name`
- For persistent dependencies, rebuild container

---

**Remember**: The plugin system is designed for flexibility. Start simple and iterate based on your tool's specific needs!

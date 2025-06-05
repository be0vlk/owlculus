# Plugin Development Guide

## Plugin Architecture Overview

Owlculus uses a plugin system that consists of:
- **Backend Plugin**: Python class that handles the actual tool execution
- **Frontend Parameter Component**: Vue component for user input (optional but recommended)
- **Frontend Result Component**: Vue component for displaying results (optional but recommended)

The system automatically discovers and loads plugins based on naming conventions.

## Backend Plugin Development

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

### 6. Dependencies
Add any required packages to `/backend/requirements.txt`:
```txt
your-package-name==version
```

## Frontend Components (Optional but Recommended)

### 1. Parameter Component

**Location**: `/frontend/src/components/plugins/YourPluginNamePluginParams.vue`

```vue
<template>
  <div class="d-flex flex-column ga-3">
    <!-- About card with plugin description (always at top) -->
    <v-card
      v-if="pluginDescription"
      color="blue-lighten-5"
      elevation="0"
      rounded="lg"
      class="pa-3"
    >
      <div class="d-flex align-center ga-2 mb-2">
        <v-icon color="blue">mdi-information</v-icon>
        <span class="text-subtitle2 font-weight-medium">About</span>
      </div>
      <p class="text-body-2 mb-0">
        {{ pluginDescription }}
      </p>
    </v-card>

    <!-- Input fields -->
    <v-text-field
      v-model="localParams.your_param"
      label="Your Parameter"
      placeholder="Enter value"
      variant="outlined"
      density="compact"
      @update:model-value="updateParams"
    />
  </div>
</template>

<script setup>
import { reactive, watch, computed } from 'vue'

const props = defineProps({
  parameters: {
    type: Object,
    required: true
  },
  modelValue: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['update:modelValue'])

// Extract plugin description from parameters
const pluginDescription = computed(() => props.parameters?.description)

// Local parameter state
const localParams = reactive({
  your_param: props.modelValue.your_param || '',
})

// Emit parameter updates
const updateParams = () => {
  emit('update:modelValue', { ...localParams })
}

// Watch for external changes
watch(() => props.modelValue, (newValue) => {
  Object.assign(localParams, newValue)
}, { deep: true })
</script>
```

### 2. Result Component

**Location**: `/frontend/src/components/plugins/YourPluginNamePluginResult.vue`

```vue
<template>
  <div class="d-flex flex-column ga-4">
    <template v-for="(item, index) in parsedResults" :key="index">
      <!-- Data Results -->
      <v-card v-if="item.type === 'data'" elevation="2" rounded="lg">
        <v-card-title class="d-flex align-center">
          <v-icon icon="mdi-your-icon" class="mr-2" />
          {{ item.data.title }}
        </v-card-title>
        <v-card-text>
          <!-- Display your results here -->
          <div>{{ item.data.result_field }}</div>
          
          <!-- Copy functionality -->
          <v-btn
            icon="mdi-content-copy"
            size="small"
            variant="text"
            @click="copyToClipboard(item.data.result_field)"
          >
            <v-tooltip activator="parent">Copy result</v-tooltip>
          </v-btn>
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

const copyToClipboard = async (text) => {
  try {
    await navigator.clipboard.writeText(text)
  } catch (err) {
    console.error('Failed to copy text:', err)
  }
}
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

### 1. Create Backend Plugin
```bash
# 1. Add dependencies to requirements.txt
echo "your-tool==1.0.0" >> backend/requirements.txt

# 2. Create plugin file
touch backend/app/plugins/mytool_plugin.py

# 3. Implement plugin class (see structure above)

# 4. Install dependencies in container
docker compose exec backend pip install your-tool
```

### 2. Create Frontend Components (Optional)
```bash
# Create parameter component
touch frontend/src/components/plugins/MytoolPluginParams.vue

# Create result component  
touch frontend/src/components/plugins/MytoolPluginResult.vue
```

### 3. Test Plugin
```bash
# Restart backend to load new plugin
docker compose restart backend

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
- **Follow Vuetify patterns** for consistent UI
- **Always place About card at top** of parameter components
- **Provide clear parameter labels** and placeholders
- **Include validation** for required fields
- **Show copy functionality** for useful data
- **Handle empty results** gracefully
- **Use appropriate icons** from Material Design Icons

### Security
- **Never log sensitive data** (API keys, passwords)
- **Validate input parameters** properly
- **Use proper error handling** to avoid exposing system information
- **Follow principle of least privilege** for external tool access

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

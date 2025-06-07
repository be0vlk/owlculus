#!/usr/bin/env python3
"""
Owlculus Plugin Generator Script

This script helps developers quickly create new plugins by generating:
- Backend plugin file with proper structure
- Frontend parameter component (Vue)
- Frontend result component (Vue)

Usage:
    python scripts/create_plugin.py <plugin_name> [options]

Example:
    python scripts/create_plugin.py whois --category Network --evidence-category "Network Assets"
"""

import os
import sys
import argparse
import re
from typing import Dict, Any
from pathlib import Path


# ANSI color codes for terminal output
class Colors:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    END = "\033[0m"


# Valid categories as defined in the plugin documentation
UI_CATEGORIES = ["Person", "Network", "Company", "Other"]
EVIDENCE_CATEGORIES = [
    "Social Media",
    "Associates",
    "Network Assets",
    "Communications",
    "Documents",
    "Other",
]


def snake_to_pascal(name: str) -> str:
    """Convert snake_case to PascalCase"""
    return "".join(word.capitalize() for word in name.split("_"))


def pascal_to_title(name: str) -> str:
    """Convert PascalCase to Title Case"""
    # Insert spaces before uppercase letters (except the first one)
    result = re.sub(r"(?<!^)(?=[A-Z])", " ", name)
    return result


def generate_backend_plugin(config: Dict[str, Any]) -> str:
    """Generate the backend plugin Python file content"""

    template = f'''"""
{config['description']}
"""

import asyncio
from typing import AsyncGenerator, Dict, Any, Optional
from .base_plugin import BasePlugin

class {config['class_name']}Plugin(BasePlugin):
    """{config['description']}"""

    def __init__(self):
        super().__init__(display_name="{config['display_name']}")
        self.description = "{config['description']}"
        self.category = "{config['category']}"  # {', '.join(UI_CATEGORIES)}
        self.evidence_category = "{config['evidence_category']}"  # {', '.join(EVIDENCE_CATEGORIES)}
        self.save_to_case = False  # Whether to auto-save results as evidence
        self.parameters = {{
            # TODO: Define your plugin parameters here
            "target": {{
                "type": "string",
                "description": "Target to analyze",
                "required": True,
            }},
            "timeout": {{
                "type": "float",
                "description": "Operation timeout in seconds",
                "default": 30.0,
                "required": False,
            }},
            # Note: save_to_case parameter is automatically added by BasePlugin
        }}

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
        if not params or "target" not in params:
            yield {{"type": "error", "data": {{"message": "Target parameter is required"}}}}
            return

        # Extract parameters
        target = params["target"]
        timeout = params.get("timeout", 30.0)

        # TODO: Implement your plugin logic here
        # Example: API calls, tool execution, data processing
        
        # Example: Simulate some work
        await asyncio.sleep(0.5)
        
        # Yield results as they become available
        yield {{
            "type": "data",
            "data": {{
                "target": target,
                "status": "analyzed",
                "findings": [
                    # TODO: Add your actual findings here
                    {{"type": "info", "description": "Example finding"}},
                ],
                "timestamp": asyncio.get_event_loop().time(),
            }},
        }}

        # Example: Yield additional results
        # yield {{
        #     "type": "data",
        #     "data": {{
        #         "additional_info": "More results...",
        #     }},
        # }}

        # Evidence saving is handled automatically by BasePlugin
        # No manual implementation needed - just yield data results

    # Optional: Override this method for custom evidence formatting
    # def _format_evidence_content(self, results: List[Dict[str, Any]], params: Dict[str, Any]) -> str:
    #     """Custom formatting for evidence content"""
    #     content_lines = [
    #         f"{{self.display_name}} Investigation Results",
    #         "=" * 50,
    #         "",
    #         f"Target: {{params.get('target', 'Unknown')}}",
    #         f"Total findings: {{len(results)}}",
    #         "",
    #     ]
    #     
    #     for i, result in enumerate(results, 1):
    #         content_lines.extend([
    #             f"Finding #{{i}}:",
    #             f"  Description: {{result.get('description', 'N/A')}}",
    #             f"  Confidence: {{result.get('confidence', 'Unknown')}}",
    #             "",
    #         ])
    #     
    #     return "\\n".join(content_lines)
'''

    return template


def generate_params_component(config: Dict[str, Any]) -> str:
    """Generate the frontend parameter component Vue file content"""

    template = f"""<template>
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
        {{{{ pluginDescription }}}}
      </p>
    </v-card>

    <!-- TODO: Add your input fields here -->
    <v-text-field
      v-model="localParams.target"
      label="Target"
      placeholder="Enter target to analyze"
      variant="outlined"
      density="compact"
      :rules="[v => !!v || 'Target is required']"
      @update:model-value="updateParams"
    />

    <v-text-field
      v-model.number="localParams.timeout"
      label="Timeout (seconds)"
      placeholder="30"
      variant="outlined"
      density="compact"
      type="number"
      @update:model-value="updateParams"
    />
  </div>
</template>

<script setup>
import {{ reactive, watch, computed }} from 'vue'

const props = defineProps({{
  parameters: {{
    type: Object,
    required: true
  }},
  modelValue: {{
    type: Object,
    required: true
  }}
}})

const emit = defineEmits(['update:modelValue'])

// Extract plugin description from parameters
const pluginDescription = computed(() => props.parameters?.description)

// Local parameter state
const localParams = reactive({{
  target: props.modelValue.target || '',
  timeout: props.modelValue.timeout || 30,
}})

// Emit parameter updates
const updateParams = () => {{
  emit('update:modelValue', {{ ...localParams }})
}}

// Watch for external changes
watch(() => props.modelValue, (newValue) => {{
  Object.assign(localParams, newValue)
}}, {{ deep: true }})
</script>
"""

    return template


def generate_result_component(config: Dict[str, Any]) -> str:
    """Generate the frontend result component Vue file content"""

    icon = "mdi-magnify"
    if config["category"] == "Person":
        icon = "mdi-account"
    elif config["category"] == "Network":
        icon = "mdi-lan"
    elif config["category"] == "Company":
        icon = "mdi-domain"

    template = f"""<template>
  <div class="d-flex flex-column ga-4">
    <template v-for="(item, index) in parsedResults" :key="index">
      <!-- Data Results -->
      <v-card v-if="item.type === 'data'" elevation="2" rounded="lg">
        <v-card-title class="d-flex align-center">
          <v-icon icon="{icon}" class="mr-2" />
          {{{{ item.data.target || '{config['display_name']} Results' }}}}
        </v-card-title>
        <v-card-text>
          <!-- TODO: Customize how your results are displayed -->
          <div v-if="item.data.status" class="mb-3">
            <span class="text-subtitle2">Status:</span>
            <span class="ml-2">{{{{ item.data.status }}}}</span>
          </div>
          
          <!-- Display findings if available -->
          <div v-if="item.data.findings && item.data.findings.length">
            <p class="text-subtitle2 mb-2">Findings:</p>
            <v-list density="compact" class="pa-0">
              <v-list-item
                v-for="(finding, fIndex) in item.data.findings"
                :key="fIndex"
                class="px-0"
              >
                <v-list-item-title>
                  <v-icon size="small" class="mr-2">mdi-chevron-right</v-icon>
                  {{{{ finding.description }}}}
                </v-list-item-title>
              </v-list-item>
            </v-list>
          </div>
          
          <!-- Copy functionality for important data -->
          <div v-if="item.data.target" class="d-flex align-center mt-3">
            <v-btn
              icon="mdi-content-copy"
              size="small"
              variant="text"
              @click="copyToClipboard(item.data.target)"
            >
              <v-tooltip activator="parent">Copy target</v-tooltip>
            </v-btn>
          </div>
          
          <!-- Raw data view (for development/debugging) -->
          <v-expansion-panels v-if="showRawData" class="mt-3">
            <v-expansion-panel>
              <v-expansion-panel-title>
                <span class="text-caption">Raw Data</span>
              </v-expansion-panel-title>
              <v-expansion-panel-text>
                <pre class="text-caption">{{{{ JSON.stringify(item.data, null, 2) }}}}</pre>
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>
        </v-card-text>
      </v-card>

      <!-- Error Messages -->
      <v-alert
        v-else-if="item.type === 'error'"
        type="error"
        variant="outlined"
      >
        {{{{ item.data.message }}}}
      </v-alert>
    </template>

    <!-- No Results -->
    <v-card v-if="!parsedResults.length" elevation="2" rounded="lg">
      <v-card-text class="text-center pa-8">
        <v-icon icon="{icon}" size="48" color="grey-darken-1" class="mb-3" />
        <p class="text-body-2 text-medium-emphasis">
          No results available.
        </p>
      </v-card-text>
    </v-card>
  </div>
</template>

<script setup>
import {{ computed, ref }} from 'vue'

const props = defineProps({{
  result: {{
    type: [Object, Array],
    required: true,
  }}
}})

// Toggle for showing raw data (useful during development)
const showRawData = ref(false)

// Parse streaming results
const parsedResults = computed(() => {{
  if (!props.result) return []
  
  if (Array.isArray(props.result)) {{
    return props.result
  }}
  
  if (props.result.type) {{
    return [props.result]
  }}
  
  return []
}})

const copyToClipboard = async (text) => {{
  try {{
    await navigator.clipboard.writeText(text)
  }} catch (err) {{
    console.error('Failed to copy text:', err)
  }}
}}
</script>
"""

    return template


def create_plugin(args):
    """Main function to create plugin files"""

    # Prepare configuration
    config = {
        "name": args.name.lower().replace("-", "_"),
        "class_name": snake_to_pascal(args.name.lower().replace("-", "_")),
        "display_name": args.display_name
        or pascal_to_title(snake_to_pascal(args.name)),
        "description": args.description,
        "category": args.category,
        "evidence_category": args.evidence_category,
    }

    # Define file paths
    project_root = Path(__file__).parent.parent
    backend_path = (
        project_root / "backend" / "app" / "plugins" / f"{config['name']}_plugin.py"
    )
    params_path = (
        project_root
        / "frontend"
        / "src"
        / "components"
        / "plugins"
        / f"{config['class_name']}PluginParams.vue"
    )
    result_path = (
        project_root
        / "frontend"
        / "src"
        / "components"
        / "plugins"
        / f"{config['class_name']}PluginResult.vue"
    )
    test_path = (
        project_root
        / "backend"
        / "tests"
        / "plugins"
        / f"test_{config['name']}_plugin.py"
    )

    # Check if files already exist
    if not args.force:
        existing_files = []
        if backend_path.exists():
            existing_files.append(str(backend_path))
        if not args.backend_only:
            if params_path.exists():
                existing_files.append(str(params_path))
            if result_path.exists():
                existing_files.append(str(result_path))
        if args.generate_tests and test_path.exists():
            existing_files.append(str(test_path))

        if existing_files:
            print(f"{Colors.RED}ERROR:{Colors.END} The following files already exist:")
            for f in existing_files:
                print(f"   - {f}")
            print(
                f"\n{Colors.YELLOW}Use --force to overwrite existing files{Colors.END}"
            )
            sys.exit(1)

    # Generate file contents
    backend_content = generate_backend_plugin(config)
    params_content = generate_params_component(config)
    result_content = generate_result_component(config)
    test_content = generate_test_file(config) if args.generate_tests else None

    # Create files
    try:
        # Write backend plugin
        backend_path.parent.mkdir(parents=True, exist_ok=True)
        with open(backend_path, "w") as f:
            f.write(backend_content)
        print(
            f"{Colors.GREEN}SUCCESS:{Colors.END} Created backend plugin: {backend_path}"
        )

        # Write frontend components if requested
        if not args.backend_only:
            params_path.parent.mkdir(parents=True, exist_ok=True)
            with open(params_path, "w") as f:
                f.write(params_content)
            print(
                f"{Colors.GREEN}SUCCESS:{Colors.END} Created parameter component: {params_path}"
            )

            with open(result_path, "w") as f:
                f.write(result_content)
            print(
                f"{Colors.GREEN}SUCCESS:{Colors.END} Created result component: {result_path}"
            )

        # Write test file if requested
        if args.generate_tests and test_content:
            test_path.parent.mkdir(parents=True, exist_ok=True)
            with open(test_path, "w") as f:
                f.write(test_content)
            print(f"{Colors.GREEN}SUCCESS:{Colors.END} Created test file: {test_path}")

        # Add dependencies to requirements.txt
        if args.dependencies:
            add_dependencies_to_requirements(args.dependencies)

        # Print next steps
        print(
            f"\n{Colors.GREEN}{Colors.BOLD}Plugin '{config['display_name']}' created successfully!{Colors.END}"
        )
        print(f"\n{Colors.CYAN}Next steps:{Colors.END}")
        print(f"1. Implement your plugin logic in: {backend_path}")
        if not args.backend_only:
            print(f"2. Customize the parameter UI in: {params_path}")
            print(f"3. Customize the result display in: {result_path}")
        if args.generate_tests:
            print(
                f"{'4' if args.backend_only else '4'}. Complete the test implementation in: {test_path}"
            )

        next_step = "5" if args.backend_only else ("5" if args.generate_tests else "4")
        if args.dependencies:
            print(
                f"{next_step}. Install dependencies: docker compose exec backend pip install {' '.join(args.dependencies)}"
            )
            next_step = str(int(next_step) + 1)
        else:
            print(
                f"{next_step}. Add any required dependencies to: backend/requirements.txt"
            )
            next_step = str(int(next_step) + 1)

        print(
            f"{next_step}. Restart the backend container: docker compose restart backend"
        )
        print(f"{str(int(next_step) + 1)}. Test your plugin in the Plugins dashboard")

        if args.backend_only:
            print(
                f"\n{Colors.YELLOW}TIP:{Colors.END} The plugin will work without frontend components, but parameters"
            )
            print(
                "   will be shown as raw JSON input and results as formatted JSON output."
            )

        if args.generate_tests:
            print(
                f"\n{Colors.YELLOW}TIP:{Colors.END} Run tests with: docker compose exec backend pytest {test_path}"
            )

    except Exception as e:
        print(f"{Colors.RED}ERROR:{Colors.END} Error creating plugin files: {e}")
        sys.exit(1)


def add_dependencies_to_requirements(dependencies):
    """Add dependencies to requirements.txt file"""
    if not dependencies:
        return

    project_root = Path(__file__).parent.parent
    requirements_path = project_root / "backend" / "requirements.txt"

    try:
        # Read existing requirements
        existing_deps = set()
        if requirements_path.exists():
            with open(requirements_path, "r") as f:
                existing_deps = {
                    line.strip().split("==")[0].split(">=")[0].split("<=")[0]
                    for line in f
                    if line.strip() and not line.startswith("#")
                }

        # Add new dependencies
        new_deps = []
        for dep in dependencies:
            dep = dep.strip()
            if dep and dep not in existing_deps:
                new_deps.append(dep)

        if new_deps:
            with open(requirements_path, "a") as f:
                f.write("\n")
                for dep in new_deps:
                    f.write(f"{dep}\n")

            print(
                f"{Colors.GREEN}SUCCESS:{Colors.END} Added dependencies to requirements.txt: {', '.join(new_deps)}"
            )
        else:
            print(
                f"{Colors.YELLOW}INFO:{Colors.END} All dependencies already exist in requirements.txt"
            )

    except Exception as e:
        print(f"{Colors.RED}ERROR:{Colors.END} Failed to update requirements.txt: {e}")


def generate_test_file(config: Dict[str, Any]) -> str:
    """Generate a basic test file for the plugin"""

    template = f'''"""
Tests for {config['display_name']} plugin
"""

import pytest
from unittest.mock import AsyncMock, patch
from app.plugins.{config['name']}_plugin import {config['class_name']}Plugin

class Test{config['class_name']}Plugin:
    """Test cases for {config['class_name']}Plugin"""

    @pytest.fixture
    def plugin(self):
        """Create plugin instance for testing"""
        return {config['class_name']}Plugin()

    def test_plugin_initialization(self, plugin):
        """Test plugin initializes correctly"""
        assert plugin.display_name == "{config['display_name']}"
        assert plugin.description == "{config['description']}"
        assert plugin.category == "{config['category']}"
        assert plugin.evidence_category == "{config['evidence_category']}"
        assert "save_to_case" in plugin.parameters

    def test_plugin_parameters(self, plugin):
        """Test plugin parameters are defined correctly"""
        # TODO: Add specific parameter validation tests
        assert isinstance(plugin.parameters, dict)
        # Example: assert "domain" in plugin.parameters
        # Example: assert plugin.parameters["domain"]["required"] is True

    @pytest.mark.asyncio
    async def test_plugin_run_missing_params(self, plugin):
        """Test plugin handles missing parameters correctly"""
        results = []
        async for result in plugin.run(None):
            results.append(result)
        
        assert len(results) == 1
        assert results[0]["type"] == "error"
        assert "required" in results[0]["data"]["message"].lower()

    @pytest.mark.asyncio
    async def test_plugin_run_empty_params(self, plugin):
        """Test plugin handles empty parameters correctly"""
        results = []
        async for result in plugin.run({{}}):
            results.append(result)
        
        assert len(results) == 1
        assert results[0]["type"] == "error"

    @pytest.mark.asyncio
    async def test_plugin_run_valid_params(self, plugin):
        """Test plugin with valid parameters"""
        # TODO: Implement test with valid parameters
        # Example:
        # params = {{"domain": "example.com", "timeout": 10}}
        # results = []
        # async for result in plugin.run(params):
        #     results.append(result)
        # 
        # assert len(results) >= 1
        # Check for successful results or expected behavior
        pass

    @pytest.mark.asyncio 
    async def test_plugin_run_timeout(self, plugin):
        """Test plugin handles timeout correctly"""
        # TODO: Implement timeout test if applicable
        # This might involve mocking the underlying service/API
        pass

    @pytest.mark.asyncio
    async def test_plugin_run_service_error(self, plugin):
        """Test plugin handles service errors gracefully"""
        # TODO: Mock service errors and test error handling
        # Example:
        # with patch('whois.whois', side_effect=Exception("Service error")):
        #     params = {{"domain": "example.com"}}
        #     results = []
        #     async for result in plugin.run(params):
        #         results.append(result)
        #     
        #     assert any(r["type"] == "error" for r in results)
        pass

    def test_format_evidence_content(self, plugin):
        """Test evidence formatting"""
        # TODO: Test evidence content formatting
        # Example results and parameters
        results = [
            # Add sample result data based on your plugin's output format
        ]
        params = {{
            # Add sample parameters
        }}
        
        # Test that formatting doesn't crash
        if hasattr(plugin, '_format_evidence_content'):
            content = plugin._format_evidence_content(results, params)
            assert isinstance(content, str)
            assert len(content) > 0

    def test_plugin_metadata(self, plugin):
        """Test plugin metadata is properly set"""
        assert plugin.display_name
        assert plugin.description  
        assert plugin.category in ["Person", "Network", "Company", "Other"]
        assert plugin.evidence_category in [
            "Social Media", "Associates", "Network Assets", 
            "Communications", "Documents", "Other"
        ]
'''

    return template


def interactive_mode():
    """Interactive mode for creating plugins"""
    print(f"{Colors.CYAN}{Colors.BOLD}Owlculus Plugin Generator{Colors.END}")
    print(f"{Colors.CYAN}{'=' * 40}{Colors.END}")
    print()

    # Get plugin name
    while True:
        name = input("Enter plugin name (e.g., whois, port_scanner): ").strip()
        if not name:
            print(f"{Colors.RED}ERROR:{Colors.END} Plugin name is required")
            continue
        if not re.match(r"^[a-z][a-z0-9_-]*$", name.lower()):
            print(
                f"{Colors.RED}ERROR:{Colors.END} Plugin name must start with a letter and contain only"
            )
            print("   lowercase letters, numbers, underscores, or hyphens")
            continue
        break

    # Get display name
    default_display = pascal_to_title(snake_to_pascal(name.lower().replace("-", "_")))
    display_name = input(f"Display name [{default_display}]: ").strip()
    if not display_name:
        display_name = default_display

    # Get description
    description = input("Brief description: ").strip()
    if not description:
        description = "Brief description of what this plugin does"

    # Get UI category
    print(f"\nUI Categories:")
    for i, cat in enumerate(UI_CATEGORIES, 1):
        print(f"  {i}. {cat}")

    while True:
        try:
            choice = input(
                f"Select UI category [1-{len(UI_CATEGORIES)}] (default: 4): "
            ).strip()
            if not choice:
                category = "Other"
                break
            idx = int(choice) - 1
            if 0 <= idx < len(UI_CATEGORIES):
                category = UI_CATEGORIES[idx]
                break
            else:
                print(
                    f"{Colors.RED}ERROR:{Colors.END} Please enter a number between 1 and {len(UI_CATEGORIES)}"
                )
        except ValueError:
            print(f"{Colors.RED}ERROR:{Colors.END} Please enter a valid number")

    # Get evidence category
    print(f"\nEvidence Categories:")
    for i, cat in enumerate(EVIDENCE_CATEGORIES, 1):
        print(f"  {i}. {cat}")

    while True:
        try:
            choice = input(
                f"Select evidence category [1-{len(EVIDENCE_CATEGORIES)}] (default: 6): "
            ).strip()
            if not choice:
                evidence_category = "Other"
                break
            idx = int(choice) - 1
            if 0 <= idx < len(EVIDENCE_CATEGORIES):
                evidence_category = EVIDENCE_CATEGORIES[idx]
                break
            else:
                print(
                    f"{Colors.RED}ERROR:{Colors.END} Please enter a number between 1 and {len(EVIDENCE_CATEGORIES)}"
                )
        except ValueError:
            print(f"{Colors.RED}ERROR:{Colors.END} Please enter a valid number")

    # Backend only option
    backend_only_input = input("\nCreate backend only? (y/N): ").strip().lower()
    backend_only = backend_only_input in ["y", "yes"]

    # Dependencies
    print(f"\n{Colors.CYAN}Dependencies:{Colors.END}")
    dependencies_input = input(
        "Required Python packages (comma-separated, or press Enter to skip): "
    ).strip()
    dependencies = (
        [dep.strip() for dep in dependencies_input.split(",") if dep.strip()]
        if dependencies_input
        else []
    )

    # Generate tests
    generate_tests_input = input("Generate test file? (Y/n): ").strip().lower()
    generate_tests = generate_tests_input not in ["n", "no"]

    # Force overwrite option
    force_input = input("Force overwrite existing files? (y/N): ").strip().lower()
    force = force_input in ["y", "yes"]

    # Create args object
    class Args:
        def __init__(self):
            self.name = name
            self.display_name = display_name
            self.description = description
            self.category = category
            self.evidence_category = evidence_category
            self.backend_only = backend_only
            self.force = force
            self.dependencies = dependencies
            self.generate_tests = generate_tests

    return Args()


def main():
    parser = argparse.ArgumentParser(
        description="Create a new Owlculus plugin with proper templates",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Interactive Mode (default):
  python scripts/create_plugin.py

Command Line Mode:
  # Create a simple plugin
  python scripts/create_plugin.py whois

  # Create a network category plugin with dependencies
  python scripts/create_plugin.py port_scanner --category Network --evidence-category "Network Assets" --dependencies "python-nmap,requests"

  # Create backend-only plugin (no frontend components)
  python scripts/create_plugin.py api_checker --backend-only --no-tests

  # Create plugin with dependencies and tests
  python scripts/create_plugin.py whois --dependencies "python-whois" 

  # Override existing files
  python scripts/create_plugin.py whois --force
        """,
    )

    parser.add_argument(
        "name",
        nargs="?",
        help="Plugin name (snake_case or kebab-case, e.g., whois, port_scanner, api-lookup)",
    )

    parser.add_argument(
        "--display-name",
        help="Human-readable display name (default: auto-generated from name)",
    )

    parser.add_argument(
        "--description",
        default="Brief description of what this plugin does",
        help="Plugin description (default: placeholder text)",
    )

    parser.add_argument(
        "--category",
        choices=UI_CATEGORIES,
        default="Other",
        help=f"UI category for plugin organization (default: Other)",
    )

    parser.add_argument(
        "--evidence-category",
        choices=EVIDENCE_CATEGORIES,
        default="Other",
        help=f"Evidence storage category (default: Other)",
    )

    parser.add_argument(
        "--backend-only",
        action="store_true",
        help="Only create backend plugin file (skip frontend components)",
    )

    parser.add_argument("--force", action="store_true", help="Overwrite existing files")

    parser.add_argument(
        "--dependencies", help="Required Python packages (comma-separated)"
    )

    parser.add_argument(
        "--no-tests", action="store_true", help="Skip generating test file"
    )

    args = parser.parse_args()

    # If no name provided, use interactive mode
    if not args.name:
        args = interactive_mode()
    else:
        # Validate plugin name for command line mode
        if not re.match(r"^[a-z][a-z0-9_-]*$", args.name.lower()):
            print(
                f"{Colors.RED}ERROR:{Colors.END} Plugin name must start with a letter and contain only"
            )
            print("   lowercase letters, numbers, underscores, or hyphens")
            sys.exit(1)

        # Add missing attributes for command line mode
        args.dependencies = (
            [dep.strip() for dep in args.dependencies.split(",") if dep.strip()]
            if args.dependencies
            else []
        )
        args.generate_tests = not args.no_tests

    create_plugin(args)


if __name__ == "__main__":
    main()

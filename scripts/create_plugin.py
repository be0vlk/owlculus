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

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict


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


def print_status(level: str, message: str) -> None:
    """Print a colored status message"""
    color_map = {
        "error": Colors.RED,
        "success": Colors.GREEN,
        "warning": Colors.YELLOW,
        "info": Colors.CYAN,
        "header": f"{Colors.CYAN}{Colors.BOLD}",
    }
    color = color_map.get(level, "")
    prefix = level.upper() + ":" if level in ["error", "success", "warning"] else ""
    print(
        f"{color}{prefix}{Colors.END} {message}"
        if prefix
        else f"{color}{message}{Colors.END}"
    )


def get_plugin_file_paths(config: Dict[str, Any]) -> Dict[str, Path]:
    """Generate all file paths for the plugin"""
    project_root = Path(__file__).parent.parent
    return {
        "backend": project_root
        / "backend"
        / "app"
        / "plugins"
        / f"{config['name']}_plugin.py",
        "params": project_root
        / "frontend"
        / "src"
        / "components"
        / "plugins"
        / f"{config['class_name']}PluginParams.vue",
        "result": project_root
        / "frontend"
        / "src"
        / "components"
        / "plugins"
        / f"{config['class_name']}PluginResult.vue",
        "test": project_root
        / "backend"
        / "tests"
        / "plugins"
        / f"test_{config['name']}_plugin.py",
    }


def validate_file_conflicts(file_paths: Dict[str, Path], args) -> None:
    """Check for existing files and handle conflicts"""
    if args.force:
        return

    existing_files = []

    # Always check backend
    if file_paths["backend"].exists():
        existing_files.append(str(file_paths["backend"]))

    # Check frontend components if not backend-only
    if not args.backend_only:
        for key in ["params", "result"]:
            if file_paths[key].exists():
                existing_files.append(str(file_paths[key]))

    # Check test file if generating tests
    if args.generate_tests and file_paths["test"].exists():
        existing_files.append(str(file_paths["test"]))

    if existing_files:
        print_status("error", "The following files already exist:")
        for f in existing_files:
            print(f"   - {f}")
        print_status("warning", "Use --force to overwrite existing files")
        sys.exit(1)


def write_files_safely(file_contents_map: Dict[Path, str]) -> None:
    """Write multiple files safely with error handling"""
    written_files = []
    try:
        for file_path, content in file_contents_map.items():
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w") as f:
                f.write(content)
            written_files.append(file_path)

            # Determine file type for appropriate message
            if "_plugin.py" in file_path.name:
                file_type = "backend plugin"
            elif "Params.vue" in file_path.name:
                file_type = "parameter component"
            elif "Result.vue" in file_path.name:
                file_type = "result component"
            elif "test_" in file_path.name:
                file_type = "test file"
            else:
                file_type = "file"

            print_status("success", f"Created {file_type}: {file_path}")

    except Exception as e:
        print_status("error", f"Error creating plugin files: {e}")
        # Clean up any files that were written
        for written_file in written_files:
            try:
                written_file.unlink()
            except:
                pass
        sys.exit(1)


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

    # Add API key requirements if specified
    api_key_line = ""
    if config.get("api_keys"):
        api_key_list = ", ".join(f'"{key}"' for key in config["api_keys"])
        api_key_line = f"\n        self.api_key_requirements = [{api_key_list}]  # Required API key providers"

    # Simplified API key checking template
    api_key_check = """        # Check API key requirements if any are defined
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
                return"""

    template = f'''"""
{config['description']}
"""

import asyncio
from typing import AsyncGenerator, Dict, Any, Optional
from sqlmodel import Session
from .base_plugin import BasePlugin

class {config['class_name']}Plugin(BasePlugin):
    """{config['description']}"""

    def __init__(self, db_session: Session = None):
        super().__init__(display_name="{config['display_name']}", db_session=db_session)
        self.description = "{config['description']}"
        self.category = "{config['category']}"  # {', '.join(UI_CATEGORIES)}
        self.evidence_category = "{config['evidence_category']}"  # {', '.join(EVIDENCE_CATEGORIES)}
        self.save_to_case = False  # Whether to auto-save results as evidence{api_key_line}
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

{api_key_check}

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
    """Generate a minimal parameter component that just uses GenericPluginParams"""

    template = f"""<template>
  <!-- This plugin uses the automatic GenericPluginParams component -->
  <!-- No custom parameter component needed unless you have special UI requirements -->
  <GenericPluginParams
    :parameters="parameters"
    :model-value="modelValue"
    :plugin-name="'{config['class_name']}Plugin'"
    @update:model-value="$emit('update:modelValue', $event)"
  />
</template>

<script setup>
import GenericPluginParams from './GenericPluginParams.vue'

// Standard props for all plugin parameter components
defineProps({{
  parameters: {{
    type: Object,
    required: true
  }},
  modelValue: {{
    type: Object,
    required: true
  }}
}})

defineEmits(['update:modelValue'])

// GenericPluginParams automatically handles:
// - Parameter form generation based on backend schema
// - API key warnings and validation
// - Case selection for evidence saving (via CaseEvidenceToggle component)
// - All standard parameter types (string, number, boolean)
//
// Only customize this component if you need:
// - Custom validation beyond basic required/optional
// - Special UI elements (dropdowns, multi-select, etc.)
// - Custom parameter layout or grouping
// - Plugin-specific help text or examples
</script>"""

    return template


def generate_result_component(config: Dict[str, Any]) -> str:
    """Generate a basic result component (most plugins should use the automatic fallback)"""

    icon = "mdi-magnify"
    if config["category"] == "Person":
        icon = "mdi-account"
    elif config["category"] == "Network":
        icon = "mdi-lan"
    elif config["category"] == "Company":
        icon = "mdi-domain"

    template = f"""<template>
  <div class="d-flex flex-column ga-4">
    <!-- TODO: Customize your result display here -->
    <!-- 
      This component is optional! The automatic PluginResult.vue provides
      a good fallback display for most plugins. Only create this if you need:
      - Custom formatting for specific data types
      - Special visualization (charts, tables, etc.)
      - Custom actions (copy buttons, links, etc.)
      - Plugin-specific styling or layout
    -->
    
    <template v-for="(item, index) in parsedResults" :key="index">
      <!-- Data Results -->
      <v-card v-if="item.type === 'data'" elevation="2" rounded="lg">
        <v-card-title class="d-flex align-center">
          <v-icon icon="{icon}" class="mr-2" />
          {{{{ item.data.target || '{config['display_name']} Results' }}}}
        </v-card-title>
        <v-card-text>
          <!-- Example: Display your plugin's specific data structure -->
          <pre class="text-caption">{{{{ JSON.stringify(item.data, null, 2) }}}}</pre>
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
import {{ computed }} from 'vue'

const props = defineProps({{
  result: {{
    type: [Object, Array],
    required: true,
  }}
}})

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
</script>
"""

    return template


def prepare_plugin_config(args) -> Dict[str, Any]:
    """Prepare the plugin configuration from arguments"""
    return {
        "name": args.name.lower().replace("-", "_"),
        "class_name": snake_to_pascal(args.name.lower().replace("-", "_")),
        "display_name": args.display_name
        or pascal_to_title(snake_to_pascal(args.name)),
        "description": args.description,
        "category": args.category,
        "evidence_category": args.evidence_category,
    }


def generate_all_content(config: Dict[str, Any], args) -> Dict[str, str]:
    """Generate all file contents based on configuration"""
    content = {
        "backend": generate_backend_plugin(config),
    }

    if not args.backend_only:
        content["params"] = generate_params_component(config)
        content["result"] = generate_result_component(config)

    if args.generate_tests:
        content["test"] = generate_test_file(config)

    return content


def display_completion_info(
    config: Dict[str, Any], args, file_paths: Dict[str, Path]
) -> None:
    """Display completion information and next steps"""
    print_status("header", f"Plugin '{config['display_name']}' created successfully!")
    print()
    print_status("info", "Next steps:")

    # Build next steps list
    steps = [f"Implement your plugin logic in: {file_paths['backend']}"]

    if not args.backend_only:
        steps.extend(
            [
                "Frontend UI is automatically handled by GenericPluginParams and PluginResult",
                f"   Only customize if needed in: {file_paths['params']} or {file_paths['result']}",
            ]
        )

    if args.generate_tests:
        steps.append(f"Complete the test implementation in: {file_paths['test']}")

    if args.dependencies:
        steps.append(
            f"Install dependencies: docker compose exec backend pip install {' '.join(args.dependencies)}"
        )
    else:
        steps.append("Add any required dependencies to: backend/requirements.txt")

    steps.extend(
        [
            "Restart the backend container: docker compose restart backend",
            "Test your plugin in the Plugins dashboard",
        ]
    )

    # Print numbered steps
    for i, step in enumerate(steps, 1):
        if step.startswith("   "):
            print(f"   {step}")
        else:
            print(f"{i}. {step}")

    # Print tips
    if args.backend_only:
        print()
        print_status("warning", "Backend-only mode: UI will be automatically generated")
    else:
        print()
        print_status("info", "Frontend components created as templates only")
        print(
            "   • GenericPluginParams.vue handles 95% of parameter forms automatically"
        )
        print("   • PluginResult.vue provides good fallback display for all data types")
        print(
            "   • Only customize the generated components if you need special UI features"
        )

    if args.generate_tests:
        print()
        print_status(
            "warning",
            f"Run tests with: docker compose exec backend pytest {file_paths['test']}",
        )

    print()
    print_status(
        "warning", "To require API keys, add to your plugin's __init__ method:"
    )
    print(
        '   self.api_key_requirements = ["provider_name"]  # e.g., ["openai", "shodan"]'
    )


def create_plugin(args):
    """Main function to create plugin files"""
    # Prepare configuration
    config = prepare_plugin_config(args)

    # Get file paths
    file_paths = get_plugin_file_paths(config)

    # Check for conflicts
    validate_file_conflicts(file_paths, args)

    # Generate all content
    content_map = generate_all_content(config, args)

    # Prepare files to write
    files_to_write = {}
    for content_type, content in content_map.items():
        files_to_write[file_paths[content_type]] = content

    # Add dependencies to requirements.txt
    if args.dependencies:
        add_dependencies_to_requirements(args.dependencies)

    # Write all files
    write_files_safely(files_to_write)

    # Display completion information
    display_completion_info(config, args, file_paths)


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
    print("\nUI Categories:")
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
    print("\nEvidence Categories:")
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
    print(f"\n{Colors.CYAN}Frontend Components:{Colors.END}")
    print("Most plugins work great with the automatic UI generation.")
    print("Frontend components are only needed for custom UI requirements.")
    backend_only_input = (
        input("Create backend only (recommended)? (Y/n): ").strip().lower()
    )
    backend_only = backend_only_input not in ["n", "no"]

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
        help="UI category for plugin organization (default: Other)",
    )

    parser.add_argument(
        "--evidence-category",
        choices=EVIDENCE_CATEGORIES,
        default="Other",
        help="Evidence storage category (default: Other)",
    )

    parser.add_argument(
        "--backend-only",
        action="store_true",
        help="Only create backend plugin file (UI will be automatically generated)",
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

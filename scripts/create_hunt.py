#!/usr/bin/env python3
"""
Owlculus Hunt Generator Script

This script helps developers quickly create new hunt workflows by generating:
- Backend hunt definition file with proper structure
- Optional test file for the hunt

Usage:
    python scripts/create_hunt.py <hunt_name> [options]

Example:
    python scripts/create_hunt.py company_investigation --category company --description "Comprehensive company investigation"
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


def get_hunt_file_paths(config: Dict[str, Any]) -> Dict[str, Path]:
    """Generate all file paths for the hunt"""
    project_root = Path(__file__).parent.parent
    return {
        "backend": project_root
        / "backend"
        / "app"
        / "hunts"
        / "definitions"
        / f"{config['name']}_hunt.py",
        "test": project_root
        / "backend"
        / "tests"
        / "hunts"
        / f"test_{config['name']}_hunt.py",
    }


def validate_file_conflicts(file_paths: Dict[str, Path], args) -> None:
    """Check for existing files and handle conflicts"""
    if args.force:
        return

    existing_files = []

    # Always check backend
    if file_paths["backend"].exists():
        existing_files.append(str(file_paths["backend"]))

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
            if "_hunt.py" in file_path.name:
                file_type = "hunt definition"
            elif "test_" in file_path.name:
                file_type = "test file"
            else:
                file_type = "file"

            print_status("success", f"Created {file_type}: {file_path}")

    except Exception as e:
        print_status("error", f"Error creating hunt files: {e}")
        # Clean up any files that were written
        for written_file in written_files:
            try:
                written_file.unlink()
            except:
                pass
        sys.exit(1)


# Valid categories for hunts
HUNT_CATEGORIES = ["domain", "person", "company", "network", "general"]


def snake_to_pascal(name: str) -> str:
    """Convert snake_case to PascalCase"""
    return "".join(word.capitalize() for word in name.split("_"))


def pascal_to_title(name: str) -> str:
    """Convert PascalCase to Title Case"""
    # Insert spaces before uppercase letters (except the first one)
    result = re.sub(r"(?<!^)(?=[A-Z])", " ", name)
    return result


def generate_hunt_definition(config: Dict[str, Any]) -> str:
    """Generate the hunt definition Python file content"""

    # Generate example steps based on category
    example_steps = []
    if config["category"] == "domain":
        example_steps = [
            {
                "step_id": "whois_lookup",
                "plugin_name": "WhoisPlugin",
                "display_name": "WHOIS lookup",
                "description": "Get domain registration information",
                "parameter_mapping": {"domain": "initial.target"},
                "timeout_seconds": 120,
            },
            {
                "step_id": "dns_records",
                "plugin_name": "DnsLookup",
                "display_name": "DNS records lookup",
                "description": "Retrieve all DNS records for the domain",
                "parameter_mapping": {"domain": "initial.target"},
                "depends_on": [],
            },
        ]
    elif config["category"] == "person":
        example_steps = [
            {
                "step_id": "email_check",
                "plugin_name": "HolehePlugin",
                "display_name": "Check email usage",
                "description": "Find online accounts associated with the email address",
                "parameter_mapping": {"email": "initial.target"},
            },
        ]
    elif config["category"] == "company":
        example_steps = [
            {
                "step_id": "domain_lookup",
                "plugin_name": "WhoisPlugin",
                "display_name": "Company domain lookup",
                "description": "Look up the company's primary domain",
                "parameter_mapping": {"domain": "initial.company_domain"},
            },
        ]
    else:
        example_steps = [
            {
                "step_id": "step1",
                "plugin_name": "YourPlugin",
                "display_name": "First Step",
                "description": "Description of what this step does",
                "parameter_mapping": {"plugin_param": "initial.target"},
            },
        ]

    # Generate step definitions code
    steps_code = []
    for i, step in enumerate(example_steps):
        step_lines = [
            "            HuntStepDefinition(",
            f'                step_id="{step["step_id"]}",',
            f'                plugin_name="{step["plugin_name"]}",',
            f'                display_name="{step["display_name"]}",',
            f'                description="{step["description"]}",',
        ]

        # Add parameter mapping
        if step.get("parameter_mapping"):
            mappings = ", ".join(
                f'"{k}": "{v}"' for k, v in step["parameter_mapping"].items()
            )
            step_lines.append(f"                parameter_mapping={{{mappings}}},")

        # Add optional fields
        if step.get("depends_on"):
            deps = ", ".join(f'"{d}"' for d in step["depends_on"])
            step_lines.append(f"                depends_on=[{deps}],")

        if step.get("timeout_seconds"):
            step_lines.append(
                f"                timeout_seconds={step['timeout_seconds']},"
            )

        if step.get("optional"):
            step_lines.append("                optional=True,")

        step_lines.append("            ),")

        if i < len(example_steps) - 1:
            step_lines.append("")

        steps_code.extend(step_lines)

    steps_str = "\n".join(steps_code)

    # Handle optional db_session parameter
    db_session_param = ""
    if config.get("needs_db_session"):
        db_session_param = ", db_session: Optional[Session] = None"

    template = f'''"""
{config['description']}
"""

from typing import List{", Optional" if config.get("needs_db_session") else ""}
{"""
from sqlmodel import Session""" if config.get("needs_db_session") else ""}

from ..base_hunt import BaseHunt, HuntStepDefinition


class {config['class_name']}Hunt(BaseHunt):
    """{config['description']}"""

    def __init__(self{db_session_param}):
        super().__init__()
        self.display_name = "{config['display_name']}"
        self.description = "{config['description']}"
        self.category = "{config['category']}"
        self.version = "1.0.0"
        
        # Define initial parameters that users will provide
        self.initial_parameters = {{
            "target": {{
                "type": "string",
                "description": "Target to investigate",
                "required": True,
            }},
            # TODO: Add more parameters as needed
            # Example:
            # "depth": {{
            #     "type": "number",
            #     "description": "Investigation depth (1-3)",
            #     "default": 1,
            #     "required": False,
            # }},
        }}

    def get_steps(self) -> List[HuntStepDefinition]:
        """Define the workflow steps for this hunt"""
        return [
{steps_str}
            
            # TODO: Add more steps to your hunt workflow
            # Example of a dependent step:
            # HuntStepDefinition(
            #     step_id="analyze_results",
            #     plugin_name="AnalysisPlugin",
            #     display_name="Analyze findings",
            #     description="Process and correlate results from previous steps",
            #     parameter_mapping={{
            #         # Access results from previous steps
            #         "data": "step1.results[0].data",
            #         "original_target": "initial.target",
            #     }},
            #     depends_on=["step1"],  # This step waits for step1 to complete
            #     optional=True,  # Hunt continues even if this step fails
            # ),
        ]

    # Optional: Override parameter validation for custom logic
    # def validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
    #     """Custom parameter validation"""
    #     validated = super().validate_parameters(parameters)
    #     
    #     # Add custom validation logic here
    #     # Example: ensure domain is properly formatted
    #     if "domain" in validated:
    #         validated["domain"] = validated["domain"].lower().strip()
    #     
    #     return validated
'''

    return template


def prepare_hunt_config(args) -> Dict[str, Any]:
    """Prepare the hunt configuration from arguments"""
    return {
        "name": args.name.lower().replace("-", "_"),
        "class_name": snake_to_pascal(args.name.lower().replace("-", "_")),
        "display_name": args.display_name
        or pascal_to_title(snake_to_pascal(args.name)),
        "description": args.description,
        "category": args.category,
        "needs_db_session": args.needs_db_session,
    }


def generate_all_content(config: Dict[str, Any], args) -> Dict[str, str]:
    """Generate all file contents based on configuration"""
    content = {
        "backend": generate_hunt_definition(config),
    }

    if args.generate_tests:
        content["test"] = generate_test_file(config)

    return content


def display_completion_info(
    config: Dict[str, Any], args, file_paths: Dict[str, Path]
) -> None:
    """Display completion information and next steps"""
    print_status("header", f"Hunt '{config['display_name']}' created successfully!")
    print()
    print_status("info", "Next steps:")

    # Build next steps list
    steps = [
        f"Implement your hunt workflow in: {file_paths['backend']}",
        "Review available plugins to use in your hunt steps:",
        "   - Run: ls backend/app/plugins/ | grep -E '_plugin.py$'",
        "Add hunt steps using HuntStepDefinition in get_steps() method",
        "Define parameter mappings to pass data between steps",
    ]

    if args.generate_tests:
        steps.append(f"Complete the test implementation in: {file_paths['test']}")

    steps.extend(
        [
            "Restart the backend container: docker compose restart backend",
            "Test your hunt in the Hunts dashboard",
        ]
    )

    # Print numbered steps
    for i, step in enumerate(steps, 1):
        if step.startswith("   "):
            print(f"   {step}")
        else:
            print(f"{i}. {step}")

    # Print parameter mapping examples
    print()
    print_status("info", "Parameter mapping examples:")
    print("   • Access initial parameters: 'initial.parameter_name'")
    print("   • Access step results: 'step_id.results[0].data.field_name'")
    print("   • Static values: Use static_parameters instead")

    print()
    print_status("info", "Step dependency examples:")
    print("   • Sequential execution: depends_on=['previous_step']")
    print("   • Parallel execution: No depends_on (runs immediately)")
    print("   • Optional steps: optional=True (failures don't stop hunt)")

    if args.generate_tests:
        print()
        print_status(
            "warning",
            f"Run tests with: docker compose exec backend pytest {file_paths['test']}",
        )

    print()
    print_status("info", "For more details, see HUNT_DEVELOPMENT.md")


def create_hunt(args):
    """Main function to create hunt files"""
    # Prepare configuration
    config = prepare_hunt_config(args)

    # Get file paths
    file_paths = get_hunt_file_paths(config)

    # Check for conflicts
    validate_file_conflicts(file_paths, args)

    # Generate all content
    content_map = generate_all_content(config, args)

    # Prepare files to write
    files_to_write = {}
    for content_type, content in content_map.items():
        files_to_write[file_paths[content_type]] = content

    # Write all files
    write_files_safely(files_to_write)

    # Display completion information
    display_completion_info(config, args, file_paths)


def generate_test_file(config: Dict[str, Any]) -> str:
    """Generate a basic test file for the hunt"""

    template = f'''"""
Tests for {config['display_name']} hunt
"""

import pytest
from app.hunts.definitions.{config['name']}_hunt import {config['class_name']}Hunt
from app.hunts.base_hunt import HuntStepDefinition


class Test{config['class_name']}Hunt:
    """Test cases for {config['class_name']}Hunt"""

    @pytest.fixture
    def hunt(self):
        """Create hunt instance for testing"""
        return {config['class_name']}Hunt()

    def test_hunt_initialization(self, hunt):
        """Test hunt initializes correctly"""
        assert hunt.display_name == "{config['display_name']}"
        assert hunt.description == "{config['description']}"
        assert hunt.category == "{config['category']}"
        assert hunt.version == "1.0.0"
        assert isinstance(hunt.initial_parameters, dict)

    def test_hunt_parameters(self, hunt):
        """Test hunt parameters are defined correctly"""
        params = hunt.initial_parameters
        
        # TODO: Add specific parameter validation tests
        assert "target" in params
        assert params["target"]["required"] is True
        assert params["target"]["type"] == "string"

    def test_hunt_steps(self, hunt):
        """Test hunt steps are properly defined"""
        steps = hunt.get_steps()
        
        assert isinstance(steps, list)
        assert len(steps) > 0
        
        # Verify all steps are HuntStepDefinition instances
        for step in steps:
            assert isinstance(step, HuntStepDefinition)
            assert step.step_id
            assert step.plugin_name
            assert step.display_name
            assert step.description

    def test_parameter_validation(self, hunt):
        """Test parameter validation"""
        # Test with valid parameters
        valid_params = {{"target": "example.com"}}
        validated = hunt.validate_parameters(valid_params)
        assert validated["target"] == "example.com"
        
        # Test missing required parameter
        with pytest.raises(ValueError, match="Required parameter 'target' is missing"):
            hunt.validate_parameters({{}})

    def test_step_dependencies(self, hunt):
        """Test step dependency graph is valid"""
        steps = hunt.get_steps()
        step_ids = {{step.step_id for step in steps}}
        
        # Verify all dependencies reference existing steps
        for step in steps:
            for dep in step.depends_on:
                assert dep in step_ids, f"Step '{{step.step_id}}' depends on non-existent step '{{dep}}'"

    def test_hunt_metadata(self, hunt):
        """Test hunt metadata generation"""
        metadata = hunt.get_metadata()
        
        assert metadata["name"] == hunt.name
        assert metadata["display_name"] == hunt.display_name
        assert metadata["description"] == hunt.description
        assert metadata["category"] == hunt.category
        assert metadata["version"] == hunt.version
        assert metadata["step_count"] == len(hunt.get_steps())
        assert metadata["initial_parameters"] == hunt.initial_parameters

    def test_hunt_definition_export(self, hunt):
        """Test hunt can be exported as definition"""
        definition = hunt.to_definition()
        
        assert definition["name"] == hunt.name
        assert definition["display_name"] == hunt.display_name
        assert definition["description"] == hunt.description
        assert definition["category"] == hunt.category
        assert definition["version"] == hunt.version
        assert len(definition["steps"]) == len(hunt.get_steps())
        
        # Verify steps are properly serialized
        for i, step_dict in enumerate(definition["steps"]):
            original_step = hunt.get_steps()[i]
            assert step_dict["step_id"] == original_step.step_id
            assert step_dict["plugin_name"] == original_step.plugin_name

    # TODO: Add more specific tests for your hunt's logic
    # Example:
    # def test_custom_parameter_validation(self, hunt):
    #     """Test custom parameter validation logic"""
    #     # Test domain normalization
    #     params = {{"domain": "EXAMPLE.COM  "}}
    #     validated = hunt.validate_parameters(params)
    #     assert validated["domain"] == "example.com"
'''

    return template


def interactive_mode():
    """Interactive mode for creating hunts"""
    print(f"{Colors.CYAN}{Colors.BOLD}Owlculus Hunt Generator{Colors.END}")
    print(f"{Colors.CYAN}{'=' * 40}{Colors.END}")
    print()

    # Get hunt name
    while True:
        name = input(
            "Enter hunt name (e.g., company_investigation, ip_recon): "
        ).strip()
        if not name:
            print(f"{Colors.RED}ERROR:{Colors.END} Hunt name is required")
            continue
        if not re.match(r"^[a-z][a-z0-9_-]*$", name.lower()):
            print(
                f"{Colors.RED}ERROR:{Colors.END} Hunt name must start with a letter and contain only"
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
        description = "Automated investigation workflow"

    # Get category
    print("\nHunt Categories:")
    for i, cat in enumerate(HUNT_CATEGORIES, 1):
        print(f"  {i}. {cat}")

    while True:
        try:
            choice = input(
                f"Select category [1-{len(HUNT_CATEGORIES)}] (default: 5): "
            ).strip()
            if not choice:
                category = "general"
                break
            idx = int(choice) - 1
            if 0 <= idx < len(HUNT_CATEGORIES):
                category = HUNT_CATEGORIES[idx]
                break
            else:
                print(
                    f"{Colors.RED}ERROR:{Colors.END} Please enter a number between 1 and {len(HUNT_CATEGORIES)}"
                )
        except ValueError:
            print(f"{Colors.RED}ERROR:{Colors.END} Please enter a valid number")

    # DB session requirement
    print(f"\n{Colors.CYAN}Database Access:{Colors.END}")
    print("Some hunts need database access to check API keys or configurations.")
    needs_db_input = (
        input("Does your hunt need database access? (y/N): ").strip().lower()
    )
    needs_db_session = needs_db_input in ["y", "yes"]

    # Generate tests
    generate_tests_input = input("\nGenerate test file? (Y/n): ").strip().lower()
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
            self.needs_db_session = needs_db_session
            self.force = force
            self.generate_tests = generate_tests

    return Args()


def main():
    parser = argparse.ArgumentParser(
        description="Create a new Owlculus hunt workflow with proper templates",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Interactive Mode (default):
  python scripts/create_hunt.py

Command Line Mode:
  # Create a simple hunt
  python scripts/create_hunt.py email_investigation

  # Create a domain category hunt
  python scripts/create_hunt.py domain_recon --category domain --description "Reconnaissance workflow for domains"

  # Create hunt with database access
  python scripts/create_hunt.py api_investigation --needs-db-session

  # Create hunt without tests
  python scripts/create_hunt.py quick_lookup --no-tests

  # Override existing files
  python scripts/create_hunt.py domain_recon --force
        """,
    )

    parser.add_argument(
        "name",
        nargs="?",
        help="Hunt name (snake_case or kebab-case, e.g., company_investigation, ip-recon)",
    )

    parser.add_argument(
        "--display-name",
        help="Human-readable display name (default: auto-generated from name)",
    )

    parser.add_argument(
        "--description",
        default="Automated investigation workflow",
        help="Hunt description (default: placeholder text)",
    )

    parser.add_argument(
        "--category",
        choices=HUNT_CATEGORIES,
        default="general",
        help="Hunt category (default: general)",
    )

    parser.add_argument(
        "--needs-db-session",
        action="store_true",
        help="Hunt needs database session for API key checks",
    )

    parser.add_argument("--force", action="store_true", help="Overwrite existing files")

    parser.add_argument(
        "--no-tests", action="store_true", help="Skip generating test file"
    )

    args = parser.parse_args()

    # If no name provided, use interactive mode
    if not args.name:
        args = interactive_mode()
    else:
        # Validate hunt name for command line mode
        if not re.match(r"^[a-z][a-z0-9_-]*$", args.name.lower()):
            print(
                f"{Colors.RED}ERROR:{Colors.END} Hunt name must start with a letter and contain only"
            )
            print("   lowercase letters, numbers, underscores, or hyphens")
            sys.exit(1)

        # Add missing attributes for command line mode
        args.generate_tests = not args.no_tests

    create_hunt(args)


if __name__ == "__main__":
    main()

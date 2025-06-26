#!/usr/bin/env python3
"""
Test data creation script for Owlculus
Creates sample data for manual testing through the UI
"""

import argparse
import asyncio
import json

import httpx


async def create_test_data(
    username: str, password: str, base_url: str = "http://localhost:8000"
):
    """Create test data for manual testing."""
    print("Creating test data for Owlculus...")

    async with httpx.AsyncClient() as client:
        try:
            # Login to get access token
            print(f"Logging in as '{username}'...")
            login_response = await client.post(
                f"{base_url}/api/auth/login",
                data={"username": username, "password": password},
            )

            if login_response.status_code != 200:
                print(
                    f"ERROR: Login failed: {login_response.status_code} - {login_response.text}"
                )
                return

            token_data = login_response.json()
            access_token = token_data["access_token"]
            headers = {"Authorization": f"Bearer {access_token}"}

            print("Login successful")

            # Create analyst and investigator users
            print("Creating test users...")

            # Create analyst user
            analyst_data = {
                "username": "analyst",
                "email": "analyst@example.com",
                "password": "anapassword1",
                "role": "Analyst",
                "is_active": True,
            }

            analyst_response = await client.post(
                f"{base_url}/api/users/", json=analyst_data, headers=headers
            )

            if analyst_response.status_code in [200, 201]:
                print("Created analyst user")
            elif (
                "already exists" in analyst_response.text
                or analyst_response.status_code == 400
            ):
                print("Analyst user already exists")
            else:
                print(
                    f"Warning: Could not create analyst user: {analyst_response.status_code} - {analyst_response.text}"
                )

            # Create investigator user
            investigator_data = {
                "username": "investigator",
                "email": "investigator@example.com",
                "password": "invpassword1",
                "role": "Investigator",
                "is_active": True,
            }

            investigator_response = await client.post(
                f"{base_url}/api/users/", json=investigator_data, headers=headers
            )

            if investigator_response.status_code in [200, 201]:
                print("Created investigator user")
            elif (
                "already exists" in investigator_response.text
                or investigator_response.status_code == 400
            ):
                print("Investigator user already exists")
            else:
                print(
                    f"Warning: Could not create investigator user: {investigator_response.status_code} - {investigator_response.text}"
                )

            # Get or create Personal client
            print("Getting clients list...")
            clients_response = await client.get(
                f"{base_url}/api/clients/", headers=headers
            )

            if clients_response.status_code != 200:
                print(
                    f"ERROR: Failed to get clients: {clients_response.status_code} - {clients_response.text}"
                )
                return

            try:
                clients = clients_response.json()
            except json.JSONDecodeError:
                print(
                    f"ERROR: Invalid JSON response from clients API: {clients_response.text}"
                )
                return

            personal_client = None
            for client_obj in clients:
                if client_obj["name"] == "Personal":
                    personal_client = client_obj
                    break

            if not personal_client:
                print(
                    "ERROR: Personal client not found. Please run init_db_auto.py first."
                )
                return

            print(f"Found Personal client: {personal_client['name']}")

            # Check if test case already exists
            print("Getting cases list...")
            cases_response = await client.get(f"{base_url}/api/cases/", headers=headers)

            if cases_response.status_code != 200:
                print(
                    f"ERROR: Failed to get cases: {cases_response.status_code} - {cases_response.text}"
                )
                return

            try:
                cases = cases_response.json()
            except json.JSONDecodeError:
                print(
                    f"ERROR: Invalid JSON response from cases API: {cases_response.text}"
                )
                return

            test_case = None
            for case in cases:
                if case["title"] == "Test Case 1":
                    test_case = case
                    print(f"Test Case 1 already exists (Case #{case['case_number']})")
                    break

            if not test_case:
                # Create Test Case 1
                print("Creating Test Case 1...")
                case_data = {
                    "title": "Test Case 1",
                    "client_id": personal_client["id"],
                    "status": "Open",
                    "notes": "This is a test case created for manual testing purposes.",
                }

                case_response = await client.post(
                    f"{base_url}/api/cases/", json=case_data, headers=headers
                )

                if case_response.status_code not in [200, 201]:
                    print(
                        f"ERROR: Failed to create case: {case_response.status_code} - {case_response.text}"
                    )
                    return

                test_case = case_response.json()
                print(f"Created Test Case 1 (Case #{test_case['case_number']})")

            # Apply Person evidence template to the case
            print("Applying Person evidence template...")
            template_response = await client.post(
                f"{base_url}/api/evidence/case/{test_case['id']}/apply-template?template_name=Person",
                headers=headers,
            )

            if template_response.status_code in [200, 201]:
                print("Applied Person evidence template")
            elif "already exist" in template_response.text:
                print("Person evidence template already applied")
            else:
                print(
                    f"Warning: Could not apply Person template: {template_response.status_code} - {template_response.text}"
                )

            # Check if John Doe entity already exists
            print("Getting entities list...")
            entities_response = await client.get(
                f"{base_url}/api/cases/{test_case['id']}/entities", headers=headers
            )

            if entities_response.status_code != 200:
                print(
                    f"ERROR: Failed to get entities: {entities_response.status_code} - {entities_response.text}"
                )
                return

            try:
                entities = entities_response.json()
            except json.JSONDecodeError:
                print(
                    f"ERROR: Invalid JSON response from entities API: {entities_response.text}"
                )
                return

            john_doe_exists = False
            for entity in entities:
                if (
                    entity["entity_type"] == "person"
                    and entity["data"].get("first_name") == "John"
                    and entity["data"].get("last_name") == "Doe"
                ):
                    john_doe_exists = True
                    print("John Doe entity already exists")
                    break

            if not john_doe_exists:
                # Create John Doe entity
                print("Creating John Doe entity...")
                entity_data = {
                    "case_id": test_case["id"],
                    "entity_type": "person",
                    "data": {
                        "first_name": "John",
                        "last_name": "Doe",
                        "notes": "This is a test person entity created for manual testing purposes.",
                    },
                }

                entity_response = await client.post(
                    f"{base_url}/api/cases/{test_case['id']}/entities",
                    json=entity_data,
                    headers=headers,
                )

                if entity_response.status_code not in [200, 201]:
                    print(
                        f"ERROR: Failed to create entity: {entity_response.status_code} - {entity_response.text}"
                    )
                    return

                john_doe = entity_response.json()
                print(f"Created John Doe entity (ID: {john_doe['id']})")

            print("\nTest data creation completed successfully!")
            print("You can now log in and work with:")
            print(f"   - Case: Test Case 1 (#{test_case['case_number']})")
            print("   - Client: Personal")
            print("   - Entity: John Doe")
            print("   - Evidence folders: Person investigation template")
            print("")
            print("Available test users:")
            print("   - admin / admin (Admin role)")
            print("   - analyst / anapassword1 (Analyst role)")
            print("   - investigator / invpassword1 (Investigator role)")

        except Exception as e:
            print(f"ERROR: Error creating test data: {e}")
            raise


def main():
    parser = argparse.ArgumentParser(description="Create test data for Owlculus")
    parser.add_argument(
        "--username", "-u", default="admin", help="Admin username (default: admin)"
    )
    parser.add_argument(
        "--password", "-p", default="admin", help="Admin password (default: admin)"
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Backend URL (default: http://localhost:8000)",
    )

    args = parser.parse_args()

    asyncio.run(create_test_data(args.username, args.password, args.url))


if __name__ == "__main__":
    main()

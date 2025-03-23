#!/usr/bin/env python3
"""
Update Client Tool for Invoice App

This script allows updating client information in the invoice database.
It can be used directly from the command line or imported by the chatbot.
"""

import os
import sys
import json
import argparse
from pdf_parser import get_collection, search_invoices


def update_client_info(client_name, updates, verbose=True):
    """
    Update client information in the database.

    Args:
        client_name (str): The name of the client to update
        updates (dict): Dictionary of fields to update (e.g., {'email': 'client@example.com'})
        verbose (bool): Whether to print status messages

    Returns:
        dict: Result of the operation with success status and message
    """
    if verbose:
        print(f"Searching for client: {client_name}")

    # Search for the client in the database
    results = search_invoices(client_name, n_results=5)

    if not results:
        if verbose:
            print(f"No client found with name: {client_name}")
        return {
            "success": False,
            "message": f"No client found with name: {client_name}",
        }

    # Get the best match
    best_match = results[0]
    matched_client_name = best_match.get("client_name", "")

    if verbose:
        print(f"Found client: {matched_client_name}")

    # Get the collection
    collection = get_collection()

    # Get all items to find the document ID for this client
    all_data = collection.get()
    client_id = None
    client_metadata = None

    # Find the document ID for this client
    for i, metadata in enumerate(all_data["metadatas"]):
        if metadata.get("client_name", "") == matched_client_name:
            client_id = all_data["ids"][i]
            client_metadata = metadata
            break

    if not client_id:
        if verbose:
            print(f"Could not find document ID for client: {matched_client_name}")
        return {
            "success": False,
            "message": f"Could not find document ID for client: {matched_client_name}",
        }

    # Update the metadata with the new information
    updated_metadata = dict(client_metadata)

    # Add or update fields
    for key, value in updates.items():
        # Special handling for services which is stored as JSON
        if key == "services" and isinstance(value, list):
            updated_metadata[key] = json.dumps(value)
        # Make sure value is a primitive type (str, int, float, bool)
        elif isinstance(value, (str, int, float, bool)):
            updated_metadata[key] = value
        else:
            # Convert non-primitive types to string
            updated_metadata[key] = str(value)

    # Update the document in the collection
    try:
        collection.update(ids=[client_id], metadatas=[updated_metadata])

        if verbose:
            print(f"Successfully updated client: {matched_client_name}")
            print("Updated fields:")
            for key, value in updates.items():
                print(f"  {key}: {value}")

        return {
            "success": True,
            "message": f"Successfully updated client: {matched_client_name}",
            "client_name": matched_client_name,
            "updated_fields": updates,
        }
    except Exception as e:
        error_msg = f"Error updating client in database: {str(e)}"
        if verbose:
            print(error_msg)
        return {"success": False, "message": error_msg}


def add_client(client_name, client_info, verbose=True):
    """
    Add a new client to the database if they don't exist.

    Args:
        client_name (str): The name of the new client
        client_info (dict): Dictionary of client information
        verbose (bool): Whether to print status messages

    Returns:
        dict: Result of the operation with success status and message
    """
    if verbose:
        print(f"Checking if client exists: {client_name}")

    # Check if client already exists
    results = search_invoices(client_name, n_results=1)

    if results:
        matched_client_name = results[0].get("client_name", "")
        if verbose:
            print(f"Client already exists: {matched_client_name}")

        # Update the existing client
        return update_client_info(matched_client_name, client_info, verbose)

    # Client doesn't exist, create a new entry
    if verbose:
        print(f"Creating new client: {client_name}")

    # Get the collection
    collection = get_collection()

    # Prepare metadata
    metadata = {
        "client_name": client_name,
        "client_address": client_info.get("address", ""),
        "invoice_number": "N/A",
        "invoice_date": "N/A",
        "invoice_amount": "N/A",
        "services": "[]",
        "source_file": "manual_entry",
    }

    # Add additional fields
    for key, value in client_info.items():
        if key != "address":  # Address is already handled above
            if key == "services" and isinstance(value, list):
                metadata[key] = json.dumps(value)
            else:
                metadata[key] = value

    # Create a simple document text
    document_text = f"Client: {client_name}\n"
    if "address" in client_info:
        document_text += f"Address: {client_info['address']}\n"
    if "email" in client_info:
        document_text += f"Email: {client_info['email']}\n"

    # Add to collection
    try:
        client_id = f"{client_name}_manual".replace(" ", "_")
        collection.add(documents=[document_text], metadatas=[metadata], ids=[client_id])

        if verbose:
            print(f"Successfully added new client: {client_name}")
            print("Client information:")
            for key, value in client_info.items():
                print(f"  {key}: {value}")

        return {
            "success": True,
            "message": f"Successfully added new client: {client_name}",
            "client_name": client_name,
            "client_info": client_info,
        }
    except Exception as e:
        error_msg = f"Error adding client to database: {str(e)}"
        if verbose:
            print(error_msg)
        return {"success": False, "message": error_msg}


def get_client_details(client_name, verbose=True):
    """
    Get detailed information about a client.

    Args:
        client_name (str): The name of the client to look up
        verbose (bool): Whether to print status messages

    Returns:
        dict: Client information or error message
    """
    if verbose:
        print(f"Looking up client: {client_name}")

    # Search for the client in the database
    results = search_invoices(client_name, n_results=1)

    if not results:
        if verbose:
            print(f"No client found with name: {client_name}")
        return {
            "success": False,
            "message": f"No client found with name: {client_name}",
        }

    # Get the client information
    client_info = results[0]

    if verbose:
        print(f"Found client: {client_info.get('client_name', '')}")
        print("Client details:")
        for key, value in client_info.items():
            if key != "services" and key != "document":
                print(f"  {key}: {value}")

    return {
        "success": True,
        "message": f"Found client: {client_info.get('client_name', '')}",
        "client_info": client_info,
    }


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Update client information in the invoice database."
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Update client subcommand
    update_parser = subparsers.add_parser("update", help="Update an existing client")
    update_parser.add_argument("client_name", help="Name of the client to update")
    update_parser.add_argument("--email", help="Client email address")
    update_parser.add_argument("--address", help="Client address")
    update_parser.add_argument("--phone", help="Client phone number")
    update_parser.add_argument("--notes", help="Additional notes about the client")

    # Add client subcommand
    add_parser = subparsers.add_parser("add", help="Add a new client")
    add_parser.add_argument("client_name", help="Name of the new client")
    add_parser.add_argument("--email", help="Client email address")
    add_parser.add_argument("--address", help="Client address")
    add_parser.add_argument("--phone", help="Client phone number")
    add_parser.add_argument("--notes", help="Additional notes about the client")

    # Get client details subcommand
    get_parser = subparsers.add_parser("get", help="Get client details")
    get_parser.add_argument("client_name", help="Name of the client to look up")

    args = parser.parse_args()

    if args.command == "update":
        # Collect updates from arguments
        updates = {}
        if args.email:
            updates["email"] = args.email
        if args.address:
            updates["client_address"] = args.address
        if args.phone:
            updates["phone"] = args.phone
        if args.notes:
            updates["notes"] = args.notes

        if not updates:
            print(
                "Error: No updates provided. Use --email, --address, --phone, or --notes."
            )
            sys.exit(1)

        # Update the client
        result = update_client_info(args.client_name, updates)
        if not result["success"]:
            sys.exit(1)

    elif args.command == "add":
        # Collect client info from arguments
        client_info = {}
        if args.email:
            client_info["email"] = args.email
        if args.address:
            client_info["address"] = args.address
        if args.phone:
            client_info["phone"] = args.phone
        if args.notes:
            client_info["notes"] = args.notes

        # Add the client
        result = add_client(args.client_name, client_info)
        if not result["success"]:
            sys.exit(1)

    elif args.command == "get":
        # Get client details
        result = get_client_details(args.client_name)
        if not result["success"]:
            sys.exit(1)

    else:
        parser.print_help()
        sys.exit(1)

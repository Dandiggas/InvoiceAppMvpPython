#!/usr/bin/env python3
"""
List Clients Tool for Invoice App

This script retrieves all clients from the invoice database and displays them in a formatted list.
It can be run directly from the command line with optional CSV export functionality.

Usage:
    python list_clients.py [--csv filename.csv]
"""

import os
import sys
import re
import csv
import argparse
from pdf_parser import get_all_invoices


def is_valid_client_name(name):
    """
    Check if a string is likely to be a valid client name.
    Returns False for strings that are likely addresses, dates, or other non-client text.
    """
    # Skip if empty or too short
    if not name or len(name) < 3:
        return False

    # Skip if it's just a number or date
    if re.match(r"^\d+$", name) or re.match(
        r"^\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}$", name
    ):
        return False

    # Skip if it starts with common non-client patterns
    if re.match(
        r"^(and|as|ul\.|description|invoice|expenses|purchase|po:)", name.lower()
    ):
        return False

    # Skip if it's just an address (starts with a number followed by a street name)
    if re.match(
        r"^\d+\s+[A-Za-z\s]+(road|street|avenue|lane|drive|way|place|court)",
        name.lower(),
    ):
        return False

    # Skip if it contains personal contact information
    if "07946670601" in name or "dadekugbe@gmail.com" in name:
        return False

    # Skip if it's just "277 shooters hill road" which appears frequently
    if "277 shooters hill road" in name.lower() and len(name.split()) <= 5:
        return False

    return True


def clean_client_info(client_name, client_info):
    """
    Clean up client information by removing personal data and formatting.
    """
    # Clean address - remove personal contact information
    address = client_info["address"]
    address = re.sub(r"\b07\d{9}\b", "", address)  # Remove phone numbers
    address = re.sub(r"\S+@\S+\.\S+", "", address)  # Remove email addresses

    # Remove user's personal address
    address = re.sub(r"277 shooters hill road", "", address, flags=re.IGNORECASE)
    address = re.sub(r"se38un", "", address, flags=re.IGNORECASE)
    address = re.sub(r"se3 8un", "", address, flags=re.IGNORECASE)

    # Clean up whitespace and formatting
    address = re.sub(r"\s+", " ", address).strip()
    address = re.sub(r"^,\s*", "", address)  # Remove leading commas
    address = re.sub(r",\s*,", ",", address)  # Remove double commas

    # If address is empty or just "London" after cleaning, set to "No address available"
    if not address or address.lower() in ["london", "unknown"]:
        address = "No address available"

    # Update the client info with cleaned address
    client_info["address"] = address

    return client_name, client_info


def list_all_clients(export_csv=None):
    """
    Retrieve all clients from the invoice database and display them in a formatted list.
    Returns a list of unique client names.
    """
    print("Retrieving clients from invoice database...")

    # Get all invoices from the database
    invoices = get_all_invoices()

    if not invoices:
        print("No invoices found in the database.")
        return []

    # Extract unique client names
    clients = {}  # Using a dict to store client name -> client info
    filtered_clients = {}  # Will store only valid clients

    for invoice in invoices:
        client_name = invoice.get("client_name", "").strip()
        if client_name and client_name != "unknown":
            # Store the client with their address and latest invoice info
            if client_name not in clients:
                clients[client_name] = {
                    "address": invoice.get("client_address", ""),
                    "latest_invoice": invoice.get("invoice_date", ""),
                    "invoice_count": 1,
                }
            else:
                # Increment invoice count
                clients[client_name]["invoice_count"] += 1

                # Update latest invoice date if this one is newer
                # (simple string comparison works for DD/MM/YYYY format)
                if (
                    invoice.get("invoice_date", "")
                    > clients[client_name]["latest_invoice"]
                ):
                    clients[client_name]["latest_invoice"] = invoice.get(
                        "invoice_date", ""
                    )

    # Filter out invalid client names and clean up client info
    for client_name, client_info in clients.items():
        if is_valid_client_name(client_name):
            # Clean up client information
            clean_name, clean_info = clean_client_info(client_name, client_info.copy())
            filtered_clients[clean_name] = clean_info

    # Display the results
    if not filtered_clients:
        print("No valid clients found in the database.")
        return []

    print(f"\nFound {len(filtered_clients)} clients:\n")
    print("-" * 80)

    # Sort clients alphabetically
    sorted_clients = sorted(filtered_clients.items())

    for i, (client_name, client_info) in enumerate(sorted_clients, 1):
        print(f"{i}. {client_name}")
        if client_info["address"] and client_info["address"] != "unknown":
            # Format address to display nicely
            address = client_info["address"].replace("\n", ", ")
            print(f"   Address: {address}")
        print(f"   Invoices: {client_info['invoice_count']}")
        if client_info["latest_invoice"] and client_info["latest_invoice"] != "unknown":
            print(f"   Latest Invoice: {client_info['latest_invoice']}")
        print()

    print("-" * 80)

    # Export to CSV if requested
    if export_csv:
        try:
            with open(export_csv, "w", newline="") as csvfile:
                fieldnames = [
                    "Client Name",
                    "Address",
                    "Invoice Count",
                    "Latest Invoice",
                ]
                writer = csv.DictWriter(
                    csvfile,
                    fieldnames=fieldnames,
                    delimiter=",",
                    quotechar='"',
                    quoting=csv.QUOTE_MINIMAL,
                )

                writer.writeheader()
                for client_name, client_info in sorted_clients:
                    writer.writerow(
                        {
                            "Client Name": client_name,
                            "Address": client_info["address"].replace("\n", ", "),
                            "Invoice Count": client_info["invoice_count"],
                            "Latest Invoice": client_info["latest_invoice"],
                        }
                    )
                print(f"Client list exported to {export_csv}")
        except Exception as e:
            print(f"Error exporting to CSV: {e}")

    return [client_name for client_name, _ in sorted_clients]


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="List all clients from the invoice database."
    )
    parser.add_argument("--csv", help="Export client list to CSV file")
    args = parser.parse_args()

    list_all_clients(export_csv=args.csv)

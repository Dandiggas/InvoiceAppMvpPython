"""
Script to process all invoices in the invoices directory and store them in ChromaDB.
"""

import os
import sys
from pdf_parser import process_invoice_directory, get_collection, search_invoices


def main():
    """Process all invoices and test search functionality."""
    # Get the invoices directory from config
    from config import config

    invoices_dir = config.INVOICES_DIR

    # Process all invoices in the directory
    print(f"Processing invoices in {invoices_dir}...")
    process_invoice_directory(invoices_dir)

    # Test search functionality with a few client names
    test_clients = [
        "ALR Music",
        "Warner Music",
        "Peninsula",
        "Mahalia",
        "Daniel Godson",
    ]

    print("\nTesting search functionality:")
    for client in test_clients:
        print(f"\nSearching for client: {client}")
        results = search_invoices(client, n_results=2)

        if results:
            for i, result in enumerate(results, 1):
                print(f"  Result {i}:")
                print(f"    Client: {result.get('client_name', 'unknown')}")
                print(f"    Address: {result.get('client_address', 'unknown')}")
                print(f"    Invoice #: {result.get('invoice_number', 'unknown')}")
                print(f"    Date: {result.get('invoice_date', 'unknown')}")
                print(f"    Amount: {result.get('invoice_amount', 'unknown')}")

                services = result.get("services", [])
                if services:
                    print(f"    Services:")
                    for service in services:
                        if isinstance(service, dict):
                            print(
                                f"      - {service.get('service_name', 'unknown')}: {service.get('service_price', 'unknown')}"
                            )
        else:
            print(f"  No results found for {client}")

    # Print collection stats
    collection = get_collection()
    count = collection.count()
    print(f"\nTotal documents in collection: {count}")


if __name__ == "__main__":
    main()

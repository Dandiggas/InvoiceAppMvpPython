"""
Script to reprocess all invoices with improved extraction logic.
"""

import os
from pdf_parser import reprocess_all_invoices
from config import config


def main():
    """Reprocess all invoices in the invoices directory."""
    # Get the invoices directory from config
    invoices_dir = config.INVOICES_DIR

    print(f"Reprocessing invoices in {invoices_dir}...")

    # Reprocess all invoices
    reprocess_all_invoices(invoices_dir)

    print("Reprocessing complete.")


if __name__ == "__main__":
    main()

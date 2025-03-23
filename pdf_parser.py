"""
PDF Parser module for the Invoice App.

This module handles extracting data from PDF invoices and storing it in a vector database.
It provides functions for parsing invoice fields, extracting client information,
and retrieving invoice data for the chatbot.
"""

import os
import re
import pdfplumber
import numpy as np
import json
import chromadb
from typing import Dict, List, Any, Optional, Union, Tuple
from config import config

# ------------------------------------------------------------
# 1) Setup Embeddings and ChromaDB
# ------------------------------------------------------------

# Initialize variables
USING_REAL_EMBEDDINGS = False
embedding_model = None

# Try to import SentenceTransformer
try:
    from sentence_transformers import SentenceTransformer

    # Initialize the model with a timeout to prevent hanging
    import threading
    import time

    def initialize_model():
        global embedding_model, USING_REAL_EMBEDDINGS
        try:
            embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
            USING_REAL_EMBEDDINGS = True
            print("Using SentenceTransformer for embeddings")
        except Exception as e:
            print(f"Failed to initialize SentenceTransformer: {e}")
            USING_REAL_EMBEDDINGS = False

    # Run model initialization with a timeout
    init_thread = threading.Thread(target=initialize_model)
    init_thread.daemon = True
    init_thread.start()

    # Wait for up to 10 seconds
    init_thread.join(timeout=10)

    if not USING_REAL_EMBEDDINGS:
        print("SentenceTransformer not available, using fallback embeddings")
except ImportError:
    print("SentenceTransformer not available, using fallback embeddings")


# Fallback embedding function that generates deterministic vectors
class FallbackEmbeddingFunction:
    """Fallback embedding function that generates deterministic vectors based on text content."""

    def __call__(self, input: Union[str, List[str]]) -> List[List[float]]:
        """
        Generate embeddings for input text.

        Args:
            input: String or list of strings to embed

        Returns:
            List of embedding vectors
        """
        if isinstance(input, list):
            return [generate_embedding(text) for text in input]
        return [generate_embedding(input)]


# Initialize embedding function
embedding_func = FallbackEmbeddingFunction()


# Initialize collection - but don't run this at module import time
_collection = None


def get_collection():
    """Get the ChromaDB collection, initializing it only once when needed."""
    global _collection
    if _collection is None:
        _collection = get_or_create_collection()
    return _collection


# Get or create collection
def get_or_create_collection(collection_name: str = "invoices_collection"):
    """
    Get or create a ChromaDB collection for storing invoice data.

    Args:
        collection_name: Name of the collection to get or create

    Returns:
        ChromaDB collection object
    """
    # Initialize ChromaDB client with the path from config
    client = chromadb.PersistentClient(path=config.CHROMA_DB_PATH)

    # Try to get the collection first, then create if it doesn't exist
    try:
        # First try to get the collection
        collection = client.get_collection(
            name=collection_name, embedding_function=embedding_func
        )
        print(f"Using existing collection: {collection_name}")
        return collection
    except Exception as e:
        # Create the collection if it doesn't exist or if there's any other error
        # This is a more robust approach since different versions of ChromaDB might
        # raise different exceptions
        try:
            print(f"Collection not found or error: {str(e)}")
            print(f"Creating new collection: {collection_name}")
            collection = client.create_collection(
                name=collection_name, embedding_function=embedding_func
            )
            return collection
        except Exception as create_error:
            print(f"Error creating collection: {str(create_error)}")
            # Try one more time to get the collection in case it was created in between
            try:
                collection = client.get_collection(
                    name=collection_name, embedding_function=embedding_func
                )
                print(f"Using existing collection: {collection_name}")
                return collection
            except Exception as final_error:
                print(f"Fatal error with ChromaDB: {str(final_error)}")
                raise


# ------------------------------------------------------------
# 2) PDF Text Extraction
# ------------------------------------------------------------


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Reads the entire PDF and returns the concatenated text of all pages.
    """
    if not os.path.exists(pdf_path):
        print(f"Error: File not found: {pdf_path}")
        return ""

    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        return text
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return ""


# ------------------------------------------------------------
# 3) Regex Patterns for Key Fields
# ------------------------------------------------------------


def extract_invoice_number(text: str) -> str:
    """
    Extract invoice number from text using regex patterns.
    Returns the invoice number as a string, or 'unknown' if not found.
    """
    # Common invoice number patterns
    patterns = [
        r"(?i)invoice\s*(?:#|number|num|no|no\.)\s*[:;]?\s*([A-Za-z0-9][\w\-\.\/]+)",
        r"(?i)(?:invoice|inv)(?:\s*#|\s+number|\s+num|\s+no|\s+no\.)?\s*[:;]?\s*([A-Za-z0-9][\w\-\.\/]+)",
        r"(?i)(?:invoice|inv)(?:\s*#|\s+number|\s+num|\s+no|\s+no\.)?[:;]?\s*([A-Za-z0-9][\w\-\.\/]+)",
        r"(?i)(?:invoice|inv)[\s#:]*([A-Za-z0-9][\w\-\.\/]+)",
        r"(?i)(?:#|number|num|no|no\.)[:;]?\s*([A-Za-z0-9][\w\-\.\/]+)",
        r"(?i)invoice\s*(?:number|num|no|no\.)?[:;]?\s*([A-Za-z0-9][\w\-\.\/]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()

    return "unknown"


def extract_invoice_date(text: str) -> str:
    """
    Extract invoice date from text using regex patterns.
    Returns the date as a string, or 'unknown' if not found.
    """
    # Common date patterns
    date_patterns = [
        # DD/MM/YYYY or DD-MM-YYYY
        r"(?i)(?:invoice|payment)\s*date\s*[:;]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"(?i)date\s*(?:of\s*invoice|issued|created)?\s*[:;]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"(?i)dated?\s*[:;]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        # Month name formats
        r"(?i)(?:invoice|payment)\s*date\s*[:;]?\s*(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{2,4})",
        r"(?i)date\s*(?:of\s*invoice|issued|created)?\s*[:;]?\s*(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{2,4})",
        r"(?i)dated?\s*[:;]?\s*(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{2,4})",
        # Standalone dates
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{2,4})",
    ]

    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()

    return "unknown"


def extract_invoice_amount(text: str) -> str:
    """
    Extract the invoice amount from the text.
    Returns the amount as a string with the original currency symbol (£ or $),
    or 'unknown' if not found.
    """
    # Normalize text for better matching
    text = text.replace(",", "")

    # Common amount patterns
    amount_patterns = [
        # British Pound (£)
        r"(?i)(?:total|amount|sum|invoice\s*total)\s*(?:due|payable|:)?\s*(?:£|GBP)?\s*(£?\s*\d+\.\d{2})",
        r"(?i)(?:£|GBP)\s*(\d+\.\d{2})",
        r"(?:^|\n)(?:£|GBP)\s*(\d+\.\d{2})(?:\s|$)",
        # US Dollar ($)
        r"(?i)(?:total|amount|sum|invoice\s*total)\s*(?:due|payable|:)?\s*(?:\$|USD)?\s*(\$?\s*\d+\.\d{2})",
        r"(?i)(?:\$|USD)\s*(\d+\.\d{2})",
        r"(?:^|\n)(?:\$|USD)\s*(\d+\.\d{2})(?:\s|$)",
        # Euro (€)
        r"(?i)(?:total|amount|sum|invoice\s*total)\s*(?:due|payable|:)?\s*(?:€|EUR)?\s*(€?\s*\d+\.\d{2})",
        r"(?i)(?:€|EUR)\s*(\d+\.\d{2})",
        r"(?:^|\n)(?:€|EUR)\s*(\d+\.\d{2})(?:\s|$)",
        # Generic (no currency symbol)
        r"(?i)(?:total|amount|sum|invoice\s*total)\s*(?:due|payable|:)?\s*(\d+\.\d{2})",
    ]

    # First try to find amounts with currency symbols
    for pattern in amount_patterns:
        match = re.search(pattern, text)
        if match:
            amount = match.group(1).strip()

            # Add currency symbol if missing
            if "£" in pattern and "£" not in amount:
                amount = f"£{amount}"
            elif "$" in pattern and "$" not in amount:
                amount = f"${amount}"
            elif "€" in pattern and "€" not in amount:
                amount = f"€{amount}"

            return amount

    # If no match, try to find any number that looks like a total
    lines = text.split("\n")
    for line in reversed(lines):  # Start from the bottom of the invoice
        if re.search(r"(?i)total|amount|sum|due|payable", line):
            match = re.search(r"(\d+\.\d{2})", line)
            if match:
                # Default to £ if no currency symbol found
                return f"£{match.group(1)}"

    return "unknown"


def parse_invoice_fields(text: str) -> dict:
    """
    Uses regex to extract:
    - invoice_number
    - invoice_date
    - invoice_amount
    from the raw text.
    """
    invoice_number = extract_invoice_number(text)
    invoice_date = extract_invoice_date(text)
    invoice_amount = extract_invoice_amount(text)

    return {
        "invoice_number": invoice_number,
        "invoice_date": invoice_date,
        "invoice_amount": invoice_amount,
    }


# ------------------------------------------------------------
# 4) Heuristic Extraction for Client Name & Address
# ------------------------------------------------------------


def extract_client_info(text: str) -> dict:
    """
    Attempts to identify 'client_name' and 'client_address' by scanning text lines.
    Uses heuristics to identify client information sections.
    Enhanced to better handle various invoice formats and layouts.
    """
    result = {"client_name": "", "client_address": "unknown"}

    # Split text into lines for analysis
    lines = text.strip().split("\n")

    # Skip empty lines
    lines = [line.strip() for line in lines if line.strip()]

    # Initialize variables to track state
    client_section_started = False
    potential_client_name = ""
    potential_client_address = []
    client_line_index = -1

    # Keywords that might indicate client information
    client_indicators = [
        r"(?i)bill\s+to",
        r"(?i)invoice\s+to",
        r"(?i)client\s*:",
        r"(?i)client\s*name",
        r"(?i)customer\s*:",
        r"(?i)recipient\s*:",
        r"(?i)billed\s+to",
        r"(?i)client\s+details",
        r"(?i)customer\s+details",
    ]

    # Keywords that indicate we've moved past client info
    end_indicators = [
        r"(?i)invoice\s+details",
        r"(?i)description",
        r"(?i)item",
        r"(?i)quantity",
        r"(?i)amount",
        r"(?i)price",
        r"(?i)total",
        r"(?i)payment\s+terms",
        r"(?i)due\s+date",
        r"(?i)service",
    ]

    # Patterns to exclude from client name
    exclude_patterns = [
        r"(?i)^invoice\b",
        r"(?i)^bill\s+to",
        r"(?i)^date",
        r"(?i)^number",
        r"(?i)^payment\s+terms",
        r"(?i)^due\s+date",
        r"(?i)^utr",
        r"(?i)^email",
        r"(?i)^phone",
        r"(?i)^tel",
        r"(?i)^fax",
        r"(?i)^vat",
        r"(?i)^tax",
    ]

    # UTR pattern to remove from client name and address
    utr_pattern = r"\b(?:UTR|utr)[\s:-]+(?:\d{9,10}|XXXXXXXXX|[0-9X]{9,10})\b"

    # Common client names from the invoices we've seen
    known_clients = [
        "ALR Music Ltd",
        "ALR Music",
        "Warner Music UK LTD",
        "Warner Music",
        "The Peninsula",
        "Peninsula",
        "Park Chinois",
        "Sky Garden",
        "Quaglinos",
        "100 Wardour Street",
        "Maison Eselle",
        "Maison Estelle",
    ]

    # Common address patterns
    address_patterns = [
        # UK street patterns
        r"\b\d+\s+[A-Za-z\s]+(?:street|st|road|rd|avenue|ave|lane|ln|drive|dr|way|place|pl|court|ct)\b",
        # UK postal code patterns
        r"\b[A-Z]{1,2}\d{1,2}[A-Z]?\s?\d[A-Z]{2}\b",
        # Common city names
        r"\b(?:London|Manchester|Birmingham|Leeds|Glasgow|Edinburgh|Liverpool|Bristol|Sheffield|Newcastle|Nottingham|Cardiff|Belfast)\b",
    ]

    # Check for known clients first
    for client in known_clients:
        if re.search(r"\b" + re.escape(client) + r"\b", text, re.IGNORECASE):
            potential_client_name = client
            # Find the line index where this client name appears
            for i, line in enumerate(lines):
                if re.search(r"\b" + re.escape(client) + r"\b", line, re.IGNORECASE):
                    client_line_index = i
                    break
            break

    # First pass: try to identify client section
    if not potential_client_name:
        for i, line in enumerate(lines):
            # Check if this line indicates start of client info
            for indicator in client_indicators:
                if re.search(indicator, line):
                    client_section_started = True
                    client_line_index = i

                    # If the indicator is at the beginning of the line, the client name might be after it
                    match = re.search(
                        r"(?i)(?:bill|invoice|billed|client)\s+(?:to|name|:)\s*:?\s*(.*)",
                        line,
                    )
                    if match and match.group(1).strip():
                        potential_client_name = match.group(1).strip()
                    break

            # If we've found the start of client section
            if client_section_started:
                # Check if we've reached the end of client info
                end_reached = False
                for indicator in end_indicators:
                    if re.search(indicator, line):
                        end_reached = True
                        break

                if end_reached:
                    client_section_started = False
                    continue

                # Skip lines that match exclude patterns
                skip_line = False
                for pattern in exclude_patterns:
                    if re.search(pattern, line):
                        skip_line = True
                        break

                if skip_line:
                    continue

                # If we don't have a client name yet, use this line
                if not potential_client_name and line:
                    potential_client_name = line
                    client_line_index = i
                # Otherwise, add to address
                elif potential_client_name and line and line != potential_client_name:
                    potential_client_address.append(line)

    # Second pass: if we didn't find a client section, use heuristics
    if not potential_client_name:
        # Look at the first 10 non-empty lines for potential client name
        for i, line in enumerate(lines[:10]):
            # Skip lines that match exclude patterns
            skip_line = False
            for pattern in exclude_patterns:
                if re.search(pattern, line):
                    skip_line = True
                    break

            if skip_line:
                continue

            # If line is short enough to be a name and doesn't look like an address
            if 2 < len(line.split()) < 8 and not re.search(r"\d{5,}", line):
                potential_client_name = line
                client_line_index = i

                # Next 1-3 lines might be the address
                for j in range(i + 1, min(i + 4, len(lines))):
                    if j < len(lines) and lines[j] != potential_client_name:
                        potential_client_address.append(lines[j])

                break

    # Special case for ALR Music Ltd which appears in many invoices
    if not potential_client_name and "ALR Music Ltd" in text:
        potential_client_name = "ALR Music Ltd"
        # Find the line index where this client name appears
        for i, line in enumerate(lines):
            if "ALR Music Ltd" in line:
                client_line_index = i
                break

    # Special case for Warner Music which appears in some invoices
    if not potential_client_name and "Warner Music" in text:
        potential_client_name = "Warner Music UK LTD"
        # Find the line index where this client name appears
        for i, line in enumerate(lines):
            if "Warner Music" in line:
                client_line_index = i
                break

    # Remove any UTR references from client name and address
    if potential_client_name:
        potential_client_name = re.sub(utr_pattern, "", potential_client_name).strip()
        # Remove any date patterns from client name (e.g., "20/2/2025")
        potential_client_name = re.sub(
            r"\d{1,2}/\d{1,2}/\d{2,4}", "", potential_client_name
        ).strip()
        # Remove any invoice numbers from client name
        potential_client_name = re.sub(
            r"(?i)invoice\s*(?:#|number|num|no|no\.)?[:;]?\s*\d+",
            "",
            potential_client_name,
        ).strip()

    # If we have a client name but no address yet, scan the entire document for address patterns
    if (
        potential_client_name
        and client_line_index >= 0
        and not potential_client_address
    ):
        # First, check lines near the client name (both before and after)
        search_range = 10  # Look 10 lines before and after
        start_idx = max(0, client_line_index - search_range)
        end_idx = min(len(lines), client_line_index + search_range)

        # Check if the client is ALR Music Ltd - special case
        if "ALR Music Ltd" in potential_client_name:
            # For ALR, look for "Lexington Street" which is a distinctive part of their address
            for i, line in enumerate(lines):
                if "Lexington Street" in line:
                    # This is likely the ALR address line
                    potential_client_address.append(line)
                    # Check the next line for additional address info
                    if i + 1 < len(lines) and len(lines[i + 1]) < 30:
                        potential_client_address.append(lines[i + 1])
                    break
        else:
            # For other clients, scan lines near the client name for address patterns
            for i in range(start_idx, end_idx):
                line = lines[i]
                # Skip if this is the client name line
                if i == client_line_index:
                    continue

                # Check if line matches address patterns
                is_address_line = False
                for pattern in address_patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        is_address_line = True
                        break

                # If it looks like an address and isn't too long
                if is_address_line and len(line) < 100:
                    potential_client_address.append(line)

        # If we still don't have an address, scan the entire document
        if not potential_client_address:
            for i, line in enumerate(lines):
                # Skip if this is the client name line
                if i == client_line_index:
                    continue

                # Check if line matches address patterns
                is_address_line = False
                for pattern in address_patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        is_address_line = True
                        break

                # If it looks like an address and isn't too long
                if is_address_line and len(line) < 100:
                    potential_client_address.append(line)
                    # Only take the first matching line to avoid getting too many false positives
                    break

    # Process the potential address lines
    potential_client_address = [
        re.sub(utr_pattern, "", addr).strip() for addr in potential_client_address
    ]

    # Filter out address lines that are likely not part of the address
    filtered_address = []
    for addr in potential_client_address:
        # Skip lines that are likely not part of the address
        if (
            re.search(r"(?i)invoice", addr)
            or re.search(r"(?i)date", addr)
            or re.search(r"(?i)number", addr)
            or re.search(r"(?i)payment", addr)
            or re.search(r"(?i)due", addr)
            or re.search(r"(?i)total", addr)
            or re.search(r"(?i)amount", addr)
            or re.search(r"(?i)service", addr)
            or re.search(r"(?i)description", addr)
            or re.search(r"(?i)quantity", addr)
            or re.search(r"(?i)price", addr)
            or re.search(r"(?i)utr", addr)
        ):
            continue
        filtered_address.append(addr)

    potential_client_address = filtered_address

    # Special case handling for known clients with consistent addresses
    if "ALR Music Ltd" in potential_client_name and not potential_client_address:
        # If we couldn't find the address through normal means, use the known address
        potential_client_address = ["36 Lexington Street London"]

    # Set the results
    if potential_client_name:
        result["client_name"] = potential_client_name

    if potential_client_address:
        result["client_address"] = "\n".join(potential_client_address)

    return result


def extract_client_name(text: str) -> str:
    """Helper function to extract just the client name"""
    return extract_client_info(text).get("client_name", "")


def extract_client_address(text: str) -> str:
    """Helper function to extract just the client address"""
    return extract_client_info(text).get("client_address", "unknown")


# ------------------------------------------------------------
# 5) Extract Service Information
# ------------------------------------------------------------


def extract_service_info(text: str) -> list:
    """
    Attempts to extract service information from the invoice text.
    Returns a list of dictionaries, each containing:
    - service_name: The name/description of the service
    - service_price: The price of the service
    """
    services = []
    seen_service_names = set()  # Track service names to avoid duplicates

    # Split text into lines for analysis
    lines = text.strip().split("\n")

    # Skip empty lines
    lines = [line.strip() for line in lines if line.strip()]

    # Keywords that might indicate the start of service items
    service_section_indicators = [
        r"(?i)description",
        r"(?i)item",
        r"(?i)service",
        r"(?i)product",
        r"(?i)work\s+performed",
    ]

    # Keywords that might indicate the end of service items
    end_section_indicators = [
        r"(?i)subtotal",
        r"(?i)total",
        r"(?i)balance",
        r"(?i)amount\s+due",
        r"(?i)payment\s+terms",
        r"(?i)thank\s+you",
    ]

    # Price patterns
    price_patterns = [
        r"(?:£|$|€)\s*(\d+(?:\.\d{2})?)",
        r"(\d+(?:\.\d{2})?)\s*(?:£|$|€)",
        r"(\d+(?:\.\d{2})?)",
    ]

    # Patterns to exclude from service descriptions
    exclude_patterns = [
        # Address patterns
        r"(?i)\b\d+\s+[A-Za-z\s]+(?:road|street|avenue|lane|way)\b",
        r"(?i)\b[A-Z]{1,2}\d{1,2}[A-Z]?\s?\d[A-Z]{2}\b",  # UK postal code
        r"(?i)\bLondon\b",
        # Contact information
        r"\b07\d{9}\b",  # UK mobile number
        r"\b\d{5}\s?\d{6}\b",  # Other phone number formats
        r"\S+@\S+\.\S+",  # Email address
        # Common non-service text
        r"(?i)invoice\s+\d+",
        r"(?i)date",
        r"(?i)number",
        r"(?i)payment",
        r"(?i)due",
        r"(?i)total",
        r"(?i)amount",
        r"(?i)utr",
        r"(?i)account",
        r"(?i)bank",
        r"(?i)sort",
        r"(?i)code",
        r"(?i)iban",
        r"(?i)swift",
    ]

    # Known service patterns
    service_patterns = [
        r"(?i)\b(?:gig|performance|recording|session|piano|quartet|trio|music|band|choir|concert|event|solo)\b",
        r"(?i)\b(?:park chinois|sky garden|quaglinos|wardour|peninsula|maison|estelle)\b",
        r"(?i)\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}\s+.*(?:gig|performance|piano|quartet|trio|band|choir)",
    ]

    # Initialize variables to track state
    in_service_section = False

    # Process each line
    for i, line in enumerate(lines):
        # Check if this line indicates start of service section
        if not in_service_section:
            for indicator in service_section_indicators:
                if re.search(indicator, line):
                    in_service_section = True
                    break

            # Skip this line if it's just a header
            if in_service_section:
                continue

        # Check if we've reached the end of service section
        if in_service_section:
            for indicator in end_section_indicators:
                if re.search(indicator, line):
                    in_service_section = False
                    break

            if not in_service_section:
                continue

            # Try to extract service and price from this line
            # First, look for price patterns
            price_match = None
            for pattern in price_patterns:
                match = re.search(pattern, line)
                if match:
                    price_match = match
                    break

            if price_match:
                # If we found a price, the rest is likely the service description
                price_value = price_match.group(1)

                # Extract service description (everything before the price)
                service_desc = line[: price_match.start()].strip()
                if not service_desc:
                    # If no description on this line, use previous line
                    if i > 0:
                        service_desc = lines[i - 1].strip()

                # Clean up service description
                service_desc = re.sub(
                    r"(?:£|$|€)\s*\d+(?:\.\d{2})?", "", service_desc
                ).strip()

                # Check if this is a valid service description
                is_valid_service = True

                # Skip if it contains any exclude patterns
                for pattern in exclude_patterns:
                    if re.search(pattern, service_desc):
                        is_valid_service = False
                        break

                # Skip if it's just the invoice number
                if re.match(r"^INVOICE\s+\d+$", service_desc, re.IGNORECASE):
                    is_valid_service = False

                # Skip if it's too short or too long
                if len(service_desc) < 5 or len(service_desc.split()) > 10:
                    is_valid_service = False

                # Skip if it's a year or date that might be misinterpreted as a price
                if (
                    re.match(r"^\d{4}$", price_value)  # Year like 2023
                    or re.match(r"^\d{1,2}\.\d{2}$", price_value)
                    and float(price_value) < 100  # Small decimal that could be a date
                    or re.match(r"^\d{1,2}\.\d{2}$", price_value)
                    and re.search(
                        r"\d{1,2}\.\d{2}", service_desc
                    )  # Decimal in both price and description
                    or re.match(r"^\d{2}\.\d{2}$", price_value)
                    and re.search(
                        r"\d{2}\.\d{2}(?:\.\d{2})?", service_desc
                    )  # Date format in description
                    or (
                        service_desc.startswith(price_value)
                        or service_desc.endswith(price_value)
                    )  # Price is part of the description
                    or (  # Specific check for date formats that look like prices
                        re.match(r"^\d{2}\.\d{2}$", price_value)
                        and (
                            re.search(
                                r"\d{2}[.-]\d{2}[.-]\d{2}", service_desc
                            )  # DD.MM.YY or DD-MM-YY
                            or re.search(r"\d{2}/\d{2}/\d{2}", service_desc)  # DD/MM/YY
                        )
                    )
                    # Special case for "28.04.23 - Kate Trio - Quaglinos" type entries
                    or (
                        re.match(r"^\d{2}\.\d{2}$", price_value)
                        and service_desc.startswith(f"{price_value}.")
                    )
                    or (
                        re.match(r"^\d{2}\.\d{2}$", price_value)
                        and re.match(r"^\d{2}\.\d{2}\.\d{2}", service_desc)
                    )
                    # Special case for service descriptions that start with a date
                    or (
                        re.match(r"^\d{2}\.\d{2}$", price_value)
                        and re.search(r"^\d{2}\.\d{2}\.\d{2}\s*-", service_desc)
                    )
                ):
                    is_valid_service = False

                # Skip if it contains the user's personal information
                if (
                    "277 shooters hill road" in service_desc.lower()
                    or "07946670601" in service_desc
                    or "dadekugbe@gmail.com" in service_desc
                ):
                    is_valid_service = False

                # Check if it matches any service patterns
                matches_service_pattern = False
                for pattern in service_patterns:
                    if re.search(pattern, service_desc):
                        matches_service_pattern = True
                        break

                # Add to services list if it's a valid service
                if (
                    is_valid_service
                    and (matches_service_pattern or in_service_section)
                    and service_desc
                    and price_value
                    and service_desc not in seen_service_names  # Check for duplicates
                ):
                    # Convert price to float to ensure it's a valid number
                    try:
                        float_price = float(price_value)
                        if (
                            10 <= float_price <= 2000
                        ):  # Reasonable price range for services
                            services.append(
                                {
                                    "service_name": service_desc,
                                    "service_price": f"£{price_value}",
                                }
                            )
                            seen_service_names.add(
                                service_desc
                            )  # Add to seen service names
                    except ValueError:
                        # Not a valid price
                        pass

    # If we couldn't find services using the structured approach,
    # try a more heuristic approach
    if not services:
        # Look for lines that have both text and a price
        for line in lines:
            for pattern in price_patterns:
                match = re.search(pattern, line)
                if match:
                    price_value = match.group(1)

                    # Extract service description (everything except the price)
                    service_desc = re.sub(
                        r"(?:£|$|€)\s*\d+(?:\.\d{2})?", "", line
                    ).strip()

                    # Check if this is a valid service description
                    is_valid_service = True

                    # Skip if it contains any exclude patterns
                    for pattern in exclude_patterns:
                        if re.search(pattern, service_desc):
                            is_valid_service = False
                            break

                    # Skip if it's just the invoice number
                    if re.match(r"^INVOICE\s+\d+$", service_desc, re.IGNORECASE):
                        is_valid_service = False

                    # Skip if it's too short or too long
                    if len(service_desc) < 5 or len(service_desc.split()) > 10:
                        is_valid_service = False

                    # Skip if it's a year (like 2024) that might be misinterpreted as a price
                    if re.match(r"^\d{4}$", price_value):
                        is_valid_service = False

                    # Skip if it contains the user's personal information
                    if (
                        "277 shooters hill road" in service_desc.lower()
                        or "07946670601" in service_desc
                        or "dadekugbe@gmail.com" in service_desc
                    ):
                        is_valid_service = False

                    # Check if it matches any service patterns
                    matches_service_pattern = False
                    for pattern in service_patterns:
                        if re.search(pattern, service_desc):
                            matches_service_pattern = True
                            break

                    # Add to services list if it's a valid service
                    if (
                        is_valid_service
                        and matches_service_pattern
                        and service_desc
                        and price_value
                        and len(service_desc) > 3
                        and service_desc
                        not in seen_service_names  # Check for duplicates
                    ):
                        # Skip if this looks like a total
                        if not re.search(
                            r"(?i)total|subtotal|balance|amount\s+due", service_desc
                        ):
                            # Convert price to float to ensure it's a valid number
                            try:
                                float_price = float(price_value)
                                if (
                                    10 <= float_price <= 2000
                                ):  # Reasonable price range for services
                                    services.append(
                                        {
                                            "service_name": service_desc,
                                            "service_price": f"£{price_value}",
                                        }
                                    )
                                    seen_service_names.add(
                                        service_desc
                                    )  # Add to seen service names
                            except ValueError:
                                # Not a valid price
                                pass

    return services


# ------------------------------------------------------------
# 6) Generate Embeddings
# ------------------------------------------------------------


def generate_embedding(text: str) -> list:
    """
    Generate an embedding for the given text.
    If a real embedding model is available, use it; otherwise, use a fallback.
    """
    global USING_REAL_EMBEDDINGS, embedding_model

    # Try to use a real embedding model if available
    if USING_REAL_EMBEDDINGS:
        try:
            return embedding_model.encode(text).tolist()
        except Exception as e:
            print(f"Error generating real embedding: {e}")
            # Fall back to random embeddings

    # Fallback: Generate a deterministic "fake" embedding based on the text
    # This ensures the same text always gets the same embedding
    text_hash = hash(text) % 10000
    np.random.seed(text_hash)

    # Generate a random embedding of dimension 384 (common for sentence embeddings)
    embedding = np.random.normal(0, 1, 384).astype(np.float32)

    # Normalize to unit length (common practice for embeddings)
    embedding = embedding / np.linalg.norm(embedding)

    return embedding.tolist()


# ------------------------------------------------------------
# 7) Store Invoice Data in ChromaDB
# ------------------------------------------------------------


def store_invoice_data(pdf_path: str, text: str = None) -> dict:
    """
    Process a PDF invoice and store its data in ChromaDB.
    Returns a dictionary with the extracted invoice data.
    """
    # Extract text if not provided
    if text is None:
        text = extract_text_from_pdf(pdf_path)
        if not text:
            return {"error": f"Failed to extract text from {pdf_path}"}

    # Parse invoice fields
    invoice_fields = parse_invoice_fields(text)

    # Extract client information
    client_info = extract_client_info(text)

    # Extract service information
    services = extract_service_info(text)

    # Combine all extracted data
    invoice_data = {
        **invoice_fields,
        **client_info,
        "services": services,
        "full_text": text,
        "source_file": os.path.basename(pdf_path),
    }

    # Generate a unique ID for this invoice
    invoice_id = (
        f"{invoice_data['client_name']}_{invoice_data['invoice_number']}".replace(
            " ", "_"
        )
    )

    # Store in ChromaDB
    try:
        # Convert services to JSON string for storage
        services_json = json.dumps(services)

        # Prepare metadata
        metadata = {
            "client_name": invoice_data["client_name"],
            "client_address": invoice_data["client_address"],
            "invoice_number": invoice_data["invoice_number"],
            "invoice_date": invoice_data["invoice_date"],
            "invoice_amount": invoice_data["invoice_amount"],
            "services": services_json,
            "source_file": os.path.basename(pdf_path),
        }

        # Add to collection
        get_collection().add(documents=[text], metadatas=[metadata], ids=[invoice_id])

        print(f"Successfully stored invoice data for {invoice_id}")
    except Exception as e:
        print(f"Error storing invoice in ChromaDB: {e}")
        invoice_data["error"] = f"Failed to store in database: {e}"

    return invoice_data


# ------------------------------------------------------------
# 8) Query Functions
# ------------------------------------------------------------


def search_invoices(query: str, n_results: int = 5) -> list:
    """
    Search for invoices matching the query.
    Returns a list of invoice data dictionaries.
    """
    try:
        # All searches will use direct metadata matching rather than vector search
        # This is more reliable, especially for short queries
        collection = get_collection()
        all_data = collection.get()

        if not all_data or "metadatas" not in all_data or not all_data["metadatas"]:
            print("No data found in the collection")
            return []

        matches = []
        query_lower = query.lower()

        # Process all documents
        for i, metadata in enumerate(all_data["metadatas"]):
            client_name = metadata.get("client_name", "")
            if not client_name:
                continue

            score = 0

            # CASE 1: Check for exact matches first
            if query_lower == client_name.lower():
                score = 1.0

            # CASE 2: Check if query appears anywhere in the client name
            elif query_lower in client_name.lower():
                # Score based on how much of the client name is matched
                score = len(query) / len(client_name) * 0.9

            # CASE 3: Check if query could be an abbreviation (e.g., ALR for Alr Music Ltd)
            elif len(query) <= 5:  # Only try abbreviation matching for short queries
                words = client_name.split()
                if len(words) >= len(query):
                    # Check first letters
                    first_letters = "".join(word[0] for word in words[: len(query)])
                    if first_letters.lower() == query_lower:
                        score = 0.8

            # If we have a match with a reasonable score
            if score > 0:
                # Create a properly structured result
                result = dict(metadata)

                # Parse services JSON
                if "services" in result and result["services"]:
                    try:
                        result["services"] = json.loads(result["services"])
                    except (json.JSONDecodeError, TypeError):
                        result["services"] = []
                else:
                    result["services"] = []

                matches.append({"score": score, "result": result})

        # Sort by score and return the top n results
        matches.sort(key=lambda x: x["score"], reverse=True)
        return [match["result"] for match in matches[:n_results]]

    except Exception as e:
        print(f"Error in search_invoices: {e}")
        return []


def retrieve_similar_invoices(query: str, n_results: int = 5) -> list:
    """
    Retrieve invoices similar to the query using vector similarity search.
    Returns a list of dictionaries containing invoice data, metadata, and relevance score.
    """
    try:
        # Handle the case where n_results might be too large for the database
        # Start with the requested number and reduce if needed
        current_n_results = min(n_results, 20)  # Cap at 20 to be safe

        while current_n_results > 0:
            try:
                # Query the collection with include parameter to get distances
                results = get_collection().query(
                    query_texts=[query],
                    n_results=current_n_results,
                    include=["metadatas", "documents", "distances"],
                )
                break  # If successful, exit the loop
            except Exception as e:
                # If error contains specific message about contiguous array
                if "contigious 2D array" in str(e) or "ef or M is too small" in str(e):
                    # Reduce n_results and try again
                    current_n_results = max(1, current_n_results // 2)
                    print(f"Reducing results to {current_n_results} and retrying...")
                else:
                    # For other errors, re-raise
                    raise e

        # Process results
        invoices = []
        if (
            results
            and "metadatas" in results
            and results["metadatas"]
            and len(results["metadatas"]) > 0
        ):
            # Get distances for relevance scores (convert to similarity score)
            distances = results.get(
                "distances", [[1.0] * len(results["metadatas"][0])]
            )[0]

            for i, metadata in enumerate(results["metadatas"][0]):
                # Calculate relevance score (1.0 is perfect match, 0.0 is no match)
                # Convert distance to similarity score
                distance = distances[i] if i < len(distances) else 1.0
                relevance_score = max(0.0, 1.0 - distance)

                # Parse services from JSON
                services = []
                if "services" in metadata and metadata["services"]:
                    try:
                        services = json.loads(metadata["services"])
                    except json.JSONDecodeError as e:
                        print(f"Error parsing services JSON: {e}")
                        pass

                # Create invoice data dictionary with metadata and relevance score
                invoice_data = {
                    "client_name": metadata.get("client_name", "unknown"),
                    "client_address": metadata.get("client_address", "unknown"),
                    "invoice_number": metadata.get("invoice_number", "unknown"),
                    "invoice_date": metadata.get("invoice_date", "unknown"),
                    "invoice_amount": metadata.get("invoice_amount", "unknown"),
                    "services": services,
                    "source_file": metadata.get("source_file", "unknown"),
                    "metadata": metadata,  # Include the full metadata
                    "relevance_score": relevance_score,  # Add relevance score
                }

                # Add the document text if available
                if (
                    "documents" in results
                    and len(results["documents"]) > 0
                    and i < len(results["documents"][0])
                ):
                    invoice_data["document"] = results["documents"][0][i]

                invoices.append(invoice_data)

        return invoices
    except Exception as e:
        print(f"Error retrieving similar invoices: {e}")
        return []


def get_all_invoices() -> list:
    """
    Retrieve all invoices from the database.
    Returns a list of invoice data dictionaries.
    """
    try:
        # Get all items from the collection
        results = get_collection().get()

        # Process results
        invoices = []
        if results and "metadatas" in results and results["metadatas"]:
            for metadata in results["metadatas"]:
                # Parse services from JSON
                services = []
                if "services" in metadata and metadata["services"]:
                    try:
                        services = json.loads(metadata["services"])
                    except json.JSONDecodeError as e:
                        print(f"Error parsing services JSON: {e}")
                        pass

                # Create invoice data dictionary
                invoice_data = {
                    "client_name": metadata.get("client_name", "unknown"),
                    "client_address": metadata.get("client_address", "unknown"),
                    "invoice_number": metadata.get("invoice_number", "unknown"),
                    "invoice_date": metadata.get("invoice_date", "unknown"),
                    "invoice_amount": metadata.get("invoice_amount", "unknown"),
                    "services": services,
                    "source_file": metadata.get("source_file", "unknown"),
                }

                invoices.append(invoice_data)

        return invoices
    except Exception as e:
        print(f"Error retrieving all invoices: {e}")
        return []


# ------------------------------------------------------------
# 9) Process a Directory of Invoices
# ------------------------------------------------------------


def process_invoice_directory(directory_path: str):
    """
    Process all PDF files in a directory and add them to the vector database.
    """
    if not os.path.exists(directory_path):
        print(f"Directory {directory_path} does not exist.")
        return

    pdf_files = [
        os.path.join(directory_path, f)
        for f in os.listdir(directory_path)
        if f.lower().endswith(".pdf")
    ]

    if not pdf_files:
        print(f"No PDF files found in {directory_path}.")
        return

    print(f"Found {len(pdf_files)} PDF files. Processing...")

    for pdf_path in pdf_files:
        try:
            print(f"Processing {os.path.basename(pdf_path)}...")
            store_invoice_data(pdf_path)
        except Exception as e:
            print(f"Error processing {pdf_path}: {str(e)}")

    print("Processing complete.")


# ------------------------------------------------------------
# 10) Reprocess All Invoices
# ------------------------------------------------------------


def reprocess_all_invoices(directory_path: str):
    """
    Reprocess all invoices in a directory using the updated client extraction logic.
    This will clear the existing collection and reindex all PDFs.
    """
    global _collection

    # Clear the existing collection by deleting all documents
    try:
        # Get all document IDs
        all_ids = get_collection().get()["ids"]
        if all_ids:
            get_collection().delete(ids=all_ids)
            print(f"Cleared {len(all_ids)} documents from the collection.")
        else:
            print("Collection is already empty.")
    except Exception as e:
        print(f"Error clearing collection: {e}")

    # Process all invoices in the directory
    process_invoice_directory(directory_path)


# ------------------------------------------------------------
# 11) Example Usage
# ------------------------------------------------------------

if __name__ == "__main__":
    # Example 1: Process a single invoice
    # pdf_path = "/path/to/your/invoice.pdf"
    # store_invoice_data(pdf_path)

    # Example 2: Process a directory of invoices
    # invoice_dir = "/path/to/your/invoices"
    # process_invoice_directory(invoice_dir)

    # Example 3: Retrieve similar invoices
    # results = search_invoices("ABC Corporation")
    # for result in results:
    #     print(f"Client: {result['client_name']}")
    #     print(f"Invoice #: {result['invoice_number']}")
    #     print("---")

    # Example usage with your existing files
    pdf_files = [
        "/path/to/16.02.25 - Solo Piano - The Peninsula.pdf",
        "/path/to/Peninsula 15:11:23.pdf",
        "/path/to/Daniel Godson and Vito Bambino Prod Invoice .pdf",
    ]

    # Uncomment to process these files
    # for pdf_path in pdf_files:
    #     if os.path.exists(pdf_path):
    #         store_invoice_data(pdf_path)
    #     else:
    #         print(f"File not found: {pdf_path}")

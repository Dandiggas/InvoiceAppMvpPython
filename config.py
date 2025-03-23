"""
Configuration settings for the Invoice App.
"""

import os


# Define a config class to hold configuration settings
class Config:
    # Path to store ChromaDB database
    CHROMA_DB_PATH = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "chroma_db"
    )

    # Path to invoices directory
    INVOICES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "invoices")


# Create a config instance
config = Config()

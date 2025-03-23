# Invoice App with RAG-Enhanced Chatbot

This application helps create and manage invoices with a chatbot assistant that uses Retrieval-Augmented Generation (RAG) to remember client details from previous invoices.

## Features

- **PDF Invoice Generation**: Create professional PDF invoices with client and service details
- **Email Sending**: Send invoices directly to clients via email
- **RAG-Enhanced Chatbot**: Automatically retrieves client information from previous invoices
- **PDF Parsing**: Extract client information, invoice details, and service information from existing PDF invoices

## Components

- `chat_bot.py`: The main chatbot application using LangChain and LangGraph with Claude 3.7 Sonnet
- `pdf_parser.py`: Module for extracting data from PDF invoices and storing it in a ChromaDB vector database
- `createpdf.py`: Module for creating PDF invoices
- `sendMail.py`: Module for sending invoices via email
- `config.py`: Configuration settings for the application
- `process_invoices.py`: Script to process all invoices in the invoices directory
- `reprocess_invoices.py`: Script to reprocess all invoices with improved extraction logic
- `test_pdf_parser.py`: Script to test the PDF parser on sample invoices

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Process existing invoices:
   ```
   python process_invoices.py
   ```

3. Run the chatbot:
   ```
   python chat_bot.py
   ```

## Using the RAG-Enhanced Chatbot

When you mention a client name in your message, the chatbot will automatically retrieve information about that client from your previous invoices. This includes:

- Client name and address
- Previous services and prices
- Invoice history

For example, you can say:
```
I want to create an invoice for ALR Music
```

The chatbot will recognize "ALR Music" as a client name, retrieve information about this client, and use it to help you create a new invoice with minimal input.

## Reprocessing Invoices

If you add new invoices or want to update the database with improved extraction logic, you can run:

```
python reprocess_invoices.py
```

This will clear the existing database and reprocess all invoices in the invoices directory.

## Environment Variables

The application uses the following environment variables:

- `USER_DETAILS`: Your company name and address (used in invoice generation)
- `ACCOUNT_DETAILS`: Your bank account details (used in invoice generation)
- `USERNAMEEMAIL`: Your email address (used for sending invoices)
- `PASSWORD`: Your email password (used for sending invoices)

## Customization

You can customize the application by:

- Adding more client names to the `known_clients` list in `chat_bot.py`
- Modifying the service extraction patterns in `chat_bot.py`
- Updating the system prompt in `chat_bot.py`

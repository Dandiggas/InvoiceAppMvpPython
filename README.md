# Invoice App MVP

A versatile Python application for generating and sending professional invoices. The app provides multiple interfaces including a GUI, CLI, and an AI-powered agent for natural language invoice generation.

## Features

- **Multiple Interfaces**:
  - GUI interface for user-friendly invoice creation
  - Command-line interface for quick invoice generation
  - AI-powered agent for natural language invoice creation

- **Core Functionality**:
  - Generate professional PDF invoices
  - Add multiple services with descriptions and prices
  - Preview invoices before generation
  - Automatic email sending to clients
  - Customizable invoice details and formatting

## Installation

1. Ensure you have Python 3.13+ installed
2. Clone this repository
3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables in a `.env` file:
```
USERNAMEEMAIL=your-email@gmail.com
PASSWORD=your-app-specific-password
OPENAI_API_KEY=your-openai-api-key  # Only needed for AI agent
```

## Usage

### GUI Interface
Run the graphical interface:
```bash
python gui.py
```

### Command Line Interface
Run the CLI version:
```bash
python main.py
```

### AI Agent
Use the AI-powered agent for natural language invoice generation:
```bash
python agent_ai.py
```

Example prompt:
```
Generate an invoice for John Doe. 
Client email: client@example.com 
Services: Design: 100, Development: 200, Testing: 50.
```

## Project Structure

- `gui.py`: Graphical user interface implementation
- `main.py`: Command-line interface implementation
- `agent_ai.py`: AI-powered invoice generation agent
- `createpdf.py`: PDF generation functionality
- `sendMail.py`: Email sending functionality

## Dependencies

- fpdf2: PDF generation
- tkinter: GUI implementation
- openai: AI agent functionality
- python-dotenv: Environment variable management
- smtplib/ssl: Email functionality

## Security Notes

- Never commit your `.env` file or expose sensitive credentials
- Use app-specific passwords for Gmail
- Store API keys securely

## License

[Your License Here]

## Contributing

[Your Contributing Guidelines Here]

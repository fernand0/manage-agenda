# manage-agenda

[![Changelog](https://img.shields.io/github/v/release/fernand0/manage-agenda?include_prereleases&label=changelog)](https://github.com/fernand0/manage-agenda/releases)
[![Tests](https://github.com/fernand0/manage-agenda/actions/workflows/test.yml/badge.svg)](https://github.com/fernand0/manage-agenda/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/fernand0/manage-agenda/blob/master/LICENSE)

A tool for adding entries to your Google Calendar from email messages and web pages using Large Language Models (LLMs) to extract event information.

## Features

- **Email Integration**: Automatically extract event information from Gmail messages
- **Web Page Processing**: Extract events from URLs/web pages, including structured data (JSON-LD, script tags)
- **Multi-Event Extraction**: Extract multiple events from a single source (email or web page)
- **Note-Taker Integration**: Batch-process URLs from `~/notes` via [note-taker](https://github.com/fernand0/another-note-taking-app) integration
- **Multi-LLM Support**: Works with Gemini, Mistral, and Ollama (local models)
- **LLM Model Evaluation**: Compare multiple Ollama models side-by-side with the `llm evaluate` command
- **Smart Date Recognition**: Advanced date parsing for complex scheduling scenarios
- **Interactive Fallback**: When LLM extraction fails, retry, provide a text snippet, or skip
- **Memory Error Handling**: Automatic fallback when LLM models require more memory
- **AI Model Metadata**: Calendar events include metadata about which AI model processed them
- **Google Calendar Sync**: Seamlessly add events to your Google Calendar
- **Flexible Configuration**: Support for multiple email and calendar accounts
- **Calendar Management**: Clean, copy, move, delete, and update calendar events
- **Enhanced Event Selection**: Select events by number or by entering text to match event titles
- **Cache Bypass Option**: Force refresh web content to bypass cache with `--force-refresh` flag
- **Retry Option**: Retry LLM processing during date confirmation with 'r' option
- **Meaningful Identifiers**: Use meaningful IDs for filenames when available instead of numeric identifiers
- **Error Page Detection**: Automatically skips error pages and empty content from URLs
- **Auth Helper**: The `auth` command guides you through Google API credential setup

## Installation

### Prerequisites
- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- API keys for LLM providers (optional, for cloud models)

### Quick Setup
```bash
git clone git@github.com:fernand0/manage-agenda.git
cd manage-agenda
uv sync  # or pip install -e .
```

### Configuration
1. Install [socialModules](https://github.com/fernand0/socialModules) for email/calendar integration
2. Configure your email and calendar accounts using socialModules
3. Set up API keys for LLM providers (if using cloud models)
4. Optionally install [note-taker](https://github.com/fernand0/another-note-taking-app) for batch URL processing from notes

## Usage

### Basic Usage
The easiest way to run the tool is using `uv`:

```bash
# Show help
uv run manage-agenda --help

# Add events (interactive mode - choose email or web source)
uv run manage-agenda add -i

# Add events from email (non-interactive, uses default LLM)
uv run manage-agenda add

# Add events with a specific LLM
uv run manage-agenda add -s mistral

# Add events with force refresh (bypass cache)
uv run manage-agenda add -i -f

# Copy events between calendars
uv run manage-agenda copy

# Clean calendar entries (select between copy or delete)
uv run manage-agenda clean

# Update event status from busy to available
uv run manage-agenda update-status

# Evaluate Ollama models
uv run manage-agenda llm evaluate

# Check/setup Google API authentication
uv run manage-agenda auth -i
```

### Interactive Event Processing
When running in interactive mode (`-i`):

1. Select an AI model (Local/mistral/gemini) (l/m/g)
2. Choose a specific model from the available options
3. Select a source: email account or web
4. For web sources:
   - Enter URLs directly, or
   - Press Enter to automatically extract URLs from `~/notes` (requires note-taker)
5. The tool extracts content and sends it to the selected AI for event parsing
6. If multiple events are found, each is processed individually
7. Select a Google Calendar account
8. Review and confirm event details
9. When confirming dates, you can choose:
   - `s`: Dates are correct (yes)
   - `n`: Manually enter new dates
   - `r`: Retry - ask the LLM again with the same prompt
   - `Y`: Modify year, `M`: month, `D`: day, `h`: hour, `m`: minute
10. Optionally remove the tag from processed emails / delete processed notes

### Interactive Fallback
When LLM extraction fails, in interactive mode you get options:
- `r`: Retry with the same content
- `p`: Provide a relevant text snippet for the LLM to focus on
- `s`: Skip the item

## Commands

### `add` - Add Events
Add entries to your calendar from email or web sources. In interactive mode, presents a unified source selection menu (email accounts and web).

#### Options
- `-i, --interactive`: Running in interactive mode
- `-s, --source`: Select LLM (default: gemini)
- `-f, --force-refresh`: Force refresh web content to bypass cache

### `llm` - LLM Operations
Group command for LLM-related operations.

#### `llm evaluate`
Evaluate multiple Ollama models by running the same prompt through each and comparing responses and timing. Optionally accepts a prompt argument; if not provided, allows selecting an email to use as prompt.

### `auth` - Authentication Setup
Check Google API authentication status and display setup instructions if credentials are missing. Shows step-by-step guidance for enabling the Gmail/Calendar API and creating OAuth credentials.

#### Options
- `-i, --interactive`: Running in interactive mode

### `clean` - Clean Calendar Entries
Combined command that allows users to select between copy or delete operations in a single workflow. This command provides an interactive menu to choose between copying events to another calendar or deleting them, with filtering capabilities.

**Event Selection:**
- Enter comma-separated numbers to select specific events (e.g., `0,2,4`)
- Enter `all` to select all events
- Enter text to match events containing that text (e.g., `meeting` to select all events with "meeting" in the title)

### `copy` - Copy Events
Copy events from one calendar to another with filtering capabilities.

**Event Selection:**
- Enter comma-separated numbers to select specific events (e.g., `0,2,4`)
- Enter `all` to select all events
- Enter text to match events containing that text (e.g., `meeting` to select all events with "meeting" in the title)

### `delete` - Delete Events
Delete events from a calendar with text-based filtering.

**Event Selection:**
- Enter comma-separated numbers to select specific events (e.g., `0,2,4`)
- Enter `all` to select all events
- Enter text to match events containing that text (e.g., `meeting` to select all events with "meeting" in the title)

### `move` - Move Events
Move events between calendars (equivalent to copy + delete).

**Event Selection:**
- Enter comma-separated numbers to select specific events (e.g., `0,2,4`)
- Enter `all` to select all events
- Enter text to match events containing that text (e.g., `meeting` to select all events with "meeting" in the title)

### `update-status` - Update Event Status
Change event status from busy to available (free) for selected events. This command allows users to update the transparency of calendar events from "opaque" (busy) to "transparent" (available), making them appear as free time on your calendar.

**Event Selection:**
- Enter comma-separated numbers to select specific events (e.g., `0,2,4`)
- Enter `all` to select all events
- Enter text to match events containing that text (e.g., `meeting` to select all events with "meeting" in the title)

### `gcalendar` - List Calendar Events
Display events from your Google Calendar.

### `gmail` - List Emails
Display emails from your Gmail account.

## Supported LLM Providers

The tool supports multiple LLM providers:

- **Google Gemini**: Via Gemini API Python SDK
- **Mistral**: Via Mistral Python Client
- **Ollama**: Local models with automatic memory error handling

Each provider requires specific configuration and API keys (for cloud services).

## Key Improvements

### Multi-Event Extraction
- A single email or web page can contain multiple events
- The LLM extracts all events and each is processed and added to the calendar individually
- Supports both list and tuple formats from LLM responses

### Structured Data Extraction
- Extracts event data from JSON-LD (`<script type="application/ld+json">`) tags in web pages
- Also processes other structured data objects embedded in script tags
- Falls back to full-text extraction when structured data is not available

### Note-Taker Integration
- Batch-process URLs stored in `~/notes` using the [note-taker](https://github.com/fernand0/another-note-taking-app) app
- Automatically extracts links from notes when no URLs are provided
- Deletes processed notes after successful calendar event creation

### Smart Date Extraction
- Prioritizes main event dates over background/historical dates
- Handles complex date formats in multiple languages
- Distinguishes between relative dates and explicit dates
- Includes time information when specified (e.g., '19:00h')
- Uses ISO dateTime format for consistent parsing

### AI Model Metadata
- Calendar events include metadata about which AI model was used for extraction
- Tracks processing time for each event

### Memory Error Handling
- Detects when Ollama models require more memory than available
- Prompts for alternative models or automatically switches to lighter models
- Prevents infinite retry loops with memory-constrained models

### External Prompt Management
- Stores prompts in external files for easy modification
- Allows prompt customization without code changes
- Maintains prompt versioning alongside code

### Cache Management
- **Force Refresh Option**: The `--force-refresh` flag bypasses cache comparison and returns full content for reprocessing
- **Improved Web Processing**: Allows reprocessing of web pages for better AI results when cached content would return zero content

### Interactive Features
- **Retry Option**: Users can retry LLM processing during date confirmation with the 'r' option
- **Interactive Fallback**: When extraction fails, users can retry, provide a snippet, or skip
- **Enhanced User Experience**: More flexible options during interactive date confirmation

### Calendar Management Utilities
- **Combined Operations**: The `clean` command provides both copy and delete functionality in a single workflow
- **Status Updates**: The `update-status` command allows changing event visibility from busy to available
- **Interactive Filtering**: Both new commands support text-based filtering and selective processing
- **Enhanced Selection**: All calendar management commands now support selecting events by number or by entering text to match event titles

### File Management
- **Meaningful Identifiers**: Uses meaningful IDs for filenames when available instead of numeric identifiers
- **Better Organization**: More descriptive filenames for cached content and processed events
- **Error Page Detection**: Automatically detects and skips error pages and empty content from URLs

## Dependencies

- [socialModules](https://github.com/fernand0/socialModules): Email and calendar integration
- [note-taker](https://github.com/fernand0/another-note-taking-app): Note management for batch URL processing
- [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/bs4/doc/): HTML parsing
- [Google Generative AI SDK](https://ai.google.dev/gemini-api/docs/quickstart?lang=python): Gemini integration
- [Mistral Python Client](https://github.com/mistralai/client-python): Mistral integration
- [Ollama Python Client](https://github.com/ollama/ollama): Local model integration

## Development

### Setting Up for Development
```bash
# Clone the repository
git clone git@github.com:fernand0/manage-agenda.git
cd manage-agenda

# Create virtual environment and install dependencies
uv sync --extra dev
# Or with pip:
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e '.[dev]'
```

### Running Tests
```bash
python -m pytest
```

### Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

Tests cover core functionalities comprehensively and include both unit and integration tests.

## License

Apache 2.0 - See [LICENSE](LICENSE) file for details.
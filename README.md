# manage-agenda

[![Changelog](https://img.shields.io/github/v/release/fernand0/manage-agenda?include_prereleases&label=changelog)](https://github.com/fernand0/manage-agenda/releases)
[![Tests](https://github.com/fernand0/manage-agenda/actions/workflows/test.yml/badge.svg)](https://github.com/fernand0/manage-agenda/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/fernand0/manage-agenda/blob/master/LICENSE)

A tool for adding entries to your Google Calendar from email messages and web pages using Large Language Models (LLMs) to extract event information.

## Features

- **Automatically extract event information from:**
  - **Gmail** messages
  - **IMAP** email accounts
  - **Web pages** and URLs, including structured data (JSON-LD, script tags). Supports batch-processing URLs from `~/notes` via [note-taker](https://github.com/fernand0/another-note-taking-app) integration
  - **Text files** stored locally
- **Multi-Event Extraction**: Extract multiple events from a single source
- **LLM-powered event extraction:**
  - Supports **Ollama** (local models), **Gemini**, and **Mistral**
  - **Model evaluation**: Compare multiple Ollama models side-by-side with the `llm evaluate` command
  - **Interactive fallback**: When extraction fails, retry, provide a text snippet, or skip
  - **Retry option**: Retry LLM processing during date confirmation with 'r' option
  - **Memory error handling**: Automatic fallback when models require more memory
  - **AI model metadata**: Calendar events include metadata about which model processed them
- **Smart Date Recognition**: Advanced date parsing for complex scheduling scenarios
- **Flexible Output**: Add events directly to Google Calendar or save as JSON files
- **Google Calendar Sync**: Seamlessly add events to your Google Calendar
- **Flexible Configuration**: Support for multiple email and calendar accounts
- **Calendar Management**: Clean, copy, move, delete, and update calendar events
- **Enhanced Event Selection**: Select events by number or by entering text to match event titles
- **Cache Bypass Option**: Force refresh web content to bypass cache with `--force-refresh` flag
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

### Install Browser (for web page processing)
```bash
# Install the default browser engine (Firefox) for Playwright
uv run manage-agenda install

# Or install a different browser
uv run manage-agenda install -b chromium
```

### Configuration
1. Install [socialModules](https://github.com/fernand0/socialModules) for email/calendar integration
2. Configure your email and calendar accounts using socialModules
3. Set up API keys for LLM providers (if using cloud models)
4. Copy `.env.example` to `.env` and fill in your values (see [Environment Variables](#environment-variables))
5. Optionally install [note-taker](https://github.com/fernand0/another-note-taking-app) for batch URL processing from notes

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
uv run manage-agenda add -a gemini
uv run manage-agenda add -a mistral

# Add events from a specific source
uv run manage-agenda add -s web
uv run manage-agenda add -s imap
uv run manage-agenda add -s text

# Add events with force refresh (bypass cache)
uv run manage-agenda add -i -f

# Save events to JSON files instead of adding to calendar
uv run manage-agenda add -o file

# Add events to a specific calendar
uv run manage-agenda add -d "My Calendar"

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

# Install Playwright browser
uv run manage-agenda install
```

### Interactive Event Processing
When running in interactive mode (`-i`):

1. Select an AI model (Local/mistral/gemini) (l/m/g)
2. Choose a specific model from the available options
3. Select a source: email account, web, or text files
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
Add entries to your calendar from email, web, or text file sources. In interactive mode, presents a unified source selection menu (email accounts, web, and text files).

#### Options
- `-i, --interactive`: Running in interactive mode
- `-a, --ai`: Select LLM provider (default: `ollama`). Options: `ollama`, `gemini`, `mistral`
- `-s, --source`: Select data source (default: `gmail`). Options: `gmail`, `imap`, `web`, `text`
- `-f, --force-refresh`: Force refresh web content to bypass cache
- `-d, --destination`: Select destination calendar by name
- `-o, --output`: Output destination (default: `calendar`). Options: `calendar`, `file`, `files`

### `llm` - LLM Operations
Group command for LLM-related operations.

#### `llm evaluate`
Evaluate multiple Ollama models by running the same prompt through each and comparing responses and timing. Optionally accepts a prompt argument; if not provided, allows selecting an email to use as prompt.

##### Options
- `-t, --type`: Evaluation input type (default: `txt`). Options: `email`, `web`, `txt`
- `-o, --output`: Output destination (default: `file`). Options: `calendar`, `file`, `files`
- `PROMPT` (optional argument): Text prompt to evaluate directly

### `auth` - Authentication Setup
Check Google API authentication status and display setup instructions if credentials are missing. Shows step-by-step guidance for enabling the Gmail/Calendar API and creating OAuth credentials.

#### Options
- `-i, --interactive`: Running in interactive mode

### `install` - Install Browser
Install the Playwright browser engine needed for web page processing.

#### Options
- `-b, --browser`: Which browser to install (default: `firefox`). Options: `chromium`, `firefox`, `webkit`, `chrome`, `chrome-beta`

### `clean` - Clean Calendar Entries
Combined command that allows users to select between copy or delete operations in a single workflow. This command provides an interactive menu to choose between copying events to another calendar or deleting them, with filtering capabilities.

#### Options
- `-i, --interactive`: Running in interactive mode
- `-s, --source`: Select source calendar
- `-d, --destination`: Select destination calendar
- `-t, --text`: Filter events by title text

**Event Selection:**
- Enter comma-separated numbers to select specific events (e.g., `0,2,4`)
- Enter `all` to select all events
- Enter text to match events containing that text (e.g., `meeting` to select all events with "meeting" in the title)

### `copy` - Copy Events
Copy events from one calendar to another with filtering capabilities.

#### Options
- `-i, --interactive`: Running in interactive mode
- `-s, --source`: Select source calendar
- `-d, --destination`: Select destination calendar
- `-t, --text`: Filter events by title text

**Event Selection:**
- Enter comma-separated numbers to select specific events (e.g., `0,2,4`)
- Enter `all` to select all events
- Enter text to match events containing that text (e.g., `meeting` to select all events with "meeting" in the title)

### `delete` - Delete Events
Delete events from a calendar with text-based filtering.

#### Options
- `-i, --interactive`: Running in interactive mode
- `-s, --source`: Select source calendar
- `-t, --text`: Filter events by title text

**Event Selection:**
- Enter comma-separated numbers to select specific events (e.g., `0,2,4`)
- Enter `all` to select all events
- Enter text to match events containing that text (e.g., `meeting` to select all events with "meeting" in the title)

### `move` - Move Events
Move events between calendars (equivalent to copy + delete).

#### Options
- `-i, --interactive`: Running in interactive mode
- `-s, --source`: Select source calendar
- `-d, --destination`: Select destination calendar
- `-t, --text`: Filter events by title text

**Event Selection:**
- Enter comma-separated numbers to select specific events (e.g., `0,2,4`)
- Enter `all` to select all events
- Enter text to match events containing that text (e.g., `meeting` to select all events with "meeting" in the title)

### `update-status` - Update Event Status
Change event status from busy to available (free) for selected events. This command allows users to update the transparency of calendar events from "opaque" (busy) to "transparent" (available), making them appear as free time on your calendar.

#### Options
- `-i, --interactive`: Running in interactive mode
- `-s, --source`: Select source calendar
- `-t, --text`: Filter events by title text

**Event Selection:**
- Enter comma-separated numbers to select specific events (e.g., `0,2,4`)
- Enter `all` to select all events
- Enter text to match events containing that text (e.g., `meeting` to select all events with "meeting" in the title)

### `gcalendar` - List Calendar Events
Display events from your Google Calendar.

#### Options
- `-i, --interactive`: Running in interactive mode

### `gmail` - List Emails
Display emails from your Gmail account.

#### Options
- `-i, --interactive`: Running in interactive mode

## Supported LLM Providers

The tool supports multiple LLM providers:

- **Ollama** (default): Local models with automatic memory error handling
- **Google Gemini**: Via Gemini API Python SDK
- **Mistral**: Via Mistral Python Client

Each provider requires specific configuration and API keys (for cloud services).

## Environment Variables

Configuration can be set via environment variables or a `.env` file. See [`.env.example`](.env.example) for a template.

| Variable | Description | Default |
|---|---|---|
| `GEMINI_API_KEY` | API key for Google Gemini | — |
| `MISTRAL_API_KEY` | API key for Mistral AI | — |
| `OLLAMA_HOST` | Ollama server URL | `http://localhost:11434` |
| `OLLAMA_DEFAULT_MODEL` | Default Ollama model | `llama2` |
| `DEFAULT_TIMEZONE` | IANA timezone for events | `Europe/Berlin` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `LOG_FILE` | Path to log file | `manage_agenda.log` |
| `DEFAULT_EMAIL_TAG` | Gmail label/tag for event emails | `zAgenda` |

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
- [Playwright](https://playwright.dev/python/): Browser automation for web page processing
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
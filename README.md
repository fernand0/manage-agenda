# manage-agenda

[![Changelog](https://img.shields.io/github/v/release/fernand0/manage-agenda?include_prereleases&label=changelog)](https://github.com/fernand0/manage-agenda/releases)
[![Tests](https://github.com/fernand0/manage-agenda/actions/workflows/test.yml/badge.svg)](https://github.com/fernand0/manage-agenda/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/fernand0/manage-agenda/blob/master/LICENSE)

A tool for adding entries to your Google Calendar from email messages and web pages using Large Language Models (LLMs) to extract event information.

## Features

- **Email Integration**: Automatically extract event information from Gmail messages
- **Web Page Processing**: Extract events from URLs/web pages
- **Multi-LLM Support**: Works with Gemini, Mistral, and Ollama (local models)
- **Smart Date Recognition**: Advanced date parsing for complex scheduling scenarios
- **Memory Error Handling**: Automatic fallback when LLM models require more memory
- **Google Calendar Sync**: Seamlessly add events to your Google Calendar
- **Flexible Configuration**: Support for multiple email and calendar accounts
- **Calendar Management**: Clean and update calendar events with new utility commands
- **Cache Bypass Option**: Force refresh web content to bypass cache with `--force-refresh` flag
- **Retry Option**: Retry LLM processing during date confirmation with 'r' option
- **Meaningful Identifiers**: Use meaningful IDs for filenames when available instead of numeric identifiers
- **Version 0.2**: Includes new 'clean' and 'update-status' commands for enhanced calendar management

## Installation

### Prerequisites
- Python 3.8+
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

## Usage

### Basic Usage
The easiest way to run the tool is using `uv`:

```bash
# Show help
uv run manage-agenda --help

# Add events from email (interactive mode)
uv run manage-agenda add -i True

# Add events from a web page
uv run manage-agenda add web -u https://example.com/event

# Copy events between calendars
uv run manage-agenda copy

# Clean calendar entries (select between copy or delete)
uv run manage-agenda clean

# Update event status from busy to available
uv run manage-agenda update-status
```

### Interactive Email Processing
When running in interactive mode (`-i True`):

1. Select an AI model (Local/mistral/gemini) (l/m/g)
2. Choose a specific model from the available options
3. Select an email account to process
4. The tool reads messages tagged with `zAgenda` (configurable)
5. Extracts content and sends to selected AI for event parsing
6. Select a Google Calendar account
7. Review and confirm event details
8. When confirming dates, you can now choose:
   - `y`: Dates are correct
   - `n`: Manually enter new dates
   - `r`: Retry - ask the LLM again with the same prompt
9. Optionally remove the tag from processed emails

### Web Page Processing
The `add web` command allows you to add events from URLs:
```bash
uv run manage-agenda add web -u https://example.com/event-page
```

To bypass the cache and reprocess web content for better AI results, use the `--force-refresh` flag:
```bash
uv run manage-agenda add --force-refresh
```
This forces the system to fetch fresh content instead of returning only new/different content compared to the cached version.

## Commands

### `add` - Add Events
Group command for adding entries to your calendar.

#### Options
- `-i, --interactive`: Running in interactive mode
- `-s, --source`: Select LLM (default: gemini)
- `-f, --force-refresh`: Force refresh web content to bypass cache

#### `add mail`
Add events from email messages. Reads messages tagged with `zAgenda` and extracts event information using LLMs. When available, uses meaningful identifiers for filenames instead of numeric identifiers for better organization.

#### `add web`
Add events from web pages. Fetches content from a URL, processes HTML to extract text, and uses LLMs to extract event details. Includes `--force-refresh` option to bypass cache and reprocess content for better AI results.

### `clean` - Clean Calendar Entries
Combined command that allows users to select between copy or delete operations in a single workflow. This command provides an interactive menu to choose between copying events to another calendar or deleting them, with filtering capabilities.

### `copy` - Copy Events
Copy events from one calendar to another with filtering capabilities.

### `delete` - Delete Events
Delete events from a calendar with text-based filtering.

### `move` - Move Events
Move events between calendars (equivalent to copy + delete).

### `update-status` - Update Event Status
Change event status from busy to available (free) for selected events. This command allows users to update the transparency of calendar events from "opaque" (busy) to "transparent" (available), making them appear as free time on your calendar.

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

### Smart Date Extraction
- Prioritizes main event dates over background/historical dates
- Handles complex date formats in multiple languages
- Distinguishes between relative dates and explicit dates
- Includes time information when specified (e.g., '19:00h')

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
- **Retry Option**: Users can now retry LLM processing during date confirmation with the 'r' option
- **Enhanced User Experience**: More flexible options during interactive date confirmation

### Calendar Management Utilities
- **Combined Operations**: The `clean` command provides both copy and delete functionality in a single workflow
- **Status Updates**: The `update-status` command allows changing event visibility from busy to available
- **Interactive Filtering**: Both new commands support text-based filtering and selective processing

### File Management
- **Meaningful Identifiers**: Uses meaningful IDs for filenames when available instead of numeric identifiers
- **Better Organization**: More descriptive filenames for cached content and processed events

## Dependencies

- [socialModules](https://github.com/fernand0/socialModules): Email and calendar integration
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
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e '.[test]'
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
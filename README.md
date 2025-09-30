# manage-agenda

[![PyPI](https://img.shields.io/pypi/v/manage-agenda.svg)](https://pypi.org/project/manage-agenda/)
[![Changelog](https://img.shields.io/github/v/release/fernand0/manage-agenda?include_prereleases&label=changelog)](https://github.com/fernand0/manage-agenda/releases)
[![Tests](https://github.com/fernand0/manage-agenda/actions/workflows/test.yml/badge.svg)](https://github.com/fernand0/manage-agenda/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/fernand0/manage-agenda/blob/master/LICENSE)

A tool for adding entries on my Google Calendar from email messages

## Steps of an execution.

When running (in ineractive mode, `-i True`) with:

```bash
uv run manage-agenda add -i True 
```

1. Asks for the selection of some AI

    ```
    Local/mistral/gemini model )(l/m/g)? 
    ```
    
    Let us choose, for instance, (g)emini.

2. Asks to choose one of the available models.

    ![image](https://github.com/user-attachments/assets/bd49fb8d-885e-4e70-8239-d4b72e62bb22)
    
    ...
    
    ![image](https://github.com/user-attachments/assets/e55beb11-6383-4c06-8314-2180aaa68045)
    
    It has a default selection. Let us suppose that we push [Enter].

4. Then we can select one of the configured email accounts.

    ```
    Rules:
    0) ('gmail', 'set', 'fernand0@elmundoesimperfecto', 'posts')
    1) ('gmail', 'set', 'fernand0@elmundoesimperfecto.com', 'drafts')
    1) ('gmail', 'set', 'otherOne@elmundoesimperfecto.com', 'posts')
    ```
    
    We can select the first one, for example.

5. It will read the messages tagged with `zAgenda` (it can be selected)
6. Extracts the content of each message and sends an adequate prompt to the selected AI. 
It will return a `json` formatted event suitable for Google calendar.
7. Asks to choose a Google calendar account.

    ```
    Rules:
    0) ('gcalendar', 'set', 'fernand0@elmundoesimperfecto.com', 'posts')
    1) ('gcalendar', 'set', 'otherOne@elmundoesimperfecto.com', 'posts')
    ```
    
    Let us suppose that we choose the first one.

8. It will show the subject of the message and it will ask to choose the calendar to enter the event.

    ```
    Subject: (some subject)
    
    0) Work
    1) Leissure 
    2) Meetings
    ...
    6) Others
    Selection 
    ```

9. It will ask if we want to delete the tag.

    ```
    Delete tag? (Press Enter to continue)
    ```

It will repeat the last four steps for each message with the tag.

## Dependencies

It relies on:

- Module [socialModules](https://github.com/fernand0/socialModules) for reading in your gmail account and writing in your google calendar (needs configuration).

- [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/bs4/doc/) for parsing HTML content.

At this moment it can use several AI modules:

- [Gemini](https://gemini.google.com/) via [Gemini API Python SDK](https://ai.google.dev/gemini-api/docs/quickstart?lang=python)
- [Mistral](https://mistral.ai/) via [Mistral Python Client](https://github.com/mistralai/client-python)
- Locally installed AIs with [Ollama](https://ollama.com/) via [Ollama code](https://github.com/ollama/ollama)

All of them need some configuration (provided in their respective sites)

## Installation

<!---
Install this tool using `pip`:
```bash
pip install manage-agenda
```
--->

```bash
git clone git@github.com:fernand0/manage-agenda.git
```

It can not be installed via pip (does it make sense in such a raw state?).

This is my first attempt at using `click` (using 
[click-app cookiecutter template](https://github.com/simonw/click-app)
some parts will not work.

## Usage

The easiest way to run it is to use `uv`.

For example, for help, run:

```bash
uv run manage-agenda --help
```

<---
For help, run:
```bash
manage-agenda --help
```
You can also use:
```bash
python -m manage_agenda --help
```
--->

## Commands

### `add`

This command is now a group for adding entries to your calendar. By default, it behaves like `add mail`.

#### `add mail`

This subcommand allows you to add entries to your calendar from email messages.

#### `add web`

This subcommand allows you to add entries to your calendar from a web page. It fetches the content of the provided URL, processes the HTML to extract only the textual information, and then uses an LLM to extract event details.

### `copy`

This command allows you to copy events from one calendar to another. You can filter the events by text and select which ones to copy.

### `delete`

This command allows you to delete events from a calendar. You can filter the events by text and select which ones to delete.

### `move`

This command allows you to move events from one calendar to another. This is equivalent to copying the events and then deleting them from the source calendar.


## Development

Tests check nothing but the correct structure of the project (using the template).

To contribute to this tool, first checkout the code. Then create a new virtual environment:
```bash
cd manage-agenda
python -m venv venv
source venv/bin/activate
```
Now install the dependencies and test dependencies:
```bash
pip install -e '.[test]'
```
To run the tests:
```bash
python -m pytest
```

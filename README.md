# manage-agenda

This program does the following steps: 

1. Asks for the selection of some AI

When running with:

```bash
uv run manage-agenda add -i True 2>&1 | tee /tmp/log.txt
```
It shows:

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
6. Asks to choose a Google calendar account.
7. Extracts the content of each message and sends an adequate prompt to the selected AI. 
It will return a `json` formatted event suitable for Google calendar.
8. It will show the subject of the message and it will ask to choose the calendar to enter the event.
9. It will ask if we want to delete the tag.

[![PyPI](https://img.shields.io/pypi/v/manage-agenda.svg)](https://pypi.org/project/manage-agenda/)
[![Changelog](https://img.shields.io/github/v/release/fernand0/manage-agenda?include_prereleases&label=changelog)](https://github.com/fernand0/manage-agenda/releases)
[![Tests](https://github.com/fernand0/manage-agenda/actions/workflows/test.yml/badge.svg)](https://github.com/fernand0/manage-agenda/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/fernand0/manage-agenda/blob/master/LICENSE)

A tool for adding entries on my Google Calendar from email messages

It relies on:

- Module [socialModules](https://github.com/fernand0/socialModules) for reading in your gmail account and writing in your google calendar (needs configuration).

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

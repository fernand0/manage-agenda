# manage-agenda

Tests are not working.

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

It can not be installed via pip (does it make sense in such a raw state?)

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

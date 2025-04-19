# manage-agenda

[![PyPI](https://img.shields.io/pypi/v/manage-agenda.svg)](https://pypi.org/project/manage-agenda/)
[![Changelog](https://img.shields.io/github/v/release/fernand0/manage-agenda?include_prereleases&label=changelog)](https://github.com/fernand0/manage-agenda/releases)
[![Tests](https://github.com/fernand0/manage-agenda/actions/workflows/test.yml/badge.svg)](https://github.com/fernand0/manage-agenda/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/fernand0/manage-agenda/blob/master/LICENSE)

A tool for adding entries on my Google Calendar from email messages

## Installation

Install this tool using `pip`:
```bash
pip install manage-agenda
```
## Usage

For help, run:
```bash
manage-agenda --help
```
You can also use:
```bash
python -m manage_agenda --help
```
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

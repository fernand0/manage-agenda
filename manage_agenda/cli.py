import click
import os

# Import auxiliary functions and classes from utils.py
from utils import setup_logging, select_llm, process_email_cli, Args  # Import only what's needed


@click.group()
@click.version_option()
def cli():
    "An app for adding entries to my calendar"


@cli.command()
@click.option(
    "-i",
    "--interactive",
    default=False,
    help="Running in interactive mode",
)
@click.option(
    "-d",
    "--delete",
    default=True,
    help="Delete tag",
)
@click.option(
    "-s",
    "--source",
    default="gemini",
    help="Select LLM",
)
def add(interactive, delete, source):
    "Add entries to the calendar"
    setup_logging()

    args = Args(interactive=interactive, delete=delete, source=source)

    model = select_llm(args)

    print(f"Model: {model}")

    process_email_cli(args, model)


if __name__ == "__main__":
    cli()

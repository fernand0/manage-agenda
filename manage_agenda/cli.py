import click
import os

# Import auxiliary functions and classes from utils.py
from .utils import (
    select_llm,
    Args,
    authorize,
    process_email_cli,
    select_account,
    list_emails_folder,
    list_events_folder,
)  # Import only what's needed

from .utils_base import (
    setup_logging,
    )

@click.group()
@click.version_option()
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Enable verbose output.",
)
@click.pass_context
def cli(ctx, verbose):
    """An app for adding entries to my calendar"""
    ctx.ensure_object(dict)
    ctx.obj['VERBOSE'] = verbose
    setup_logging(verbose)


@cli.command()
@click.option(
    "-i",
    "--interactive",
    is_flag=True,
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
@click.pass_context
def add(ctx, interactive, delete, source):
    """Add entries to the calendar"""
    verbose = ctx.obj['VERBOSE']
    args = Args(interactive=interactive, delete=delete, source=source, verbose=verbose)

    model = select_llm(args)

    if verbose:
        print(f"Model: {model}")

    process_email_cli(args, model)

@cli.command()
@click.option(
    "-i",
    "--interactive",
    is_flag=True,
    default=False,
    help="Running in interactive mode",
)
@click.pass_context
def auth(ctx, interactive):
    """Auth related operations"""
    verbose = ctx.obj['VERBOSE']
    args = Args(interactive=interactive, delete=None, source=None, verbose=verbose)
    if verbose:
        print(f"Args: {args}")
    #api_src = select_account(args, api_src_type="g")
    api_src = authorize(args)
    if not api_src.getClient():
        msg = ('1. Enable the Gcalendar API:\n'  # Corrected newline escape
          '   Go to the Google Cloud Console. https://console.cloud.google.com/
'  # Corrected newline escape
          "   If you don't have a project, create one.

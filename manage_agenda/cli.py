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
    copy_events_cli,
    delete_events_cli,
    move_events_cli,
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
    "-s",
    "--source",
    default="gemini",
    help="Select LLM",
)
@click.pass_context
def add(ctx, interactive, source):
    """Add entries to the calendar"""
    verbose = ctx.obj['VERBOSE']
    args = Args(
        interactive=interactive,
        delete=None,
        source=source,
        verbose=verbose,
        destination=None,
        text=None,
    )

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
    args = Args(interactive=interactive, delete=None, source=None, verbose=verbose, destination=None, text=None)
    if verbose:
        print(f"Args: {args}")
    #api_src = select_account(args, api_src_type="g")
    api_src = authorize(args)
    if not api_src.getClient():
        msg = ('1. Enable the Gcalendar API:\n'
          '   Go to the Google Cloud Console. https://console.cloud.google.com/\n'
          "   If you don't have a project, create one.\n"
          '   Search for "Gmail API" in the API Library.\n'
          '   Enable the Gmail API.\n'
          '2. Create Credentials:\n'
          '   In the Google Cloud Console, go to "APIs & Services" > "Credentials".\n'
          '   Click "Create credentials" and choose "OAuth client ID".\n'
          '   You might be asked to configure the consent screen first. '
          '   If so, click "Configure consent screen", choose "External",'
          '     give your app a name, and save.\n'
          '   Back on the "Create credentials" page, select "Web application" '
          '     as the Application type.\n'
          '   Give your OAuth 2.0 client a name.\n'
          '   Add http://localhost:8080 to "Authorized JavaScript origins".\n'
          '   Add http://localhost:8080/oauth2callback to "Authorized redirect URIs".\n'
          '   Click "Create".\n'
          '   Download the resulting JSON file (this is your credentials.json file).\n'
          f'  and rename (or make a link) to: {api_src.confName((api_src.getServer(), api_src.getNick()))}')
        print(msg)
    else:
        print(f"This account has been correctly authorized")
        api_src.info()

@cli.command()
@click.option(
    "-i",
    "--interactive",
    is_flag=True,
    default=False,
    help="Running in interactive mode",
)
@click.pass_context
def gcalendar(ctx, interactive):
    """List events from Google Calendar"""
    verbose = ctx.obj['VERBOSE']
    args = Args(interactive=interactive, delete=None, source=None, verbose=verbose, destination=None, text=None)
    api_src = select_account(args, api_src_type="gcalendar")
    list_events_folder(args, api_src)

@cli.command()
@click.option(
    "-i",
    "--interactive",
    is_flag=True,
    default=False,
    help="Running in interactive mode",
)
@click.pass_context
def gmail(ctx, interactive):
    """List emails from Gmail"""
    verbose = ctx.obj['VERBOSE']
    args = Args(interactive=interactive, delete=None, source=None, verbose=verbose, destination=None, text=None)
    api_src = select_account(args, api_src_type="gmail")
    list_emails_folder(args, api_src)


@cli.command()
@click.option(
    "-i",
    "--interactive",
    is_flag=True,
    default=False,
    help="Running in interactive mode",
)
@click.option(
    "-s",
    "--source",
    default=None,
    help="Select source calendar",
)
@click.option(
    "-d",
    "--destination",
    default=None,
    help="Select destination calendar",
)
@click.option(
    "-t",
    "--text",
    default=None,
    help="Select text in title",
)
@click.pass_context
def copy(ctx, interactive, source, destination, text):
    """Copy entries from one calendar to another"""
    verbose = ctx.obj['VERBOSE']
    args = Args(
        interactive=interactive,
        delete=None,
        source=source,
        verbose=verbose,
        destination=destination,
        text=text,
    )

    copy_events_cli(args)

@cli.command()
@click.option(
    "-i",
    "--interactive",
    is_flag=True,
    default=False,
    help="Running in interactive mode",
)
@click.option(
    "-s",
    "--source",
    default=None,
    help="Select source calendar",
)
@click.option(
    "-t",
    "--text",
    default=None,
    help="Select text in title",
)
@click.pass_context
def delete(ctx, interactive, source, text):
    """Delete entries from a calendar"""
    verbose = ctx.obj['VERBOSE']
    args = Args(
        interactive=interactive,
        delete=None,
        source=source,
        verbose=verbose,
        destination=None,
        text=text,
    )

    delete_events_cli(args)

@cli.command()
@click.option(
    "-i",
    "--interactive",
    is_flag=True,
    default=False,
    help="Running in interactive mode",
)
@click.option(
    "-s",
    "--source",
    default=None,
    help="Select source calendar",
)
@click.option(
    "-d",
    "--destination",
    default=None,
    help="Select destination calendar",
)
@click.option(
    "-t",
    "--text",
    default=None,
    help="Select text in title",
)
@click.pass_context
def move(ctx, interactive, source, destination, text):
    """Move entries from one calendar to another"""
    verbose = ctx.obj['VERBOSE']
    args = Args(
        interactive=interactive,
        delete=None,
        source=source,
        verbose=verbose,
        destination=destination,
        text=text,
    )

    move_events_cli(args)


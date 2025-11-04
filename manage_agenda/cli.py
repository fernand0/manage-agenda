import click
import os

# Import auxiliary functions and classes from utils.py
from .utils import (
    select_llm,
    Args,
    authorize,
    process_email_cli,
    process_web_cli,
    select_api_source,
    list_emails_folder,
    list_events_folder,
    copy_events_cli,
    delete_events_cli,
    move_events_cli,
    get_add_sources,
)  # Import only what's needed
from socialModules.configMod import select_from_list

from .utils_base import (
    setup_logging,
)

from .utils_llm import (
    evaluate_models,
)
from .utils import select_email_prompt, Args


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
    ctx.obj["VERBOSE"] = verbose
    setup_logging(verbose)


@cli.group()
@click.pass_context
def llm(ctx):
    """LLM related operations"""
    pass


@llm.command()
@click.argument("prompt", required=False)
@click.pass_context
def evaluate(ctx, prompt):
    """Evaluate different LLM models"""
    if not prompt:
        args = Args(
            interactive=True,
            delete=None,
            source=None,
            verbose=ctx.obj["VERBOSE"],
            destination=None,
            text=None,
        )
        prompt = select_email_prompt(args)

    if prompt:
        evaluate_models(prompt)


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
    """Add entries to the calendar."""
    verbose = ctx.obj["VERBOSE"]
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

    if interactive:
        sources = get_add_sources()
        print(f"Sources: {sources}")
        sel, selected_source= select_from_list(sources)

        if selected_source == "web":
            process_web_cli(args, model)
        else:
            process_email_cli(args, model, source_name=selected_source)
    else:
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
    verbose = ctx.obj["VERBOSE"]
    args = Args(
        interactive=interactive,
        delete=None,
        source=None,
        verbose=verbose,
        destination=None,
        text=None,
    )
    if verbose:
        print(f"Args: {args}")
    # api_src = select_account(args, api_src_type="g")
    api_src = authorize(args)
    if not api_src.getClient():
        msg = (
            "1. Enable the Gcalendar API:\n"
            "   Go to the Google Cloud Console. https://console.cloud. google.com/"
            "   If you don't have a project, create one.\n"
            '   Search for "Gmail API" in the API Library. '
            "   Enable the Gmail API. "
            "2. Create Credentials: "
            '   In the Google Cloud Console, go to "APIs & Services" > "Credentials". '
            '   Click "Create credentials" and choose "OAuth client ID".  '
            "   You might be asked to configure the consent screen first. "
            '   If so, click "Configure consent screen", choose "External",'
            "     give your app a name, and save.\n"
            '   Back on the "Create credentials" page, select "Web application" '
            "     as the Application type. "
            "   Give your OAuth 2.0 client a name. "
            '   Add http://localhost:8080 to "Authorized JavaScript origins". '
            '   Add http://localhost:8080/oauth2callback to "Authorized redirect URIs". '
            '   Click "Create". '
            "   Download the resulting JSON file (this is your credentials.json file). "
            f"  and rename (or make a link) to: {api_src.confName((api_src.getServer(), api_src.getNick()))}"
        )
        print(msg)
    else:
        print(f"This account has been correctly authorized")


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
    verbose = ctx.obj["VERBOSE"]
    args = Args(
        interactive=interactive,
        delete=None,
        source=None,
        verbose=verbose,
        destination=None,
        text=None,
    )
    api_src = select_api_source(args, api_src_type="gcalendar")
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
    verbose = ctx.obj["VERBOSE"]
    args = Args(
        interactive=interactive,
        delete=None,
        source=None,
        verbose=verbose,
        destination=None,
        text=None,
    )
    list_emails_folder(args)


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
    verbose = ctx.obj["VERBOSE"]
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
    verbose = ctx.obj["VERBOSE"]
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
    verbose = ctx.obj["VERBOSE"]
    args = Args(
        interactive=interactive,
        delete=None,
        source=source,
        verbose=verbose,
        destination=destination,
        text=text,
    )

    move_events_cli(args)

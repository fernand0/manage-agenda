import os
import sys
from runpy import run_module

import click
from socialModules.configMod import select_from_list

from .utils import (
    Args,
    authorize,
    clean_events_cli,
    copy_events_cli,
    delete_events_cli,
    get_add_sources,
    list_emails_folder,
    list_events_folder,
    move_events_cli,
    process_email_cli,
    process_txt_cli,
    process_web_cli,
    select_api_source,
    select_llm,
    update_event_status_cli,
)
from .utils_base import setup_logging
from .utils_llm import evaluate_models


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
@click.option(
    "-t",
    "--type",
    "type_",
    type=click.Choice(["email", "web", "txt"]),
    default="txt",
    help="Type of evaluation to run (email, web, txt)",
)
@click.option(
    "-o",
    "--output",
    type=click.Choice(["calendar", "file", "files"]),
    default="file",
    help="Output destination: calendar, file, or files",
)
@click.argument("prompt", required=False)
@click.pass_context
def evaluate(ctx, type_, output, prompt):
    """Evaluate different LLM models"""
    if prompt:
        print(prompt)
    if output == "files":
        output = "file"
    args = Args(
        interactive=False,
        delete=None,
        source=None,
        verbose=ctx.obj["VERBOSE"],
        destination=None,
        text=None,
        output=output,
    )

    evaluate_models(args, prompt=prompt, eval_type=type_ if not prompt else None)


@cli.command()
@click.option(
    "-i",
    "--interactive",
    is_flag=True,
    default=False,
    help="Running in interactive mode",
)
@click.option(
    "-a",
    "--ai",
    default="ollama",
    help="Select LLM",
)
@click.option(
    "-f",
    "--force-refresh",
    is_flag=True,
    default=False,
    help="Force refresh web content to bypass cache",
)
@click.option(
    "-s",
    "--source",
    type=click.Choice(["gmail", "imap", "web", "text"]),
    default="gmail",
    help="Source of data: gmail, imap, web, or files",
)
@click.option(
    "-o",
    "--output",
    type=click.Choice(["calendar", "file", "files"]),
    default="calendar",
    help="Output destination: calendar, file, or files",
)
@click.pass_context
def add(ctx, interactive, source, ai, force_refresh, output):
    """Add entries to the calendar."""
    verbose = ctx.obj["VERBOSE"]
    if output == "files":
        output = "file"
    args = Args(
        interactive=interactive,
        delete=None,
        source=source,
        ai=ai,
        verbose=verbose,
        destination=None,
        text=None,
        output=output,
    )

    # Create rules instance once and reuse it
    from .utils import ensure_rules

    rules = ensure_rules()

    model = select_llm(args)

    if verbose:
        click.echo(f"Selected model: {model.model_name}")


    if interactive:
        sources = get_add_sources(rules=rules)
        sel, selected = select_from_list(sources, title="Sources of information")

        if selected is None:
            return

        # if "Web" in selected_source:  # Check if "Web" is in the selected source string
        print(f"\nSelected: {selected}")
        if isinstance(selected, str) and (("Web" in selected) or selected.startswith("http")):
            if selected.startswith("http"):
                process_web_cli(args, model, urls=selected.split(" "), force_refresh=force_refresh)
            else:
                process_web_cli(args, model, force_refresh=force_refresh)
        elif isinstance(selected, str) and (("Text" in selected) or os.path.exists(selected)):
            if "." in selected:
                process_txt_cli(args, model, source_name=selected.split(" "), rules=rules)
            else:
                process_txt_cli(args, model, rules=rules)
        else:
            process_email_cli(args, model, source_name=selected, rules=rules)
    else:
        process_email_cli(args, model, rules=rules)


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
    api_src = authorize(args)
    if not api_src.getClient():
        msg = (
            "1. Enable the Gcalendar API:\n"
            "   Go to the Google Cloud Console. https://console.cloud.google.com/\n"
            "   If you don't have a project, create one.\n"
            '   Search for "Gmail API" in the API Library. \n'
            "   Enable the Gmail API. \n"
            "2. Create Credentials: \n"
            '   In the Google Cloud Console, go to "APIs & Services" > "Credentials". \n'
            '   Click "Create credentials" and choose "OAuth client ID".  \n'
            "   You might be asked to configure the consent screen first. \n"
            '   If so, click "Configure consent screen", choose "External",\n'
            "     give your app a name, and save.\n"
            '   Back on the "Create credentials" page, select "Web application\n" '
            "     as the Application type. \n"
            "   Give your OAuth 2.0 client a name. \n"
            '   Add http://localhost:8080 to "Authorized JavaScript origins". \n'
            '   Add http://localhost:8080/oauth2callback to "Authorized redirect URIs". \n'
            '   Click "Create". \n'
            "   Download the resulting JSON file (this is your credentials.json file). \n"
            f"  and rename (or make a link) to: {api_src.confName((api_src.getServer(), api_src.getNick()))}\n"
        )
        print(msg)
    else:
        print("This account has been correctly authorized")


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
def clean(ctx, interactive, source, destination, text):
    """Clean calendar entries (select between copy or delete)"""
    verbose = ctx.obj["VERBOSE"]
    args = Args(
        interactive=interactive,
        delete=None,
        source=source,
        verbose=verbose,
        destination=destination,
        text=text,
    )

    clean_events_cli(args)


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
def update_status(ctx, interactive, source, text):
    """Update event status from busy to available"""
    verbose = ctx.obj["VERBOSE"]
    args = Args(
        interactive=interactive,
        delete=None,
        source=source,
        verbose=verbose,
        destination=None,
        text=text,
    )

    update_event_status_cli(args)

BROWSERS = ("chromium", "firefox", "webkit", "chrome", "chrome-beta")

@cli.command()
@click.option(
    "--browser",
    "-b",
    default="firefox",
    type=click.Choice(BROWSERS, case_sensitive=False),
    help="Which browser to install",
)
def install(browser):
    """
    Install the Playwright browser needed by this tool.

    Usage:

        manage-agenda install

    Or for browsers other than the Firefox default:

        manage-agenda install -b chromium
    """
    sys.argv = ["playwright", "install", browser]
    run_module("playwright", run_name="__main__")

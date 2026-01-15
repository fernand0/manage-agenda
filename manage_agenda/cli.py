import click

# Import auxiliary functions and classes from utils.py
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
    process_web_cli,
    select_api_source,
    select_email_prompt,
    select_llm,
    update_event_status_cli,
)
from .utils_base import (
    setup_logging,
)
from .utils_llm import (
    evaluate_models,
)

def select_from_list(options, identifier="", selector="", default=""):
    """
    Presents a list of options to the user and returns the selected option.
    """
    for i, option in enumerate(options):
        print(f"{i}) {option}")

    while True:
        try:
            selection = input("Select an option: ")
            if selection.isdigit():
                selection = int(selection)
                if 0 <= selection < len(options):
                    return selection, options[selection]
            elif selection.startswith('http'):
                return len(options)-1, selection
            else:
                for i, option in enumerate(options):
                    if selection.lower() in option.lower():
                        return i, option
        except (ValueError, IndexError):
            pass
        except (KeyboardInterrupt, EOFError):
            print("\nSelection cancelled.")
            return None, None
        print("Invalid selection. Please try again.")


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
@click.option(
    "-f",
    "--force-refresh",
    is_flag=True,
    default=False,
    help="Force refresh web content to bypass cache",
)
@click.pass_context
def add(ctx, interactive, source, force_refresh):
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

    # Create rules instance once and reuse it
    from socialModules import moduleRules
    rules = moduleRules.moduleRules()
    rules.checkRules()

    model = select_llm(args)

    if verbose:
        print(f"Model: {model}")

    if interactive:
        sources = get_add_sources(rules=rules)
        sel, selected = select_from_list(sources)

        #if "Web" in selected_source:  # Check if "Web" is in the selected source string
        print(f"\nSelected: {selected} - {type(selected)}")
        if (isinstance(selected, str)
            and (("Web" in selected)
            or selected.startswith('http'))):
            url = None
            if selected.startswith('http'):
                process_web_cli(args, model, urls = selected.split(' '), force_refresh=force_refresh)
            else:
                process_web_cli(args, model, force_refresh=force_refresh)
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
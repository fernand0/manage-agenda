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
def cli():
    "An app for adding entries to my calendar"
    setup_logging()


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
@click.option(
    "-i",
    "--interactive",
    default=False,
    help="Running in interactive mode",
)
def add(interactive, delete, source):
    "Add entries to the calendar"

    args = Args(interactive=interactive, delete=delete, source=source)

    model = select_llm(args)

    print(f"Model: {model}")

    process_email_cli(args, model)

@cli.command()
@click.option(
    "-i",
    "--interactive",
    default=False,
    help="Running in interactive mode",
)
def auth(interactive):
    "Auth related operations"

    args = Args(interactive=interactive, delete=None, source=None)
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


@cli.command()
@click.option(
    "-i",
    "--interactive",
    default=False,
    help="Running in interactive mode",
)
@click.option('--auth','-a', is_flag=True, help='Authorization flow.')
def gcalendar(interactive, auth):
    "Gcalendar related operations"

    args = Args(interactive=interactive, delete=None, source=None)
    api_src = select_account(args, api_src_type="gcalendar")

    list_events_folder(args, api_src)


@cli.command()
@click.option(
    "-i",
    "--interactive",
    default=False,
    help="Running in interactive mode",
)
@click.option('--auth','-a', is_flag=True, help='Authorization flow.')
def gmail(interactive, auth):
    "Gmail related operations"

    args = Args(interactive=interactive, delete=None, source=None)
    api_src = select_account(args)

    list_emails_folder(args, api_src)

if __name__ == "__main__":
    setup_logging()
    cli()

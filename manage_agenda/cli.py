import click


@click.group()
@click.version_option()
def cli():
    "A tool for adding entries on my Google Calendar from email messages"


@cli.command(name="command")
@click.argument(
    "example"
)
@click.option(
    "-o",
    "--option",
    help="An example option",
)
def first_command(example, option):
    "Command description goes here"
    click.echo("Here is some output")

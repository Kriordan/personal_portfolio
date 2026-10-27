import json
from pathlib import Path

import click
from flask.cli import with_appcontext

from .service import import_metadata, refresh


@click.command("refresh-lottery")
@click.option("--state", type=click.Choice(["all", "ny", "ct"]), default="all", show_default=True)
@click.option("--dry-run", is_flag=True, help="Fetch and validate without writing anything.")
@click.option("--scheduled", is_flag=True, help="Identify a Heroku Scheduler invocation in the status panel.")
@with_appcontext
def refresh_lottery(state, dry_run, scheduled):
    results = refresh(state, dry_run=dry_run, scheduled=scheduled)
    click.echo(json.dumps(results, indent=2))
    if any(r["status"] == "failed" for r in results):
        raise click.ClickException("One or more sources failed; their last valid snapshots were preserved")


@click.command("import-ny-lottery-metadata")
@click.argument("path", required=False, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--dry-run", is_flag=True)
@with_appcontext
def import_ny_metadata(path, dry_run):
    """Validate and upsert NY metadata. Defaults to the bundled verified catalog."""
    path = path or Path(__file__).parent / "data" / "ny_metadata.json"
    try:
        count = import_metadata(json.loads(path.read_text()), dry_run=dry_run)
    except (ValueError, KeyError, TypeError) as exc:
        raise click.ClickException(f"Metadata rejected: {exc}") from exc
    click.echo(f"{'Validated' if dry_run else 'Imported'} {count} NY games. Run refresh-lottery --state ny to publish updated details.")

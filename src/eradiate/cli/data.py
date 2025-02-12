import os.path
import textwrap
from pathlib import Path

import click
from rich.console import Console
from ruamel.yaml import YAML

import eradiate

from ..exceptions import DataError

console = Console(color_system=None)


@click.group()
def data():
    """
    Manage data.
    """
    pass


@data.command()
@click.option(
    "--input-directory",
    "-i",
    default=".",
    help="Path to input directory (default: '.').",
)
@click.option(
    "--output-file",
    "-o",
    default=None,
    help="Path to output file (default: '<input_directory>/registry.txt').",
)
@click.option(
    "--rules",
    "-r",
    default=None,
    help="Path to the registry rule file "
    "(default: '<input_directory>/registry_rules.yml').",
)
@click.option(
    "--hash-algorithm",
    "-a",
    default="sha256",
    help="Hashing algorithm (default: 'sha256').",
)
def make_registry(input_directory, output_file, rules, hash_algorithm):
    """
    Recursively construct a file registry from the current working directory.
    """
    from eradiate.data._core import load_rules, make_registry

    input_directory = Path(input_directory)
    console.print(f"Creating registry file from '{input_directory}'")

    # Load include and exclude rules
    if rules is None:
        rules = input_directory / "registry_rules.yml"
    console.print(f"Using rules in '{rules}'")
    rule_map = load_rules(rules)

    # Write registry
    if output_file is None:
        output_file = input_directory / "registry.txt"
    console.print(f"Writing registry file to '{output_file}'")
    make_registry(
        input_directory,
        output_file,
        includes=rule_map["include"],
        excludes=rule_map["exclude"],
        alg=hash_algorithm,
        show_progress=True,
    )


@data.command()
def update_registries():
    """
    Update local registries for online sources.
    """
    # Update data store registries
    for data_store_id, data_store in eradiate.data.data_store.stores.items():
        if isinstance(data_store, eradiate.data.SafeOnlineDataStore):
            console.print(
                f"[bold cyan]{data_store_id}[/] [{data_store.__class__.__name__}]"
            )
            console.print(f"    Refreshing registry \[{data_store.registry_path}]")
            data_store.registry_delete()
            console.print(
                "    Downloading from "
                f"\[{os.path.join(data_store.base_url, data_store.registry_fname)}]"
            )
            data_store.registry_fetch()
            console.print("  [green]✓ Done[/]")
            continue


@data.command()
@click.argument("files", nargs=-1)
@click.option(
    "--from-file",
    "-f",
    default=None,
    help="Optional path to a file list (YAML format). If this option is set, "
    "the FILES argument(s) will be ignored.",
)
def fetch(files, from_file):
    """
    Fetch files from the Eradiate data store. FILES is an arbitrary number of
    relative paths to files to be retrieved from the data store. If FILES is
    unset, the list of files is read from a YAML file which can be specified by
    using the ``--from-file`` option and defaults to
    ``$ERADIATE_SOURCE_DIR/resources/downloads.yml``.
    """
    if not files:
        if from_file is None:
            # TODO: fetch this list from online
            from_file = eradiate.config.source_dir / "resources/downloads.yml"
        console.print(f"Reading file list from '{from_file}'")
        yaml = YAML()
        files = yaml.load(from_file)

    for filename in files:
        try:
            console.print(f"[blue]Fetching '{filename}'[/]")
            path = eradiate.data.data_store.fetch(filename)
        except DataError:
            console.print(f"[red]✗[/] not found")
        else:
            console.print(f"[green]✓[/] found \[{path}]")


@data.command()
@click.option("--keep", "-k", is_flag=True, help="Keep registered files.")
def purge_cache(keep):
    """
    Purge the cache of online data stores.
    """
    for data_store_id, data_store in eradiate.data.data_store.stores.items():
        console.print(
            f"[bold cyan]{data_store_id}[/] [{data_store.__class__.__name__}]"
        )

        if isinstance(data_store, eradiate.data.SafeDirectoryDataStore):
            console.print(f"  Skipping")
            continue

        if isinstance(data_store, eradiate.data.SafeOnlineDataStore):
            console.print(f"  Purging '{data_store.path}'")
            if keep:
                data_store.purge(keep="registered")
            else:
                data_store.purge()
            continue

        if isinstance(data_store, eradiate.data.BlindOnlineDataStore):
            console.print(f"  Purging '{data_store.path}'")
            data_store.purge()
            continue


@data.command()
@click.argument("data_stores", nargs=-1)
@click.option(
    "-l", "--list-registry", is_flag=True, help="Show registry content if relevant."
)
def info(data_stores, list_registry):
    """
    Display information about data store configuration.

    The optional DATA_STORES argument specifies the list of data stores for
    which information is requested. If no data store ID is passed, information
    is displayed for all data stores.
    """

    # Build section list
    sections = [
        ("[purple]Base URL[/] \[base_url]", "base_url"),
        ("[purple]Local path[/] \[path]", "path"),
        ("[purple]Registry path[/] \[registry_path]", "registry_path"),
    ]

    if list_registry:
        sections.append(("Registered files", "registry_keys"))

    first = True

    for data_store_id, data_store in eradiate.data.data_store.stores.items():
        if data_stores and (data_store_id not in data_stores):
            continue

        # Collect section contents
        reprs = {}

        for attr in ["base_url", "path", "registry_path"]:
            try:
                reprs[attr] = f"'{getattr(data_store, attr)}'"
            except (NotImplementedError, AttributeError):
                reprs[attr] = None

        try:
            reprs["registry_keys"] = "\n".join(
                f"'{x}'" for x in sorted(data_store.registry.keys())
            )
        except (NotImplementedError, AttributeError):
            reprs["registry_keys"] = None

        # Display the content for current data store
        if not first:
            console.print()
        else:
            first = False

        console.print(
            f"[bold cyan]{data_store_id}[/] \[{data_store.__class__.__name__}]"
        )

        for section_title, repr_key in sections:
            the_repr = reprs[repr_key]

            if the_repr is not None:
                console.print(f"  {section_title}")
                console.print(textwrap.indent(reprs[repr_key], " " * 4))

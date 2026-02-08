"""CLI entry point for Timberline."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import click
from dotenv import load_dotenv
from loguru import logger

from timberline.config import Settings


def _setup_logging(level: str) -> None:
    logger.remove()
    logger.add(sys.stderr, level=level, format="<level>{level: <8}</level> | {message}")


def _load_settings(**overrides: str | None) -> Settings:
    load_dotenv()
    kwargs = {k: v for k, v in overrides.items() if v is not None}
    return Settings(**kwargs)


def _build_tools(settings: Settings):
    from timberline.knowledge.store import KnowledgeStore
    from timberline.loki.client import LokiClient
    from timberline.tools.knowledge_tools import build_knowledge_tools
    from timberline.tools.loki_tools import build_loki_tools

    client = LokiClient(base_url=settings.loki_url, org_id=settings.loki_org_id)
    store = KnowledgeStore(settings.knowledge_base_path)
    tools = build_loki_tools(client) + build_knowledge_tools(store)
    return tools, client, store


@click.group()
def cli() -> None:
    """Timberline - Agentic log analysis for Loki."""
    pass


@cli.command()
@click.option("--since", default="24h", help="How far back to analyze (e.g. 1h, 24h, 7d)")
@click.option("--namespace", default=None, help="Kubernetes namespace to focus on")
@click.option("--loki-url", default=None, help="Loki URL override")
@click.option("--log-level", default=None, help="Log level (DEBUG, INFO, WARNING)")
def analyze(since: str, namespace: str | None, loki_url: str | None, log_level: str | None) -> None:
    """Run an agentic log analysis."""
    settings = _load_settings(loki_url=loki_url, log_level=log_level)
    _setup_logging(settings.log_level)

    from timberline.agent import run_agent
    from timberline.prompts.system import build_system_prompt

    tools, client, store = _build_tools(settings)

    extra = ""
    if namespace:
        extra += f"Focus your analysis on the '{namespace}' namespace.\n"
    extra += f"Analyze logs from the last {since}.\n"

    system_prompt = build_system_prompt(
        knowledge_base_path=str(settings.knowledge_base_path),
        extra_context=extra,
    )

    prompt = f"Analyze the Kubernetes logs from the last {since}."
    if namespace:
        prompt += f" Focus on the '{namespace}' namespace."
    prompt += " Find issues, patterns, and provide actionable insights. Save your findings to the knowledge base."

    click.echo("Starting analysis...")
    click.echo(f"  Loki: {settings.loki_url}")
    click.echo(f"  Model: {settings.llm_model}")
    click.echo(f"  Time range: last {since}")
    if namespace:
        click.echo(f"  Namespace: {namespace}")
    click.echo()

    async def _run():
        try:
            return await run_agent(
                tools=tools,
                system_prompt=system_prompt,
                user_prompt=prompt,
                model=settings.llm_model,
                api_key=os.environ.get("OPENROUTER_API_KEY"),
                max_turns=settings.max_agent_turns,
            )
        finally:
            await client.close()

    result = asyncio.run(_run())

    click.echo("\n" + "=" * 60)
    click.echo("ANALYSIS COMPLETE")
    click.echo("=" * 60)
    click.echo(f"\nTurns used: {result.turns_used}")
    click.echo(f"Tool calls: {result.tool_calls_made}")
    if result.errors:
        click.echo(f"Errors: {len(result.errors)}")
    click.echo(f"\n{result.summary}")


@cli.command()
@click.option("--loki-url", default=None, help="Loki URL override")
def health(loki_url: str | None) -> None:
    """Check Loki connectivity."""
    settings = _load_settings(loki_url=loki_url)
    _setup_logging(settings.log_level)

    from timberline.loki.client import LokiClient

    async def _check():
        client = LokiClient(base_url=settings.loki_url, org_id=settings.loki_org_id)
        try:
            ready = await client.ready()
            if ready:
                click.echo(f"Loki ({settings.loki_url}): OK")
                labels = await client.labels()
                click.echo(f"  Labels: {', '.join(labels) if labels else '(none)'}")
            else:
                click.echo(f"Loki ({settings.loki_url}): NOT READY")
                sys.exit(1)
        except Exception as e:
            click.echo(f"Loki ({settings.loki_url}): ERROR - {e}")
            sys.exit(1)
        finally:
            await client.close()

    asyncio.run(_check())


@cli.group()
def kb() -> None:
    """Knowledge base commands."""
    pass


@kb.command("list")
@click.option("--directory", default=".", help="Directory to list")
def kb_list(directory: str) -> None:
    """List files in the knowledge base."""
    settings = _load_settings()
    from timberline.knowledge.store import KnowledgeStore

    store = KnowledgeStore(settings.knowledge_base_path)
    files = store.list_files(directory=directory)
    if files:
        for f in files:
            click.echo(f)
    else:
        click.echo("Knowledge base is empty.")


@kb.command("view")
@click.argument("path")
def kb_view(path: str) -> None:
    """View a file from the knowledge base."""
    settings = _load_settings()
    from timberline.knowledge.store import KnowledgeStore

    store = KnowledgeStore(settings.knowledge_base_path)
    try:
        content = store.read(path)
        click.echo(content)
    except FileNotFoundError:
        click.echo(f"File not found: {path}", err=True)
        sys.exit(1)


@kb.command("clear")
@click.option("--confirm", is_flag=True, help="Confirm deletion")
def kb_clear(confirm: bool) -> None:
    """Clear the knowledge base."""
    if not confirm:
        click.echo("Use --confirm to actually delete knowledge base contents.")
        return
    settings = _load_settings()
    import shutil

    kb_path = settings.knowledge_base_path
    if kb_path.exists():
        for item in kb_path.iterdir():
            if item.name == "README.md":
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
        click.echo("Knowledge base cleared.")
    else:
        click.echo("Knowledge base directory does not exist.")

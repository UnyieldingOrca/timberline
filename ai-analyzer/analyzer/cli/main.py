import click
from datetime import date, datetime, timedelta
from loguru import logger

from ..analysis.engine import AnalysisEngine
from ..config.settings import Settings


@click.group()
@click.option('--milvus-host', help='Milvus host (default: milvus)')
@click.option('--milvus-port', type=int, help='Milvus port (default: 19530)')
@click.option('--milvus-collection', help='Milvus collection name (default: timberline_logs)')
@click.option('--llm-provider', type=click.Choice(['openai', 'anthropic', 'local']),
              help='LLM provider (openai, anthropic, local)')
@click.option('--llm-model', help='LLM model name')
@click.option('--llm-api-key', help='LLM API key')
@click.option('--llm-endpoint', help='LLM endpoint URL (for local provider)')
@click.option('--report-output-dir', help='Report output directory')
@click.option('--max-logs', type=int, help='Maximum logs per analysis (default: 10000)')
@click.pass_context
def cli(ctx, **kwargs):
    """AI Log Analyzer CLI"""
    # Store CLI overrides in context for commands to use
    ctx.ensure_object(dict)
    ctx.obj['cli_overrides'] = {k.replace('_', '-'): v for k, v in kwargs.items() if v is not None}


@cli.command()
@click.option('--date', type=click.DateTime(formats=['%Y-%m-%d']),
              help='Specific date to analyze (YYYY-MM-DD)')
@click.pass_context
def analyze_daily(ctx, date_param):
    """Analyze logs for the past 24 hours or specific date"""
    try:
        logger.info("Starting AI log analysis")

        # Use provided date or default to yesterday
        if date_param:
            analysis_date = date_param.date()
        else:
            analysis_date = (datetime.now() - timedelta(days=1)).date()

        logger.info(f"Analyzing logs for date: {analysis_date}")

        # Initialize settings with CLI overrides
        settings = Settings.from_cli_overrides(ctx.obj.get('cli_overrides', {}))
        engine = AnalysisEngine(settings)

        # Run analysis
        result = engine.analyze_daily_logs(analysis_date)

        logger.info(f"Analysis completed. Processed {result.total_logs_processed} logs")
        logger.info(f"Health score: {result.health_score:.2f}")

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise click.ClickException(f"Analysis failed: {e}")


@cli.command()
@click.pass_context
def health_check(ctx):
    """Perform system health checks"""
    try:
        logger.info("Running health checks")

        # Initialize settings with CLI overrides
        settings = Settings.from_cli_overrides(ctx.obj.get('cli_overrides', {}))
        engine = AnalysisEngine(settings)

        # Basic connectivity tests
        milvus_ok = engine.milvus_client.health_check()
        llm_ok = engine.llm_client.health_check()

        if milvus_ok and llm_ok:
            logger.info("All health checks passed")
            click.echo("✓ System healthy")
        else:
            logger.error("Health checks failed")
            click.echo("✗ System unhealthy")
            exit(1)

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise click.ClickException(f"Health check failed: {e}")


if __name__ == '__main__':
    cli()
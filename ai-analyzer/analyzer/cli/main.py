import click
import sys
from datetime import date, datetime, timedelta
from loguru import logger

from .. import __version__
from ..analysis.engine import AnalysisEngine, AnalysisEngineError
from ..config.settings import Settings
from ..reporting.generator import ReportGenerator
from ..storage.milvus_client import MilvusQueryEngine
from ..storage.analysis_results_store import AnalysisResultsStore
from ..logging_config import configure_logging


@click.group()
@click.option('--milvus-host', help='Milvus host (default: milvus)')
@click.option('--milvus-port', type=int, help='Milvus port (default: 19530)')
@click.option('--milvus-collection', help='Milvus collection name (default: timberline_logs)')
@click.option('--llm-model', help='LLM model name')
@click.option('--llm-api-key', help='LLM API key')
@click.option('--llm-endpoint', help='LLM endpoint URL (for custom OpenAI-compatible endpoints)')
@click.option('--report-output-dir', help='Report output directory')
@click.option('--max-logs', type=int, help='Maximum logs per analysis (default: 10000)')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.option('--quiet', '-q', is_flag=True, help='Quiet mode (errors only)')
@click.pass_context
def cli(ctx, verbose, quiet, **kwargs):
    """AI Log Analyzer - Kubernetes log analysis with AI insights"""

    # Initialize settings to get log configuration
    settings = Settings()

    # Configure logging based on settings and CLI flags
    configure_logging(
        level=settings.log_level,
        json_format=(settings.log_format == 'json'),
        verbose=verbose,
        quiet=quiet
    )

    # Store CLI overrides in context for commands to use
    ctx.ensure_object(dict)
    ctx.obj['cli_overrides'] = {k.replace('_', '-'): v for k, v in kwargs.items() if v is not None}


@cli.command()
@click.option('--date', 'date_param', type=click.DateTime(formats=['%Y-%m-%d']),
              help='Specific date to analyze (YYYY-MM-DD)')
@click.option('--dry-run', is_flag=True, help='Validate configuration without running analysis')
@click.pass_context
def analyze_daily(ctx, date_param, dry_run):
    """Analyze logs for the past 24 hours or specific date"""
    try:
        # Use provided date or default to yesterday
        if date_param:
            analysis_date = date_param.date()
        else:
            analysis_date = (datetime.now() - timedelta(days=1)).date()

        logger.info(f"{'Validating configuration for' if dry_run else 'Starting AI log analysis for'} {analysis_date}")

        # Initialize settings with CLI overrides
        settings = Settings.from_cli_overrides(ctx.obj.get('cli_overrides', {}))

        if dry_run:
            click.echo("✓ Configuration validation passed")
            click.echo(f"Analysis would run for date: {analysis_date}")
            click.echo(f"Milvus: {settings.milvus_connection_string}")
            click.echo(f"LLM Model: {settings.llm_model}")
            if settings.llm_endpoint:
                click.echo(f"LLM Endpoint: {settings.llm_endpoint}")
            click.echo(f"Output Directory: {settings.report_output_dir}")
            return

        # Initialize analysis engine
        engine = AnalysisEngine(settings)

        # Run analysis
        with click.progressbar(length=8, label='Running analysis pipeline') as bar:
            result = engine.analyze_daily_logs(analysis_date)
            bar.update(8)  # Complete progress

        # Display results
        click.echo("\n" + "="*50)
        click.echo("📊 ANALYSIS RESULTS")
        click.echo("="*50)
        click.echo(f"Date: {result.analysis_date}")
        click.echo(f"Logs Processed: {result.total_logs_processed:,}")
        click.echo(f"Errors: {result.error_count}")
        click.echo(f"Warnings: {result.warning_count}")
        click.echo(f"Health Score: {result.health_score:.2f}/1.0")
        click.echo(f"Clusters: {len(result.analyzed_clusters)}")
        click.echo(f"Top Issues: {len(result.top_issues)}")
        click.echo(f"Execution Time: {result.execution_time:.1f}s")

        if result.top_issues:
            click.echo("\n🚨 TOP ISSUES:")
            for i, issue in enumerate(result.top_issues[:5], 1):
                click.echo(f"  {i}. [Severity {issue.severity}] {issue.log.message[:80]}...")

        logger.info(f"Analysis completed successfully")

    except AnalysisEngineError as e:
        logger.error(f"Analysis engine error: {e}")
        raise click.ClickException(str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise click.ClickException(f"Analysis failed: {e}")


@cli.command()
@click.pass_context
def health_check(ctx):
    """Perform comprehensive system health checks"""
    try:
        logger.info("Running health checks")

        # Initialize settings with CLI overrides
        settings = Settings.from_cli_overrides(ctx.obj.get('cli_overrides', {}))
        engine = AnalysisEngine(settings)

        # Run comprehensive health checks
        health_status = engine.health_check()

        # Display results
        click.echo("\n" + "="*30)
        click.echo("🏥 HEALTH CHECK RESULTS")
        click.echo("="*30)

        components = [
            ("Milvus Database", health_status['milvus']),
            ("LLM Provider", health_status['llm']),
            ("Results Store", health_status['results_store']),
            ("Report Generator", health_status['report_generator'])
        ]

        for name, status in components:
            icon = "✓" if status else "✗"
            color = "green" if status else "red"
            click.echo(click.style(f"{icon} {name}: {'OK' if status else 'FAILED'}", fg=color))

        overall = health_status['overall']
        if overall:
            click.echo(click.style("\n✅ Overall Status: HEALTHY", fg="green", bold=True))
            sys.exit(0)
        else:
            click.echo(click.style("\n❌ Overall Status: UNHEALTHY", fg="red", bold=True))
            sys.exit(1)

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        click.echo(click.style(f"❌ Health check failed: {e}", fg="red"))
        sys.exit(1)


@cli.command()
@click.option('--days', type=int, default=30, help='Number of days to keep (default: 30)')
@click.option('--dry-run', is_flag=True, help='Show what would be deleted without actually deleting')
@click.pass_context
def cleanup_reports(ctx, days, dry_run):
    """Clean up old report files"""
    try:
        logger.info(f"{'Checking' if dry_run else 'Cleaning up'} reports older than {days} days")

        settings = Settings.from_cli_overrides(ctx.obj.get('cli_overrides', {}))
        report_generator = ReportGenerator(settings)

        if dry_run:
            # List reports that would be cleaned up
            reports = report_generator.list_reports(limit=100)
            cutoff_time = datetime.now() - timedelta(days=days)

            old_reports = [
                r for r in reports
                if datetime.fromisoformat(r['modified']) < cutoff_time
            ]

            click.echo(f"Would delete {len(old_reports)} reports:")
            for report in old_reports[:10]:  # Show first 10
                click.echo(f"  - {report['filename']} ({report['modified']})")
            if len(old_reports) > 10:
                click.echo(f"  ... and {len(old_reports) - 10} more")
        else:
            removed_count = report_generator.cleanup_old_reports(keep_days=days)
            click.echo(f"✓ Cleaned up {removed_count} old report files")

    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        raise click.ClickException(f"Cleanup failed: {e}")


@cli.command()
@click.option('--limit', type=int, default=10, help='Number of recent reports to show')
@click.pass_context
def list_reports(ctx, limit):
    """List recent analysis reports"""
    try:
        settings = Settings.from_cli_overrides(ctx.obj.get('cli_overrides', {}))
        report_generator = ReportGenerator(settings)

        reports = report_generator.list_reports(limit=limit)

        if not reports:
            click.echo("No reports found.")
            return

        click.echo(f"\n📄 RECENT REPORTS ({len(reports)} found)")
        click.echo("="*50)

        for report in reports:
            size_mb = report['size_bytes'] / 1024 / 1024
            click.echo(f"{report['filename']}")
            click.echo(f"  Modified: {report['modified']}")
            click.echo(f"  Size: {size_mb:.2f} MB")
            click.echo()

    except Exception as e:
        logger.error(f"Failed to list reports: {e}")
        raise click.ClickException(f"Failed to list reports: {e}")


@cli.command()
@click.option('--limit', type=int, default=10, help='Number of recent results to show')
@click.pass_context
def list_stored_results(ctx, limit):
    """List analysis results stored in Milvus"""
    try:
        settings = Settings.from_cli_overrides(ctx.obj.get('cli_overrides', {}))

        results_store = AnalysisResultsStore(settings)
        results = results_store.list_recent_analyses(limit=limit)

        if not results:
            click.echo("No analysis results found in Milvus.")
            return

        click.echo(f"\n📊 STORED ANALYSIS RESULTS ({len(results)} found)")
        click.echo("="*80)

        for result in results:
            generated_at = datetime.fromtimestamp(result['generated_at'] / 1000)
            click.echo(f"\nDate: {result['analysis_date']}")
            click.echo(f"  Generated: {generated_at.isoformat()}")
            click.echo(f"  Total Logs: {result['total_logs_processed']:,}")
            click.echo(f"  Errors: {result['error_count']} ({result['error_rate']:.2f}%)")
            click.echo(f"  Warnings: {result['warning_count']} ({result['warning_rate']:.2f}%)")
            click.echo(f"  Clusters: {result['clusters_found']}")
            click.echo(f"  Top Issues: {result['top_issues_count']}")
            click.echo(f"  Execution Time: {result['execution_time']:.1f}s")

    except Exception as e:
        logger.error(f"Failed to list stored results: {e}")
        raise click.ClickException(f"Failed to list stored results: {e}")


@cli.command()
@click.argument('analysis_date')
@click.pass_context
def get_stored_result(ctx, analysis_date):
    """Get a specific analysis result from Milvus by date (YYYY-MM-DD)"""
    try:
        settings = Settings.from_cli_overrides(ctx.obj.get('cli_overrides', {}))

        results_store = AnalysisResultsStore(settings)
        result = results_store.get_analysis_by_date(analysis_date)

        if not result:
            click.echo(f"No analysis result found for date: {analysis_date}")
            return

        click.echo(f"\n📊 ANALYSIS RESULT FOR {analysis_date}")
        click.echo("="*80)

        generated_at = datetime.fromtimestamp(result['generated_at'] / 1000)
        click.echo(f"Generated: {generated_at.isoformat()}")
        click.echo(f"Total Logs: {result['total_logs_processed']:,}")
        click.echo(f"Errors: {result['error_count']} ({result['error_rate']:.2f}%)")
        click.echo(f"Warnings: {result['warning_count']} ({result['warning_rate']:.2f}%)")
        click.echo(f"Clusters: {result['clusters_found']}")
        click.echo(f"Top Issues: {result['top_issues_count']}")
        click.echo(f"Execution Time: {result['execution_time']:.1f}s")
        click.echo(f"\nLLM Summary:")
        click.echo(result['llm_summary'])

        # Optionally show report data
        if 'report_data' in result:
            click.echo("\n📄 Full report data available in JSON format")
            if click.confirm("Show full JSON report?", default=False):
                import json
                click.echo(json.dumps(result['report_data'], indent=2))

    except Exception as e:
        logger.error(f"Failed to get stored result: {e}")
        raise click.ClickException(f"Failed to get stored result: {e}")


@cli.command()
@click.pass_context
def version(ctx):
    """Show version information"""
    click.echo(f"AI Log Analyzer v{__version__}")
    click.echo("Kubernetes log analysis with AI insights")
    click.echo("Built with ❤️  using Python and Claude AI")


if __name__ == '__main__':
    cli()
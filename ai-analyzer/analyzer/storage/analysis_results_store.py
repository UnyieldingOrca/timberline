"""PostgreSQL-based storage for analysis results."""
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import desc

from ..models.log import DailyAnalysisResult
from ..config.settings import Settings
from ..db.base import get_engine, get_session_maker
from ..db.models import AnalysisResult


class AnalysisResultsStoreError(Exception):
    """Raised when analysis results storage operations fail"""
    pass


class AnalysisResultsStore:
    """Store and retrieve analysis results in PostgreSQL"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.engine = None
        self.session_maker = None
        self._connected = False

    def connect(self) -> bool:
        """Connect to PostgreSQL database"""
        try:
            logger.info(f"Connecting to PostgreSQL database")

            self.engine = get_engine(self.settings.database_url)
            self.session_maker = get_session_maker(self.engine)
            self._connected = True

            logger.info("Connected to PostgreSQL database")
            return True

        except SQLAlchemyError as e:
            logger.error(f"Database connection failed: {e}")
            raise AnalysisResultsStoreError(f"Failed to connect to database: {e}")
        except Exception as e:
            logger.error(f"Unexpected error connecting to database: {e}")
            raise AnalysisResultsStoreError(f"Connection failed: {e}")

    def disconnect(self) -> None:
        """Close database connection"""
        try:
            if self.engine:
                self.engine.dispose()
                self.engine = None
                self.session_maker = None
                self._connected = False

            logger.info("Disconnected from database")
        except Exception as e:
            logger.warning(f"Error during disconnect: {e}")

    def is_connected(self) -> bool:
        """Check if connected to database"""
        return self._connected and self.engine is not None

    def _get_session(self) -> Session:
        """Get database session"""
        if not self.is_connected():
            self.connect()

        if not self.session_maker:
            raise AnalysisResultsStoreError("Session maker not initialized")

        return self.session_maker()

    def store_analysis_result(
        self,
        analysis: DailyAnalysisResult,
        report: Dict[str, Any]
    ) -> int:
        """
        Store analysis result in database

        Args:
            analysis: The analysis result
            report: The generated report dictionary

        Returns:
            The ID of the inserted record
        """
        logger.info(f"Storing analysis result for {analysis.analysis_date}")

        session = self._get_session()
        try:
            # Create analysis result record
            result_record = AnalysisResult(
                analysis_date=analysis.analysis_date.isoformat(),
                generated_at=datetime.utcnow(),
                total_logs_processed=analysis.total_logs_processed,
                error_count=analysis.error_count,
                warning_count=analysis.warning_count,
                error_rate=analysis.error_rate,
                warning_rate=analysis.warning_rate,
                execution_time=analysis.execution_time,
                clusters_found=len(analysis.analyzed_clusters),
                top_issues_count=len(analysis.top_issues),
                report_data=report,
                llm_summary=analysis.llm_summary,
            )

            session.add(result_record)
            session.commit()

            inserted_id = result_record.id
            logger.info(f"Analysis result stored successfully with ID: {inserted_id}")

            return inserted_id

        except IntegrityError as e:
            session.rollback()
            logger.error(f"Duplicate analysis result for date {analysis.analysis_date}: {e}")
            raise AnalysisResultsStoreError(f"Analysis result already exists for {analysis.analysis_date}")
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Failed to store analysis result: {e}")
            raise AnalysisResultsStoreError(f"Storage failed: {e}")
        except Exception as e:
            session.rollback()
            logger.error(f"Unexpected error storing analysis result: {e}")
            raise AnalysisResultsStoreError(f"Storage failed: {e}")
        finally:
            session.close()

    def get_analysis_by_date(self, analysis_date: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve analysis result by date

        Args:
            analysis_date: ISO format date string (YYYY-MM-DD)

        Returns:
            Dictionary containing the analysis result, or None if not found
        """
        logger.info(f"Retrieving analysis result for date: {analysis_date}")

        session = self._get_session()
        try:
            result = session.query(AnalysisResult).filter(
                AnalysisResult.analysis_date == analysis_date
            ).first()

            if not result:
                logger.info(f"No analysis result found for date: {analysis_date}")
                return None

            logger.info(f"Retrieved analysis result for date: {analysis_date}")
            return {
                'id': result.id,
                'analysis_date': result.analysis_date,
                'generated_at': result.generated_at,
                'total_logs_processed': result.total_logs_processed,
                'error_count': result.error_count,
                'warning_count': result.warning_count,
                'error_rate': result.error_rate,
                'warning_rate': result.warning_rate,
                'execution_time': result.execution_time,
                'clusters_found': result.clusters_found,
                'top_issues_count': result.top_issues_count,
                'report_data': result.report_data,
                'llm_summary': result.llm_summary,
            }

        except SQLAlchemyError as e:
            logger.error(f"Failed to retrieve analysis result: {e}")
            raise AnalysisResultsStoreError(f"Retrieval failed: {e}")
        finally:
            session.close()

    def list_recent_analyses(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        List recent analysis results

        Args:
            limit: Maximum number of results to return

        Returns:
            List of analysis result dictionaries
        """
        logger.info(f"Listing recent analyses (limit: {limit})")

        session = self._get_session()
        try:
            results = session.query(AnalysisResult).order_by(
                desc(AnalysisResult.generated_at)
            ).limit(limit).all()

            logger.info(f"Retrieved {len(results)} recent analyses")

            return [
                {
                    'id': r.id,
                    'analysis_date': r.analysis_date,
                    'generated_at': r.generated_at,
                    'total_logs_processed': r.total_logs_processed,
                    'error_count': r.error_count,
                    'warning_count': r.warning_count,
                    'error_rate': r.error_rate,
                    'warning_rate': r.warning_rate,
                    'execution_time': r.execution_time,
                    'clusters_found': r.clusters_found,
                    'top_issues_count': r.top_issues_count,
                }
                for r in results
            ]

        except SQLAlchemyError as e:
            logger.error(f"Failed to list analyses: {e}")
            raise AnalysisResultsStoreError(f"List failed: {e}")
        finally:
            session.close()

    def delete_old_analyses(self, days_to_keep: int = 30) -> int:
        """
        Delete analysis results older than specified days

        Args:
            days_to_keep: Number of days to keep

        Returns:
            Number of records deleted
        """
        logger.info(f"Deleting analyses older than {days_to_keep} days")

        session = self._get_session()
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)

            deleted_count = session.query(AnalysisResult).filter(
                AnalysisResult.generated_at < cutoff_date
            ).delete()

            session.commit()

            logger.info(f"Deleted {deleted_count} old analyses")
            return deleted_count

        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Failed to delete old analyses: {e}")
            raise AnalysisResultsStoreError(f"Deletion failed: {e}")
        finally:
            session.close()

    def health_check(self) -> bool:
        """Check database connection health"""
        try:
            if not self.is_connected():
                self.connect()

            session = self._get_session()
            try:
                # Perform simple query
                session.query(AnalysisResult).limit(1).all()
                return True
            finally:
                session.close()

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

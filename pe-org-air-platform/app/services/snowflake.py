import snowflake.connector
from snowflake.connector import DictCursor
from snowflake.connector.pandas_tools import write_pandas
import logging
import json
import os
import uuid
import asyncio
import threading
import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.config import settings

logger = logging.getLogger(__name__)

logging.getLogger("snowflake.connector").setLevel(logging.WARNING)

class SnowflakeService:
    @staticmethod
    def _clean_data(val: Any) -> Any:
        """Fixes NaN/None values for Snowflake."""
        if val is None:
            return None
        # Handle Pandas/Numpy NaN
        if isinstance(val, (float, int)) and (np.isnan(val) or np.isinf(val)):
            return 0.0
        if isinstance(val, str):
            v_lower = val.lower().strip()
            if v_lower in ['nan', 'none', 'null', '']:
                return None
            return val
        if isinstance(val, (dict, list)):
            return json.loads(json.dumps(val, default=lambda x: None).replace(': NaN', ': null').replace(': nan', ': null'))
        return val

    def __init__(self):
        self.conn_params = {
            "user": settings.SNOWFLAKE_USER,
            "password": settings.SNOWFLAKE_PASSWORD.get_secret_value(),
            "account": settings.SNOWFLAKE_ACCOUNT,
            "warehouse": settings.SNOWFLAKE_WAREHOUSE,
            "database": settings.SNOWFLAKE_DATABASE,
            "schema": settings.SNOWFLAKE_SCHEMA,
            "role": settings.SNOWFLAKE_ROLE,
        }

        self._conn = None
        self._lock = threading.Lock()

    def get_connection(self):
        with self._lock:
            if self._conn is None or self._is_connection_closed():
                snowflake.connector.paramstyle = 'pyformat'
                
                self._conn = snowflake.connector.connect(
                    **self.conn_params,
                    autocommit=True,
                    insecure_mode=True, 
                    session_parameters={
                        'PYTHON_CONNECTOR_QUERY_RESULT_FORMAT': 'JSON', 
                        'USE_CACHED_RESULT': False
                    }
                )
        return self._conn
    
    def _is_connection_closed(self) -> bool:
        try:
            return self._conn is None or self._conn.is_closed()
        except Exception:
            return True

    async def connect(self):
        """Open Snowflake connection."""
        await asyncio.to_thread(self.get_connection)

    async def close(self):
        """Close Snowflake connection."""
        if self._conn:
            await asyncio.to_thread(self._conn.close)
            self._conn = None

    def _execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        with conn.cursor(DictCursor) as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [{k.lower(): v for k, v in dict(row).items()} for row in rows]
    
    def execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """Synchronous query execution."""
        return self._execute_query(query, params)
    
    def _execute_update(self, query: str, params: tuple = None) -> None:
        conn = self.get_connection()
        logger.debug(f"Executing SQL: {query}")
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
            conn.commit()
            logger.debug("SQL Execution and Commit successful.")
        except Exception as e:
            logger.error(f"SQL Execution failed: {e}")
            raise

    def _execute_many(self, query: str, params_list: List[tuple]) -> None:
        if not params_list:
            return
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.executemany(query, params_list)
            conn.commit()
        except Exception as e:
            logger.error(f"Bulk SQL Execution failed: {e}")
            conn.rollback()
            raise

    def _batch_write_df(self, df: pd.DataFrame, table_name: str) -> None:
        """Helper to write a DataFrame to Snowflake using the optimized write_pandas."""
        if df.empty:
            return
        conn = self.get_connection()
        
        # Use write_pandas for bulk loading
        try:
            df_copy = df.copy()
            df_copy.columns = [c.upper() for c in df_copy.columns]
            success, nchunks, nrows, _ = write_pandas(
                conn=conn,
                df=df_copy,
                table_name=table_name.upper(),
                quote_identifiers=False,
                auto_create_table=False
            )
            if not success:
                raise Exception(f"write_pandas reported failure")
            logger.info(f"Bulk-loaded {nrows} rows into {table_name} via write_pandas.")
            return
        except Exception as e:
            logger.warning(f"write_pandas failed for {table_name}, using SQL fallback: {e}")
            
        # Fallback to SQL INSERT
        try:
            columns = df.columns.tolist()
            placeholders = ', '.join(['%s'] * len(columns))
            col_names = ', '.join(columns)
            insert_sql = f"INSERT INTO {table_name} ({col_names}) VALUES ({placeholders})"
            
            values = [tuple(row) for row in df.values]
            
            with conn.cursor() as cursor:
                cursor.executemany(insert_sql, values)
            conn.commit()
            logger.info(f"Bulk-loaded {len(values)} rows into {table_name} via SQL fallback.")
        except Exception as fallback_error:
            logger.error(f"SQL fallback failed for {table_name}: {fallback_error}")
            conn.rollback()
            raise

    async def fetch_all(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self._execute_query, query, params)

    async def fetch_one(self, query: str, params: tuple = None) -> Optional[Dict[str, Any]]:
        results = await self.fetch_all(query, params)
        return results[0] if results else None


    async def execute(self, query: str, params: tuple = None) -> None:
        await asyncio.to_thread(self._execute_update, query, params)
        
    async def execute_many(self, query: str, params_list: List[tuple]) -> None:
        await asyncio.to_thread(self._execute_many, query, params_list)
    
    # Industries
    async def fetch_industries(self) -> List[Dict[str, Any]]:
        query = "SELECT * FROM industries ORDER BY name"
        return await self.fetch_all(query)

    async def fetch_industry_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM industries WHERE name = %s LIMIT 1"
        return await self.fetch_one(query, (name,))

    # Companies
    async def fetch_company(self, company_id: str) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM companies WHERE id = %s AND is_deleted = FALSE"
        return await self.fetch_one(query, (company_id,))

    async def fetch_company_by_ticker(self, ticker: str) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM companies WHERE ticker = %s AND is_deleted = FALSE LIMIT 1"
        return await self.fetch_one(query, (ticker,))

    async def fetch_companies_by_ticker_or_name(self, ticker: Optional[str], name: Optional[str]) -> List[Dict[str, Any]]:
        query = "SELECT id, ticker, name FROM companies WHERE (ticker = %s OR name = %s) AND is_deleted = FALSE"
        return await self.fetch_all(query, (ticker, name))

    async def count_industries(self) -> int:
        query = "SELECT COUNT(*) AS cnt FROM industries"
        res = await self.fetch_one(query)
        return res['cnt'] if res else 0

    async def create_sec_document(self, doc_data: Dict[str, Any]) -> None:
        query = """
            MERGE INTO documents AS target
            USING (SELECT %s AS id) AS source
            ON target.document_id = source.id
            WHEN MATCHED THEN UPDATE SET processing_status = 'UPDATED'
            WHEN NOT MATCHED THEN INSERT (
                document_id, cik, company_name, filing_type, 
                accession_number, s3_raw_path, content_hash, processing_status, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'COMPLETED', CURRENT_TIMESTAMP())
        """
        params = (
            doc_data['doc_id'],
            doc_data['doc_id'], doc_data['meta'].cik, doc_data['meta'].company_name, doc_data['meta'].filing_type,
            doc_data['meta'].accession_number, doc_data['s3_key'], doc_data['content_hash']
        )
        await self.execute(query, params)

    async def create_sec_document_chunks_bulk(self, chunk_params: List[tuple]) -> None:
        if not chunk_params:
            return
        query = """
            INSERT INTO document_chunks (
                chunk_id, document_id, chunk_index, 
                section_name, chunk_text, token_count
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """
        await self.execute_many(query, chunk_params)

    async def fetch_companies(self, limit: int, offset: int, industry_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if industry_id:
            query = "SELECT * FROM companies WHERE industry_id = %s AND is_deleted = FALSE ORDER BY name LIMIT %s OFFSET %s"
            params = (industry_id, limit, offset)
        else:
            query = "SELECT * FROM companies WHERE is_deleted = FALSE ORDER BY name LIMIT %s OFFSET %s"
            params = (limit, offset)
        return await self.fetch_all(query, params)
    
    async def count_companies(self, industry_id: Optional[str] = None) -> int:
        if industry_id:
            query = "SELECT COUNT(*) as count FROM companies WHERE industry_id = %s AND is_deleted = FALSE"
            res = await self.fetch_one(query, (industry_id,))
        else:
            query = "SELECT COUNT(*) as count FROM companies WHERE is_deleted = FALSE"
            res = await self.fetch_one(query)
        return res['count'] if res else 0

    async def create_company(self, company: Dict[str, Any]) -> None:
        query = """
            INSERT INTO companies (id, name, ticker, industry_id, position_factor, cik, name_norm, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP())
        """
        params = (
            str(company['id']), 
            company['name'], 
            company['ticker'], 
            str(company['industry_id']), 
            company['position_factor'],
            company.get('cik'),
            company.get('name_norm')
        )
        await self.execute(query, params)

    async def update_company(self, company_id: str, company: Dict[str, Any]) -> None:
        query = """
            UPDATE companies 
            SET name = %s, ticker = %s, industry_id = %s, position_factor = %s, cik = %s, name_norm = %s, updated_at = CURRENT_TIMESTAMP()
            WHERE id = %s
        """
        params = (
            company['name'],
            company['ticker'],
            str(company['industry_id']),
            company['position_factor'],
            company.get('cik'),
            company.get('name_norm'),
            company_id
        )
        await self.execute(query, params)

    async def delete_company(self, company_id: str) -> None:
        query = "UPDATE companies SET is_deleted = TRUE, updated_at = CURRENT_TIMESTAMP() WHERE id = %s"
        await self.execute(query, (company_id,))

    # Assessments
    async def fetch_assessment(self, assessment_id: str) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM assessments WHERE id = %s"
        return await self.fetch_one(query, (assessment_id,))

    async def list_assessments(self, limit: int, offset: int, company_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if company_id:
            query = "SELECT * FROM assessments WHERE company_id = %s ORDER BY assessment_date DESC LIMIT %s OFFSET %s"
            params = (company_id, limit, offset)
        else:
            query = "SELECT * FROM assessments ORDER BY assessment_date DESC LIMIT %s OFFSET %s"
            params = (limit, offset)
        return await self.fetch_all(query, params)

    async def count_assessments(self, company_id: Optional[str] = None) -> int:
        if company_id:
            query = "SELECT COUNT(*) as count FROM assessments WHERE company_id = %s"
            res = await self.fetch_one(query, (company_id,))
        else:
            query = "SELECT COUNT(*) as count FROM assessments"
            res = await self.fetch_one(query)
        return res['count'] if res else 0

    async def create_assessment(self, assessment: Dict[str, Any]) -> None:
        query = """
            INSERT INTO assessments (id, company_id, assessment_type, assessment_date, primary_assessor, secondary_assessor, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP())
        """
        params = (
            str(assessment['id']),
            str(assessment['company_id']),
            assessment['assessment_type'].value if hasattr(assessment['assessment_type'], 'value') else assessment['assessment_type'],
            assessment['assessment_date'],
            assessment.get('primary_assessor'),
            assessment.get('secondary_assessor'),
            'draft'
        )
        await self.execute(query, params)

    async def update_assessment_status(self, assessment_id: str, status: str) -> None:
        query = "UPDATE assessments SET status = %s WHERE id = %s"
        await self.execute(query, (status, assessment_id))

    # Dimension Scores
    async def create_dimension_score(self, score: Dict[str, Any]) -> None:
        query = """
            INSERT INTO dimension_scores (id, assessment_id, dimension, score, weight, confidence, evidence_count, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP())
        """
        params = (
            str(score['id']),
            str(score['assessment_id']),
            score['dimension'].value if hasattr(score['dimension'], 'value') else score['dimension'],
            score['score'],
            score.get('weight'),
            score.get('confidence'),
            score.get('evidence_count')
        )
        await self.execute(query, params)
    
    async def fetch_dimension_scores(self, assessment_id: str) -> List[Dict[str, Any]]:
        query = "SELECT * FROM dimension_scores WHERE assessment_id = %s"
        return await self.fetch_all(query, (assessment_id,))

    async def update_dimension_score(self, score_id: str, score: float, confidence: float) -> None:
        query = "UPDATE dimension_scores SET score = %s, confidence = %s WHERE id = %s"
        await self.execute(query, (score, confidence, score_id))

    # External Signals
    async def create_external_signal(self, signal: Dict[str, Any]) -> None:
        query = """
            INSERT INTO external_signals (id, signal_hash, company_id, category, source, signal_date, raw_value, normalized_score, confidence, metadata, created_at)
            SELECT %s, %s, %s, %s, %s, %s, %s, %s, %s, PARSE_JSON(%s), CURRENT_TIMESTAMP()
        """
        params = (
            str(signal['id']),
            signal.get('signal_hash'),
            str(signal['company_id']),
            str(signal['category'].value if hasattr(signal['category'], 'value') else signal['category']),
            str(signal['source']),
            str(signal['signal_date']),
            signal.get('raw_value'),
            signal.get('normalized_score'),
            signal.get('confidence'),
            json.dumps(signal.get('metadata', {})) if isinstance(signal.get('metadata'), dict) else signal.get('metadata')
        )
        await self.execute(query, params)

    async def create_external_signals_bulk(self, signals: List[Dict[str, Any]]) -> None:
        if not signals: return
        
        now_date = datetime.now().date()
        processed = []
        for s in signals:
            clean_s = {
                "id": str(s['id']),
                "signal_hash": str(s.get('signal_hash', '')),
                "company_id": str(s['company_id']),
                "category": str(s['category'].value if hasattr(s['category'], 'value') else s['category']),
                "source": str(s['source']),
                "signal_date": self._clean_data(s.get('signal_date')) or now_date,
                "raw_value": str(self._clean_data(s.get('raw_value')) or '')[:500],
                "normalized_score": float(self._clean_data(s.get('normalized_score')) or 0.0),
                "confidence": float(self._clean_data(s.get('confidence')) or 0.0),
                "metadata": json.dumps(self._clean_data(s.get('metadata', {})))
            }
            # Convert date string to actual date object for pandas/arrow
            if isinstance(clean_s["signal_date"], str):
                try:
                    clean_s["signal_date"] = datetime.strptime(clean_s["signal_date"], '%Y-%m-%d').date()
                except:
                    clean_s["signal_date"] = now_date
            processed.append(clean_s)

        df = pd.DataFrame(processed)
        await asyncio.to_thread(self._batch_write_df, df, "external_signals")

    async def create_signal_evidence_bulk(self, evidence_list: List[Dict[str, Any]]) -> None:
        if not evidence_list: return
        
        now_date = datetime.now().date()
        processed = []
        for e in evidence_list:
            desc = self._clean_data(e.get('description'))
            clean_e = {
                "id": str(e['id']),
                "signal_id": str(e['signal_id']),
                "company_id": str(e['company_id']),
                "category": str(e['category'].value if hasattr(e['category'], 'value') else e['category']),
                "source": str(e['source']),
                "title": str(self._clean_data(e['title']))[:500],
                "description": str(desc)[:2000] if desc else None,
                "url": str(self._clean_data(e.get('url')))[:1000] if e.get('url') else None,
                "tags": json.dumps(self._clean_data(e.get('tags', []))),
                "evidence_date": self._clean_data(e.get('evidence_date')) or now_date,
                "metadata": json.dumps(self._clean_data(e.get('metadata', {})))
            }
            if isinstance(clean_e["evidence_date"], str):
                try:
                    clean_e["evidence_date"] = datetime.strptime(clean_e["evidence_date"], '%Y-%m-%d').date()
                except:
                    clean_e["evidence_date"] = now_date
            processed.append(clean_e)

        df = pd.DataFrame(processed)
        await asyncio.to_thread(self._batch_write_df, df, "signal_evidence")

    async def upsert_company_signal_summary(self, summary: Dict[str, Any]) -> None:
        query = """
            MERGE INTO company_signal_summaries AS target
            USING (SELECT %s AS company_id, %s AS ticker, %s AS technology_hiring_score, %s AS innovation_activity_score, %s AS digital_presence_score, %s AS leadership_signals_score, %s AS composite_score, %s AS signal_count) AS source
            ON target.company_id = source.company_id
            WHEN MATCHED THEN
                UPDATE SET 
                    ticker = source.ticker,
                    technology_hiring_score = source.technology_hiring_score,
                    innovation_activity_score = source.innovation_activity_score,
                    digital_presence_score = source.digital_presence_score,
                    leadership_signals_score = source.leadership_signals_score,
                    composite_score = source.composite_score,
                    signal_count = source.signal_count,
                    last_updated = CURRENT_TIMESTAMP()
            WHEN NOT MATCHED THEN
                INSERT (company_id, ticker, technology_hiring_score, innovation_activity_score, digital_presence_score, leadership_signals_score, composite_score, signal_count, last_updated)
                VALUES (source.company_id, source.ticker, source.technology_hiring_score, source.innovation_activity_score, source.digital_presence_score, source.leadership_signals_score, source.composite_score, source.signal_count, CURRENT_TIMESTAMP())
        """
        params = (
            str(summary['company_id']),
            summary['ticker'],
            summary.get('technology_hiring_score', 0.0),
            summary.get('innovation_activity_score', 0.0),
            summary.get('digital_presence_score', 0.0),
            summary.get('leadership_signals_score', 0.0),
            summary.get('composite_score', 0.0),
            summary.get('signal_count', 0)
        )
        await self.execute(query, params)

    async def fetch_company_signal_summary(self, company_id: str) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM company_signal_summaries WHERE company_id = %s"
        return await self.fetch_one(query, (company_id,))

    async def fetch_external_signals(self, company_id: str, category: Optional[str] = None, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        query = "SELECT * FROM external_signals WHERE company_id = %s"
        params = [company_id]
        if category:
            query += " AND category = %s"
            params.append(category)
        query += " ORDER BY signal_date DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        return await self.fetch_all(query, tuple(params))

    async def fetch_signal_evidence(self, company_id: str, category: Optional[str] = None, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        query = "SELECT * FROM signal_evidence WHERE company_id = %s"
        params = [company_id]
        if category:
            query += " AND category = %s"
            params.append(category)
        query += " ORDER BY evidence_date DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        return await self.fetch_all(query, tuple(params))

    # SEC Documents
    async def update_company_cik(self, ticker: str, cik: str, company_name: str) -> None:
        """Update CIK and normalized name for a company based on ticker."""
        name_norm = " ".join((company_name or "").strip().casefold().split())
        query = """
            UPDATE companies 
            SET cik = %s, name_norm = %s, updated_at = CURRENT_TIMESTAMP()
            WHERE ticker = %s AND (cik IS NULL OR name_norm IS NULL)
        """
        await self.execute(query, (cik, name_norm, ticker))

    async def fetch_sec_documents(
        self, 
        company_filter: Optional[str] = None, 
        filing_type: Optional[str] = None, 
        limit: int = 50, 
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        where = []
        params: List[Any] = []

        if company_filter:
            where.append("(company_name ILIKE %s OR cik ILIKE %s OR document_id ILIKE %s)")
            like = f"%{company_filter}%"
            params.extend([like, like, like])
        
        if filing_type:
            where.append("filing_type = %s")
            params.append(filing_type)

        where_clause = ("WHERE " + " AND ".join(where)) if where else ""
        query = f"""
            SELECT * FROM documents
            {where_clause}
            ORDER BY document_id DESC
            LIMIT %s OFFSET %s
        """
        params.extend([limit, offset])
        return await self.fetch_all(query, tuple(params))

    async def fetch_sec_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM documents WHERE document_id = %s LIMIT 1"
        return await self.fetch_one(query, (document_id,))

    async def fetch_sec_document_chunks(
        self, 
        document_id: str, 
        section: Optional[str] = None, 
        limit: int = 200, 
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        where = ["document_id = %s"]
        params: List[Any] = [document_id]

        if section:
            where.append("section_name = %s")
            params.append(section)

        where_clause = " AND ".join(where)
        query = f"""
            SELECT * FROM document_chunks
            WHERE {where_clause}
            ORDER BY chunk_index ASC
            LIMIT %s OFFSET %s
        """
        params.extend([limit, offset])
        return await self.fetch_all(query, tuple(params))

    # Analytical Metrics
    async def fetch_industry_distribution(self) -> List[Dict[str, Any]]:
        query = """
            SELECT i.name, COUNT(c.id) as count
            FROM industries i
            LEFT JOIN companies c ON i.id = c.industry_id
            WHERE c.is_deleted = FALSE OR c.id IS NULL
            GROUP BY i.name
            ORDER BY count DESC
        """
        return await self.fetch_all(query)

    async def fetch_company_metrics(self, company_id: Optional[str] = None) -> List[Dict[str, Any]]:
        where_clause = ""
        params = []
        if company_id:
            where_clause = "AND c.id = %s"
            params.append(company_id)
            
        query = f"""
            SELECT 
                c.id, 
                c.name, 
                c.ticker,
                (SELECT COUNT(*) FROM external_signals s WHERE s.company_id = c.id) as signals,
                (SELECT COUNT(*) FROM signal_evidence e WHERE e.company_id = c.id) as evidence,
                (SELECT COUNT(*) FROM documents d WHERE UPPER(d.cik) = UPPER(c.cik) OR (c.ticker IS NOT NULL AND UPPER(d.cik) = UPPER(c.ticker))) as filings
            FROM companies c
            WHERE c.is_deleted = FALSE {where_clause}
            ORDER BY signals DESC
        """
        # Note: We fallback to ticker if CIK isn't set yet because the pipeline might use ticker as CIK initially
        return await self.fetch_all(query, tuple(params))

    async def fetch_signal_category_distribution(self, company_id: Optional[str] = None) -> List[Dict[str, Any]]:
        where_clause = ""
        params = []
        if company_id:
            where_clause = "WHERE company_id = %s"
            params.append(company_id)
            
        query = f"""
            SELECT category, COUNT(*) as count
            FROM external_signals
            {where_clause}
            GROUP BY category
            ORDER BY count DESC
        """
        return await self.fetch_all(query, tuple(params))

db = SnowflakeService()

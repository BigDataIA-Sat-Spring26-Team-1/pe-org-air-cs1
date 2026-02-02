import snowflake.connector
from snowflake.connector import DictCursor
from typing import List, Dict, Any, Optional
import asyncio
import threading
from app.config import settings

class SnowflakeService:
    def __init__(self):
        self.conn_params = {
            "user": settings.SNOWFLAKE_USER,
            "password": settings.SNOWFLAKE_PASSWORD,
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
                self._conn = snowflake.connector.connect(**self.conn_params)
        return self._conn
    
    def _is_connection_closed(self) -> bool:
        try:
            return self._conn is None or self._conn.is_closed()
        except Exception:
            return True

    async def connect(self):
        """Establish the persistent connection."""
        await asyncio.to_thread(self.get_connection)

    async def close(self):
        """Close the persistent connection."""
        if self._conn:
            await asyncio.to_thread(self._conn.close)
            self._conn = None

    def _execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        with conn.cursor(DictCursor) as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
            # Normalize keys to lowercase for Pydantic compatibility
            return [{k.lower(): v for k, v in dict(row).items()} for row in rows]
    
    def _execute_update(self, query: str, params: tuple = None) -> None:
        conn = self.get_connection()
        with conn.cursor() as cursor:
            cursor.execute(query, params)

    async def fetch_all(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self._execute_query, query, params)

    async def fetch_one(self, query: str, params: tuple = None) -> Optional[Dict[str, Any]]:
        results = await self.fetch_all(query, params)
        return results[0] if results else None


    async def execute(self, query: str, params: tuple = None) -> None:
        await asyncio.to_thread(self._execute_update, query, params)
    
    # Companies
    async def fetch_company(self, company_id: str) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM companies WHERE id = %s AND is_deleted = FALSE"
        return await self.fetch_one(query, (company_id,))

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
            INSERT INTO companies (id, name, ticker, industry_id, position_factor, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP())
        """
        params = (
            str(company['id']), 
            company['name'], 
            company['ticker'], 
            str(company['industry_id']), 
            company['position_factor']
        )
        await self.execute(query, params)

    async def update_company(self, company_id: str, company: Dict[str, Any]) -> None:
        query = """
            UPDATE companies 
            SET name = %s, ticker = %s, industry_id = %s, position_factor = %s, updated_at = CURRENT_TIMESTAMP()
            WHERE id = %s
        """
        params = (
            company['name'],
            company['ticker'],
            str(company['industry_id']),
            company['position_factor'],
            company_id
        )
        await self.execute(query, params)

    async def delete_company(self, company_id: str) -> None:
        query = "UPDATE companies SET is_deleted = TRUE, updated_at = CURRENT_TIMESTAMP() WHERE id = %s"
        await self.execute(query, (company_id,))
    
    # Industries
    async def fetch_industries(self) -> List[Dict[str, Any]]:
        query = "SELECT * FROM industries ORDER BY name"
        return await self.fetch_all(query)

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

db = SnowflakeService()

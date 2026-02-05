import random
from typing import Dict, Any, List
import structlog

logger = structlog.get_logger()

class BaseSignalCollector:
    def collect(self, ticker: str) -> Dict[str, Any]:
        raise NotImplementedError

class JobSignalCollector(BaseSignalCollector):
    """
    Simulates collecting job posting data to assess AI hiring.
    """
    def collect(self, ticker: str) -> Dict[str, Any]:
        # Deterministic simulation based on ticker
        random.seed(ticker + "jobs")
        
        total_postings = random.randint(50, 5000)
        ai_keywords = ["machine learning", "artificial intelligence", "data science", "nlp", "computer vision"]
        
        # Tech companies have higher ratio
        is_tech = ticker in ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'META', 'AMZN']
        ratio = random.uniform(0.1, 0.3) if is_tech else random.uniform(0.01, 0.1)
        
        ai_postings = int(total_postings * ratio)
        
        return {
            "total_openings": total_postings,
            "ai_roles": ai_postings,
            "ai_percentage": round((ai_postings / total_postings) * 100, 2),
            "top_keywords": random.sample(ai_keywords, k=3)
        }

class PatentSignalCollector(BaseSignalCollector):
    """
    Simulates USPTO patent search for AI terms.
    """
    def collect(self, ticker: str) -> Dict[str, Any]:
        random.seed(ticker + "patents")
        
        is_tech = ticker in ['AAPL', 'MSFT', 'GOOGL', 'IBM', 'NVDA']
        base_patents = random.randint(100, 1000) if is_tech else random.randint(0, 50)
        
        return {
            "total_patents_l12m": base_patents,
            "ai_patents": int(base_patents * random.uniform(0.3, 0.8)),
            "top_classes": ["G06N", "G06F", "H04L"] # Common IPC classes for AI
        }

class TechStackCollector(BaseSignalCollector):
    """
    Simulates BuiltWith technology stack analysis.
    """
    def collect(self, ticker: str) -> Dict[str, Any]:
        random.seed(ticker + "tech")
        
        cloud_providers = ["AWS", "Azure", "GCP"]
        ai_frameworks = ["TensorFlow", "PyTorch", "Scikit-learn", "Keras"]
        
        has_cloud = random.choice([True, True, False]) # Likely has cloud
        
        return {
            "cloud_provider": random.choice(cloud_providers) if has_cloud else None,
            "ai_frameworks": random.sample(ai_frameworks, k=random.randint(1, 4)) if has_cloud else [],
            "modern_stack_score": random.randint(60, 100)
        }

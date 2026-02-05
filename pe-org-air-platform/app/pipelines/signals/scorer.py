from typing import Dict, Any
from decimal import Decimal

class SignalScorer:
    """
    Normalizes and scores raw signal data.
    """
    
    def normalize_hiring(self, data: Dict[str, Any]) -> float:
        # Benchmark: 20% AI roles is 100/100
        percentage = data.get("ai_percentage", 0)
        score = (percentage / 20.0) * 100
        return min(100.0, max(0.0, score))

    def normalize_patents(self, data: Dict[str, Any]) -> float:
        # Benchmark: 50 AI patents is 100/100
        count = data.get("ai_patents", 0)
        score = (count / 50.0) * 100
        return min(100.0, max(0.0, score))

    def normalize_tech(self, data: Dict[str, Any]) -> float:
        # Use the "modern_stack_score" directly or heuristic
        base = data.get("modern_stack_score", 50)
        # Bonus for having PyTorch/TensorFlow
        frameworks = len(data.get("ai_frameworks", []))
        score = base + (frameworks * 5)
        return min(100.0, max(0.0, float(score)))

    def calculate_composite(self, hiring_score: float, patent_score: float, tech_score: float) -> Dict[str, Any]:
        weights = {"hiring": 0.4, "patents": 0.3, "tech": 0.3}
        
        composite = (hiring_score * weights["hiring"]) + \
                    (patent_score * weights["patents"]) + \
                    (tech_score * weights["tech"])
                    
        grade = "F"
        if composite >= 90: grade = "A"
        elif composite >= 80: grade = "B"
        elif composite >= 70: grade = "C"
        elif composite >= 60: grade = "D"
        
        return {
            "composite_score": round(composite, 2),
            "grade": grade,
            "components": {
                "hiring": round(hiring_score, 2),
                "innovation": round(patent_score, 2),
                "tech": round(tech_score, 2)
            }
        }

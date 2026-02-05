import re
from pathlib import Path
from typing import Dict, Optional, List
import bs4
from bs4 import BeautifulSoup
import pdfplumber
import structlog

logger = structlog.get_logger()

class SecParser:
    """
    Parses SEC filings (HTML/PDF/TXT) and attempts to extract key sections:
    - Item 1: Business
    - Item 1A: Risk Factors
    - Item 7: MD&A
    """
    
    SECTION_PATTERNS = {
        "Item 1": [r"Item\s+1\.\s+Business", r"ITEM\s+1\.\s+BUSINESS"],
        "Item 1A": [r"Item\s+1A\.\s+Risk\s+Factors", r"ITEM\s+1A\.\s+RISK\s+FACTORS"],
        "Item 7": [r"Item\s+7\.\s+Management", r"ITEM\s+7\.\s+MANAGEMENT"],
        "End": [r"Item\s+8\.", r"Item\s+1B\.", r"Item\s+2\."]
    }

    def parse(self, file_path: Path) -> Dict[str, str]:
        """
        Main entry point. Returns dictionary of Section Name -> Text Content.
        """
        suffix = file_path.suffix.lower()
        
        if suffix == '.html' or suffix == '.htm':
            return self._parse_html(file_path)
        elif suffix == '.txt':
            # Check if it's actually HTML inside TXT (common in Edgar)
            with open(file_path, 'r', errors='ignore') as f:
                head = f.read(1000)
            if "<html" in head.lower() or "<xml" in head.lower():
                return self._parse_html(file_path)
            else:
                return self._parse_text_fallback(file_path)
        elif suffix == '.pdf':
            return self._parse_pdf(file_path)
        else:
            logger.warning("unsupported_file_type", path=str(file_path))
            return {}

    def _parse_html(self, path: Path) -> Dict[str, str]:
        """
        Parses HTML using BeautifulSoup.
        Heuristic: Iterate through tags, switch active section when header found.
        """
        sections = {"Item 1": "", "Item 1A": "", "Item 7": ""}
        current_section = None
        
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                soup = BeautifulSoup(f, 'lxml')
                
            # Remove script/style
            for s in soup(["script", "style"]):
                s.extract()
                
            # Linear scan of text elements
            # This is a simplified approach; robust regex on full text is often safer 
            # for "dirty" HTML than DOM traversal.
            text = soup.get_text(separator="\n")
            return self._extract_sections_regex(text)
            
        except Exception as e:
            logger.error("html_parse_error", path=str(path), error=str(e))
            return {}

    def _parse_pdf(self, path: Path) -> Dict[str, str]:
        try:
            full_text = []
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    txt = page.extract_text()
                    if txt:
                        full_text.append(txt)
            
            combined_text = "\n".join(full_text)
            return self._extract_sections_regex(combined_text)
        except Exception as e:
            logger.error("pdf_parse_error", path=str(path), error=str(e))
            return {}

    def _parse_text_fallback(self, path: Path) -> Dict[str, str]:
        # Implementation for plain text
        try:
             with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
                return self._extract_sections_regex(text)
        except Exception:
            return {}

    def _extract_sections_regex(self, text: str) -> Dict[str, str]:
        """
        Uses distinct regex to slice the document text.
        NOTE: This is the 'hard' part of SEC parsing.
        """
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Simple slicing strategy
        # Find start indices
        idxs = {}
        for section, patterns in self.SECTION_PATTERNS.items():
            for pat in patterns:
                match = re.search(pat, text)
                if match:
                    idxs[section] = match.start()
                    break
        
        results = {}
        
        # Helper to slice
        def extract_slice(start_key, end_keys_candidates):
            if start_key not in idxs: 
                return ""
            start_idx = idxs[start_key]
            
            # Find the nearest end key that is AFTER start_idx
            end_idx = len(text)
            for end_key in end_keys_candidates:
                if end_key in idxs and idxs[end_key] > start_idx:
                    end_idx = min(end_idx, idxs[end_key])
            
            # Sanity limit: max 500k chars to avoid capturing whole doc if end missing
            return text[start_idx:min(end_idx, start_idx + 1000000)]

        # Item 1 -> Ends at 1A or 2
        results["Item 1"] = extract_slice("Item 1", ["Item 1A", "End"])
        
        # Item 1A -> Ends at 1B or 2
        results["Item 1A"] = extract_slice("Item 1A", ["End"])
        
        # Item 7 -> Ends at 7A or 8
        results["Item 7"] = extract_slice("Item 7", ["End"]) # Need better end markers for Item 7
        
        # Filter out empty results or very short ones (false positives)
        return {k: v for k, v in results.items() if len(v) > 500}


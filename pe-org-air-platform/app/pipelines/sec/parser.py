import re
from pathlib import Path
from typing import Dict, Optional, List
from bs4 import BeautifulSoup
import pdfplumber
import structlog

logger = structlog.get_logger()

class SecParser:
    def __init__(self):
        self.PATTERNS_BY_FORM = {
            "10-K": {
                "Business": [r"Item\s+1\.\s+Business", r"ITEM\s+1\.\s+BUSINESS"],
                "Risk Factors": [r"Item\s+1A\.\s+Risk\s+Factors"],
                "MD&A": [r"Item\s+7\.\s+Management"]
            },
            "10-Q": {
                "MD&A": [r"Item\s+2\.\s+Management", r"ITEM\s+2\.\s+MANAGEMENT"],
                "Risk Factors": [r"Item\s+1A\.\s+Risk\s+Factors"]
            },
            "8-K": {
                "Events": [r"Item\s+8\.01", r"Item\s+5\.02", r"Item\s+1\.01"]
            },
            "DEF 14A": {
                "CD&A": [r"COMPENSATION\s+DISCUSSION\s+(?:AND|&)\s+ANALYSIS"],
                "Summary Tables": [r"SUMMARY\s+COMPENSATION\s+TABLE", r"EXECUTIVE\s+COMPENSATION\s+TABLES"],
                "Incentive Plan": [r"ANNUAL\s+INCENTIVE\s+PLAN", r"LONG-TERM\s+INCENTIVE"]
            }
        }

    def parse(self, file_path: Path, form_type: str) -> Dict[str, str]:
        text = ""
        suffix = file_path.suffix.lower()

        try:
            if suffix in ['.html', '.htm', '.txt']:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    raw_content = f.read()

                    if "<html" in raw_content.lower() or "<xml" in raw_content.lower():
                        soup = BeautifulSoup(raw_content, 'lxml')
                        for script in soup(["script", "style"]):
                            script.extract()
                        text = soup.get_text(separator="\n\n")
                    else:
                        text = raw_content

            elif suffix == '.pdf':
                with pdfplumber.open(file_path) as pdf:
                    text = "\n".join([p.extract_text() or "" for p in pdf.pages])

        except Exception as e:
            logger.error("file_read_error", path=str(file_path), error=str(e))
            return {}

        clean_text = re.sub(r'\s+', ' ', text)
        return self._extract_sections(clean_text, form_type)

    def _extract_sections(self, text: str, form_type: str) -> Dict[str, str]:
        patterns = self.PATTERNS_BY_FORM.get(form_type, {})
        results = {}

        all_start_patterns = []
        for pat_list in patterns.values():
            all_start_patterns.extend(pat_list)

        all_start_patterns.extend([r"Item\s+15\.", r"SIGNATURES", r"PART\s+II", r"Item\s+6\."])

        for section_name, specific_patterns in patterns.items():
            matches = []

            for pat in specific_patterns:
                for m in re.finditer(pat, text, re.IGNORECASE):
                    matches.append(m)

            if not matches:
                continue

            valid_match = None
            for m in matches:
                if m.start() < 3000 and len(matches) > 1:
                    continue
                valid_match = m
                break

            if not valid_match:
                continue

            start_idx = valid_match.start()
            end_idx = len(text)

            for end_pat in all_start_patterns:
                next_match = re.search(end_pat, text[start_idx + 50:])
                if next_match:
                    absolute_end = start_idx + 50 + next_match.start()
                    if absolute_end < end_idx:
                        end_idx = absolute_end

            content = text[start_idx:end_idx]

            if len(content) > 500:
                results[section_name] = content

        return results

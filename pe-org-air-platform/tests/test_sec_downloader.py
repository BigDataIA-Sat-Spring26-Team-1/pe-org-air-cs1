import pytest
from pathlib import Path

from app.pipelines.sec.downloader import SecDownloader


@pytest.mark.asyncio
async def test_sec_downloader_creates_download_dir(tmp_path):
    download_dir = tmp_path / "sec_downloads"

    d = SecDownloader(
        download_dir=str(download_dir),
        email="piyush.a@northeastern.edu",  # fix email
        company="PE-OrgAIR",
        max_workers=1,
    )

    metas = await d.download_filings(
        tickers=["AAPL"],
        filing_types=["10-K"],
        limit_per_type=1,
    )

    base_dir = Path(download_dir) / "sec-edgar-filings"
    assert base_dir.exists()

    # Optional debug
    print("discovered_count:", len(metas))

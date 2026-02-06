import pytest
import time
from uuid import UUID


@pytest.mark.asyncio
class TestFullApplicationFlow:
    """
    Integration tests ensuring endpoints work in the correct logical order:
    Industries -> Companies -> Assessments -> Dimension Scores
    """
    
    # State to share between tests
    industry_id = None
    company_id = None
    assessment_id = None
    score_id = None

    async def test_01_industries_list(self, client):
        """Ensure industries are seeded and accessible."""
        response = await client.get("/api/v1/industries/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        # Save an industry ID for next steps
        TestFullApplicationFlow.industry_id = data[0]["id"]
        print(f"\nIndustry selected: {TestFullApplicationFlow.industry_id}")

    async def test_02_company_lifecycle(self, client):
        """Create -> Get -> Update -> List."""
        # 1. Create
        payload = {
            "name": f"Flow Test Co {int(time.time())}",
            "ticker": "FLOW",
            "industry_id": TestFullApplicationFlow.industry_id,
            "position_factor": 0.5
        }
        res_create = await client.post("/api/v1/companies/", json=payload)
        assert res_create.status_code == 201
        TestFullApplicationFlow.company_id = res_create.json()["id"]

        # 2. Get Single
        res_get = await client.get(f"/api/v1/companies/{TestFullApplicationFlow.company_id}")
        assert res_get.status_code == 200
        assert res_get.json()["name"] == payload["name"]

        # 3. Update
        update_payload = payload.copy()
        update_payload["name"] = "Updated Flow Co"
        res_update = await client.put(f"/api/v1/companies/{TestFullApplicationFlow.company_id}", json=update_payload)
        assert res_update.status_code == 200
        assert res_update.json()["name"] == "Updated Flow Co"

        # 4. List Check (Filter by industry and use large page size to ensure it's found)
        params = {"industry_id": TestFullApplicationFlow.industry_id, "page_size": 100}
        res_list = await client.get("/api/v1/companies/", params=params)
        assert res_list.status_code == 200
        ids = [c["id"] for c in res_list.json()["items"]]
        assert TestFullApplicationFlow.company_id in ids

    async def test_03_assessment_lifecycle(self, client):
        """Create -> List -> Get -> Patch Status."""
        # 1. Create (State check: requires company_id)
        payload = {
            "company_id": TestFullApplicationFlow.company_id,
            "assessment_type": "due_diligence",
            "primary_assessor": "Test Lead"
        }
        res_create = await client.post("/api/v1/assessments", json=payload)
        assert res_create.status_code == 201
        TestFullApplicationFlow.assessment_id = res_create.json()["id"]

        # 2. Get Single
        res_get = await client.get(f"/api/v1/assessments/{TestFullApplicationFlow.assessment_id}")
        assert res_get.status_code == 200
        assert res_get.json()["status"] == "draft"

        # 3. Update Status (Valid: Draft -> In Progress)
        res_patch = await client.patch(
            f"/api/v1/assessments/{TestFullApplicationFlow.assessment_id}/status", 
            json={"status": "in_progress"}
        )
        assert res_patch.status_code == 200
        assert res_patch.json()["status"] == "in_progress"

        # 4. Invalid Transition (In Progress -> Approved directly should fail)
        res_invalid = await client.patch(
            f"/api/v1/assessments/{TestFullApplicationFlow.assessment_id}/status", 
            json={"status": "approved"}
        )
        assert res_invalid.status_code == 400
        assert "Invalid status transition" in res_invalid.json()["detail"]

        # 5. Valid Transition (In Progress -> Submitted)
        res_valid = await client.patch(
            f"/api/v1/assessments/{TestFullApplicationFlow.assessment_id}/status", 
            json={"status": "submitted"}
        )
        assert res_valid.status_code == 200

    async def test_04_dimension_scores_lifecycle(self, client):
        """Add -> List -> Update."""
        # 1. Add Score
        payload = {
            "assessment_id": TestFullApplicationFlow.assessment_id,
            "dimension": "data_infrastructure",
            "score": 88.0,
            "confidence": 0.9
        }
        res_add = await client.post(f"/api/v1/assessments/{TestFullApplicationFlow.assessment_id}/scores", json=payload)
        assert res_add.status_code == 201
        TestFullApplicationFlow.score_id = res_add.json()["id"]

        # 2. List Scores
        res_list = await client.get(f"/api/v1/assessments/{TestFullApplicationFlow.assessment_id}/scores")
        assert res_list.status_code == 200
        assert len(res_list.json()) >= 1
        assert res_list.json()[0]["dimension"] == "data_infrastructure"

        # 3. Update Score
        update_payload = {
            "assessment_id": TestFullApplicationFlow.assessment_id,
            "dimension": "data_infrastructure",
            "score": 95.0,
            "confidence": 1.0
        }
        res_upd = await client.put(f"/api/v1/scores/{TestFullApplicationFlow.score_id}", json=update_payload)
        assert res_upd.status_code == 200
        # Note: Depending on DAO implementation, we verify updated fields
        assert res_upd.json()["score"] == 95.0

    async def test_05_error_handling_and_deletion(self, client):
        """Test invalid IDs, missing records, and final cleanup Deletion."""
        # 1. Missing Resource (404)
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        res_404 = await client.get(f"/api/v1/companies/{fake_uuid}")
        assert res_404.status_code == 404

        # 2. Invalid UUID format (422)
        res_422 = await client.get("/api/v1/companies/not-a-uuid")
        assert res_422.status_code == 422

        # 3. Final Deletion (Cleanup)
        res_del = await client.delete(f"/api/v1/companies/{TestFullApplicationFlow.company_id}")
        assert res_del.status_code == 204

        # 4. Verify Delete worked (GET should now be 404)
        res_post_del = await client.get(f"/api/v1/companies/{TestFullApplicationFlow.company_id}")
        assert res_post_del.status_code == 404
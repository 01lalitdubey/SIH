"""End-to-end API tests against an in-memory SQLite DB (see conftest.py).

Background tasks (the mock pipeline) run synchronously within TestClient's
request/response cycle, so jobs are already finished by the time a POST
/process call returns — no polling needed here, unlike the live manual
test log in README.md which exercises real async timing against Postgres.
"""

import uuid


def test_health(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"


def test_upload_valid_image(client, sample_image_bytes):
    resp = client.post(
        "/api/v1/images/upload",
        files={"file": ("sample.jpg", sample_image_bytes, "image/jpeg")},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["filename"] == "sample.jpg"
    assert body["width"] == 200
    assert body["height"] == 100
    assert body["file_size"] == len(sample_image_bytes)


def test_upload_rejects_unsupported_type(client):
    resp = client.post(
        "/api/v1/images/upload",
        files={"file": ("notes.txt", b"hello world", "text/plain")},
    )
    assert resp.status_code == 415


def test_upload_rejects_empty_file(client):
    resp = client.post(
        "/api/v1/images/upload",
        files={"file": ("empty.jpg", b"", "image/jpeg")},
    )
    assert resp.status_code == 400


def test_list_and_get_image(client, sample_image_bytes):
    created = client.post(
        "/api/v1/images/upload",
        files={"file": ("list-me.jpg", sample_image_bytes, "image/jpeg")},
    ).json()

    listing = client.get("/api/v1/images")
    assert listing.status_code == 200
    assert any(item["id"] == created["id"] for item in listing.json())

    single = client.get(f"/api/v1/images/{created['id']}")
    assert single.status_code == 200
    assert single.json()["filename"] == "list-me.jpg"


def test_get_image_not_found(client):
    resp = client.get(f"/api/v1/images/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_process_requires_image_or_aoi(client):
    resp = client.post(
        "/api/v1/process",
        json={"analysis_name": "No source", "scale_factor": 2},
    )
    assert resp.status_code == 422


def test_process_rejects_invalid_scale_factor(client):
    resp = client.post(
        "/api/v1/process",
        json={
            "analysis_name": "Bad scale",
            "scale_factor": 3,
            "aoi": {"north": 1, "south": 0, "east": 1, "west": 0},
        },
    )
    assert resp.status_code == 422


def test_process_rejects_unknown_image(client):
    resp = client.post(
        "/api/v1/process",
        json={
            "image_id": str(uuid.uuid4()),
            "analysis_name": "Ghost image",
            "scale_factor": 2,
        },
    )
    assert resp.status_code == 404


def test_full_pipeline_success_with_image(client, sample_image_bytes):
    image = client.post(
        "/api/v1/images/upload",
        files={"file": ("pipeline.jpg", sample_image_bytes, "image/jpeg")},
    ).json()

    job = client.post(
        "/api/v1/process",
        json={
            "image_id": image["id"],
            "analysis_name": "Pipeline Test",
            "scale_factor": 2,
        },
    ).json()
    assert job["status"] == "queued"

    status_resp = client.get(f"/api/v1/process/{job['job_id']}")
    assert status_resp.status_code == 200
    completed = status_resp.json()
    assert completed["status"] == "completed"
    assert completed["current_stage"] == "evaluation"
    assert completed["started_at"] is not None
    assert completed["completed_at"] is not None

    result_resp = client.get(f"/api/v1/results/{job['job_id']}")
    assert result_resp.status_code == 200
    result = result_resp.json()
    assert result["is_mock"] is True
    assert result["output_width"] == 400  # 200 * scale_factor 2
    assert result["output_height"] == 200  # 100 * scale_factor 2
    assert result["psnr"] is not None
    assert result["ssim"] is not None
    assert result["lpips"] is not None


def test_aoi_only_job_completes_without_output_file(client):
    job = client.post(
        "/api/v1/process",
        json={
            "analysis_name": "AOI only",
            "scale_factor": 4,
            "aoi": {"north": 25.7, "south": 20.6, "east": 81.6, "west": 72.4},
        },
    ).json()

    result = client.get(f"/api/v1/results/{job['job_id']}").json()
    assert result["output_path"] is None
    assert result["output_width"] is None
    assert result["psnr"] is not None


def test_simulate_failure(client, sample_image_bytes):
    image = client.post(
        "/api/v1/images/upload",
        files={"file": ("fail.jpg", sample_image_bytes, "image/jpeg")},
    ).json()

    job = client.post(
        "/api/v1/process",
        json={
            "image_id": image["id"],
            "analysis_name": "Failure Test",
            "scale_factor": 2,
            "simulate_failure": True,
        },
    ).json()

    status_resp = client.get(f"/api/v1/process/{job['job_id']}").json()
    assert status_resp["status"] == "failed"
    assert status_resp["current_stage"] == "super_resolution"
    assert "super_resolution" in status_resp["error_message"]

    # No result should exist for a failed job.
    result_resp = client.get(f"/api/v1/results/{job['job_id']}")
    assert result_resp.status_code == 404


def test_process_job_not_found(client):
    resp = client.get(f"/api/v1/process/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_result_not_found_for_unknown_job(client):
    resp = client.get(f"/api/v1/results/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_list_processing_jobs(client, sample_image_bytes):
    image = client.post(
        "/api/v1/images/upload",
        files={"file": ("list-jobs.jpg", sample_image_bytes, "image/jpeg")},
    ).json()
    created = client.post(
        "/api/v1/process",
        json={"image_id": image["id"], "analysis_name": "Listed Job", "scale_factor": 2},
    ).json()

    listing = client.get("/api/v1/process").json()
    assert any(j["job_id"] == created["job_id"] for j in listing)


def test_image_file_endpoint_serves_bytes(client, sample_image_bytes):
    image = client.post(
        "/api/v1/images/upload",
        files={"file": ("serve-me.jpg", sample_image_bytes, "image/jpeg")},
    ).json()

    resp = client.get(f"/api/v1/images/{image['id']}/file")
    assert resp.status_code == 200
    assert resp.content == sample_image_bytes


def test_result_file_endpoint_serves_output_image(client, sample_image_bytes):
    image = client.post(
        "/api/v1/images/upload",
        files={"file": ("serve-output.jpg", sample_image_bytes, "image/jpeg")},
    ).json()
    job = client.post(
        "/api/v1/process",
        json={"image_id": image["id"], "analysis_name": "Serve Output", "scale_factor": 2},
    ).json()

    resp = client.get(f"/api/v1/results/{job['job_id']}/file")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert len(resp.content) > 0


def test_result_file_404_for_aoi_only_job(client):
    job = client.post(
        "/api/v1/process",
        json={
            "analysis_name": "No file expected",
            "scale_factor": 2,
            "aoi": {"north": 1, "south": 0, "east": 1, "west": 0},
        },
    ).json()

    resp = client.get(f"/api/v1/results/{job['job_id']}/file")
    assert resp.status_code == 404


def test_image_file_not_found(client):
    resp = client.get(f"/api/v1/images/{uuid.uuid4()}/file")
    assert resp.status_code == 404

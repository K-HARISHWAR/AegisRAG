"""Unit, integration, and security tests for Phase 14 Feedback Loop & Continuous Evaluation."""

import uuid
from fastapi.testclient import TestClient
import pytest

from tests.conftest import get_auth_header


def test_submit_positive_and_negative_feedback(client: TestClient, seeded_db: dict) -> None:
    """Test user can submit thumbs-up and thumbs-down feedback with tags and metadata."""
    users = {u.email: u for u in seeded_db["users"]}
    alice = users["alice@example.com"]
    headers = get_auth_header(alice.id)

    # 1. Submit Positive Feedback (Thumbs Up)
    pos_resp = client.post(
        "/api/v1/feedback",
        headers=headers,
        json={
            "query_text": "What is the engineering SLA?",
            "answer_text": "The SLA response time for Tier-1 engineering outages is 15 minutes.",
            "rating": "positive",
            "model_version": "mock-llm-v1",
            "prompt_version": "v1.0.0",
            "evidence_level": "strong",
        },
    )
    assert pos_resp.status_code == 201
    pos_data = pos_resp.json()
    assert pos_data["rating"] == "positive"
    assert pos_data["user_email"] == alice.email
    assert pos_data["review_status"] == "not_required"
    assert pos_data["reason_tags"] == []

    # 2. Submit Negative Feedback (Thumbs Down) with Failure Tags
    neg_resp = client.post(
        "/api/v1/feedback",
        headers=headers,
        json={
            "query_text": "What is the cafeteria menu?",
            "answer_text": "The available documentation does not contain sufficient information to answer this question.",
            "rating": "negative",
            "reason_tags": ["incomplete", "irrelevant_retrieval"],
            "comment": "Does not answer my question about lunch.",
            "model_version": "mock-llm-v1",
            "prompt_version": "v1.0.0",
            "evidence_level": "insufficient",
        },
    )
    assert neg_resp.status_code == 201
    neg_data = neg_resp.json()
    assert neg_data["rating"] == "negative"
    assert neg_data["reason_tags"] == ["incomplete", "irrelevant_retrieval"]
    assert neg_data["comment"] == "Does not answer my question about lunch."
    # Auto review task created
    assert neg_data["review_status"] == "pending_review"


def test_feedback_ownership_and_isolation(client: TestClient, seeded_db: dict) -> None:
    """Test standard employee can only see their own feedback, while manager sees department feedback."""
    users = {u.email: u for u in seeded_db["users"]}
    alice = users["alice@example.com"]      # Engineering Employee
    bob = users["bob@example.com"]          # HR Employee
    charlie = users["charlie@example.com"]  # Engineering Manager
    admin = users["admin@example.com"]      # Admin

    # Alice submits feedback
    client.post(
        "/api/v1/feedback",
        headers=get_auth_header(alice.id),
        json={
            "query_text": "Alice question",
            "answer_text": "Alice answer",
            "rating": "positive",
        },
    )

    # Bob submits feedback
    client.post(
        "/api/v1/feedback",
        headers=get_auth_header(bob.id),
        json={
            "query_text": "Bob question",
            "answer_text": "Bob answer",
            "rating": "negative",
            "reason_tags": ["poor_citation"],
        },
    )

    # Alice listing should only return Alice's feedback
    alice_list = client.get("/api/v1/feedback", headers=get_auth_header(alice.id))
    assert alice_list.status_code == 200
    alice_items = alice_list.json()
    assert len(alice_items) == 1
    assert alice_items[0]["user_email"] == alice.email

    # Bob listing should only return Bob's feedback
    bob_list = client.get("/api/v1/feedback", headers=get_auth_header(bob.id))
    assert bob_list.status_code == 200
    bob_items = bob_list.json()
    assert len(bob_items) == 1
    assert bob_items[0]["user_email"] == bob.email

    # Charlie (Engineering Manager) sees Alice's feedback, but NOT Bob's (HR)
    charlie_list = client.get("/api/v1/feedback", headers=get_auth_header(charlie.id))
    assert charlie_list.status_code == 200
    charlie_items = charlie_list.json()
    assert len(charlie_items) == 1
    assert charlie_items[0]["user_email"] == alice.email

    # Admin sees all feedback across all departments
    admin_list = client.get("/api/v1/feedback", headers=get_auth_header(admin.id))
    assert admin_list.status_code == 200
    assert len(admin_list.json()) >= 2


def test_feedback_stats_rbac_and_aggregation(client: TestClient, seeded_db: dict) -> None:
    """Test feedback stats computation and manager/admin RBAC enforcement."""
    users = {u.email: u for u in seeded_db["users"]}
    alice = users["alice@example.com"]
    charlie = users["charlie@example.com"]
    admin = users["admin@example.com"]

    # 1. Standard employee (Alice) is forbidden from viewing stats
    emp_stats = client.get("/api/v1/feedback/stats", headers=get_auth_header(alice.id))
    assert emp_stats.status_code == 403

    # 2. Manager (Charlie) can access stats
    mgr_stats = client.get("/api/v1/feedback/stats", headers=get_auth_header(charlie.id))
    assert mgr_stats.status_code == 200
    data = mgr_stats.json()
    assert "total_feedback" in data
    assert "satisfaction_rate" in data
    assert "failure_categories" in data

    # 3. Admin can access stats
    admin_stats = client.get("/api/v1/feedback/stats", headers=get_auth_header(admin.id))
    assert admin_stats.status_code == 200


def test_human_review_task_workflow(client: TestClient, seeded_db: dict) -> None:
    """Test negative feedback review triage workflow from pending_review to resolved."""
    users = {u.email: u for u in seeded_db["users"]}
    alice = users["alice@example.com"]
    charlie = users["charlie@example.com"]

    # Alice submits negative feedback
    fb_resp = client.post(
        "/api/v1/feedback",
        headers=get_auth_header(alice.id),
        json={
            "query_text": "How do I request admin tokens?",
            "answer_text": "Contact IT admin.",
            "rating": "negative",
            "reason_tags": ["incomplete"],
            "comment": "Procedure lacks ticket link.",
        },
    )
    assert fb_resp.status_code == 201
    feedback_id = fb_resp.json()["id"]

    # 1. Alice cannot triage or update review task
    unauth_update = client.patch(
        f"/api/v1/feedback/{feedback_id}/review",
        headers=get_auth_header(alice.id),
        json={"review_status": "resolved", "reviewer_notes": "Self resolved"},
    )
    assert unauth_update.status_code == 403

    # 2. Charlie (Manager) updates review task to in_review
    in_review_resp = client.patch(
        f"/api/v1/feedback/{feedback_id}/review",
        headers=get_auth_header(charlie.id),
        json={
            "review_status": "in_review",
            "reviewer_notes": "Assigned to Engineering Lead to update runbook documentation.",
        },
    )
    assert in_review_resp.status_code == 200
    data = in_review_resp.json()
    assert data["review_status"] == "in_review"
    assert data["reviewer_email"] == charlie.email
    assert "Engineering Lead" in data["reviewer_notes"]
    assert data["reviewed_at"] is not None

    # 3. Charlie resolves review task
    resolved_resp = client.patch(
        f"/api/v1/feedback/{feedback_id}/review",
        headers=get_auth_header(charlie.id),
        json={
            "review_status": "resolved",
            "reviewer_notes": "Added direct Jira service desk portal link to section 3.2.",
        },
    )
    assert resolved_resp.status_code == 200
    assert resolved_resp.json()["review_status"] == "resolved"


def test_dashboard_handles_empty_data(client: TestClient, seeded_db: dict) -> None:
    """Test stats endpoint handles zero feedback without division-by-zero errors."""
    users = {u.email: u for u in seeded_db["users"]}
    admin = users["admin@example.com"]

    resp = client.get("/api/v1/feedback/stats", headers=get_auth_header(admin.id))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_feedback"] >= 0
    assert data["satisfaction_rate"] >= 0.0

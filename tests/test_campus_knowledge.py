"""
Tests for Campus Spatial Knowledge, Multi-Building Facilities, Fleet Vehicles,
Static Infrastructure, and Campus SOPs in Knowledge Agent.
"""
import pytest
from fastapi.testclient import TestClient

from agents.knowledge_agent.agent import execute_knowledge_query
from agents.knowledge_agent.location_resolver import (
    resolve_location,
    resolve_facility,
    resolve_vehicle,
    resolve_static_object,
    resolve_campus_sku
)
from agents.knowledge_agent.knowledge_store import knowledge_store, seed_warehouse_sops
from agents.knowledge_agent.server import app
from database.connection import init_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_sops():
    """Ensure database and seed SOPs are initialized."""
    init_db()
    seed_warehouse_sops(knowledge_store)


# ==================== 1. Campus Facility Resolution ====================

def test_resolve_cold_vault_facility():
    """Querying Cold Vault or Building 4 returns BLD-04 with cold-chain specs."""
    res = resolve_location("where is the cold vault?")
    assert res["found"] is True
    assert res["entity_type"] == "campus_facility"
    assert res["building_id"] == "BLD-04"
    assert "Building 4" in res["name"]
    assert "2°–4°C" in res["category"]
    assert "320 Chilled Bays" in res["capacity"]


def test_resolve_building_by_number():
    """Querying Building 1 returns High-Bay Hub BLD-01."""
    res = resolve_location("where is building 1?")
    assert res["found"] is True
    assert res["building_id"] == "BLD-01"
    assert "High-Bay Hub" in res["name"]
    assert "2,400 Pallet Bays" in res["capacity"]


def test_resolve_quarantine_yard():
    """Querying Quarantine Yard or Bay 11 returns BLD-05."""
    res = resolve_location("where is quarantine yard?")
    assert res["found"] is True
    assert res["building_id"] == "BLD-05"
    assert "Restricted Access" in res["status"]


def test_resolve_gatehouse_and_scale():
    """Querying Gatehouse returns BLD-07 with 60T scale info."""
    res = resolve_location("where is the gatehouse?")
    assert res["found"] is True
    assert res["building_id"] == "BLD-07"
    assert "60T" in res["capacity"]


def test_resolve_tech_mezzanine():
    """Querying Tech Mezzanine returns cleanroom ESD specs."""
    res = resolve_location("tell me about building 3")
    assert res["found"] is True
    assert res["building_id"] == "BLD-03"
    assert "Cleanroom ESD" in res["category"]


# ==================== 2. Fleet Vehicle Resolution ====================

def test_resolve_forklift_1():
    """Querying Forklift 1 returns FL-01 active at Building 1 dock."""
    res = resolve_location("where is Forklift 1?")
    assert res["found"] is True
    assert res["entity_type"] == "campus_vehicle"
    assert res["vehicle_id"] == "FL-01"
    assert "Building 1" in res["nearest_facility"]
    assert "89%" in res["battery_soc"]


def test_resolve_tugger_agv():
    """Querying AGV returns AGV-01 on autonomous route."""
    res = resolve_location("where is the AGV?")
    assert res["found"] is True
    assert res["vehicle_id"] == "AGV-01"
    assert "Autonomous Navigation" in res["status"]


def test_resolve_reach_truck_charging():
    """Querying Reach Truck 2 or Charger Bay 2 returns RT-02 charging in Building 6."""
    res = resolve_location("where is charger bay 2?")
    assert res["found"] is True
    assert res["vehicle_id"] == "RT-02"
    assert "Building 6" in res["nearest_facility"]
    assert "Charging" in res["status"]


# ==================== 3. Static Infrastructure Resolution ====================

def test_resolve_60t_scale():
    """Querying 60T scale returns OBJ-WGH-01 at Gatehouse."""
    res = resolve_location("where is the 60t scale?")
    assert res["found"] is True
    assert res["entity_type"] == "campus_infrastructure"
    assert res["object_id"] == "OBJ-WGH-01"
    assert "Building 7" in res["building_name"]


def test_resolve_fast_chargers():
    """Querying fast chargers returns Building 6 Fleet Depot chargers."""
    res = resolve_location("where are the fast chargers?")
    assert res["found"] is True
    assert res["object_id"] == "OBJ-CHG-01"
    assert "Building 6" in res["building_name"]


def test_resolve_airlock_port():
    """Querying airlock returns Building 4 Cold Vault airlock."""
    res = resolve_location("where is the airlock?")
    assert res["found"] is True
    assert res["object_id"] == "OBJ-AIR-01"
    assert "Building 4" in res["building_name"]


# ==================== 4. Campus Product Location Mapping ====================

def test_resolve_insulin_location():
    """Querying insulin returns Building 4 Cold Vault storage."""
    res = resolve_location("where is insulin stored?")
    assert res["found"] is True
    assert res["building_id"] == "BLD-04"
    assert "Building 4 — Cold Vault" in res["formatted_message"]
    assert "SKU-5520" in res["sku"]


def test_resolve_lithium_batteries_location():
    """Querying forklift batteries returns Building 5 Quarantine Yard."""
    res = resolve_location("where are lithium batteries kept?")
    assert res["found"] is True
    assert res["building_id"] == "BLD-05"
    assert "Building 5 — Quarantine Yard" in res["formatted_message"]


# ==================== 5. End-to-End Query Execution Engine ====================

def test_execute_query_facility_location():
    """End-to-end query for cold vault via execute_knowledge_query."""
    res = execute_knowledge_query("Where is the Cold Vault located?")
    assert res["agent"] == "knowledge_agent"
    assert res["data"]["found"] is True
    assert res["data"]["building_id"] == "BLD-04"
    assert "Chilled Bays" in res["response"]


def test_execute_query_campus_overview():
    """Asking for campus layout returns all 7 buildings."""
    res = execute_knowledge_query("What buildings are on the campus?")
    assert res["agent"] == "knowledge_agent"
    assert res["data"]["found"] is True
    assert "Colombo Logistics Complex" in res["response"]
    assert "Building 1" in res["response"]
    assert "Building 4" in res["response"]
    assert "Building 7" in res["response"]


def test_execute_query_cold_chain_sop():
    """Retrieving SOP for cold chain temperature excursions."""
    res = execute_knowledge_query("what is the SOP for cold chain temperature excursion?")
    assert res["agent"] == "knowledge_agent"
    assert res["source"] == "vector_rag"
    assert "Cold Storage" in res["response"] or "Cold-Chain Vault" in res["response"] or "Temperature" in res["response"]


def test_execute_query_gatehouse_protocol():
    """Retrieving SOP for gatehouse carrier check-in."""
    res = execute_knowledge_query("what is the carrier check-in procedure at Gate 1?")
    assert res["agent"] == "knowledge_agent"
    assert res["source"] == "vector_rag"
    assert "Weighbridge" in res["response"] or "Gate 1" in res["response"] or "manifest" in res["response"]


# ==================== 6. Campus REST Endpoints ====================

def test_rest_campus_overview():
    """GET /campus/overview returns campus complex and 7 buildings."""
    resp = client.get("/campus/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert len(data["buildings"]) == 7


def test_rest_campus_facilities():
    """GET /campus/facilities returns all buildings."""
    resp = client.get("/campus/facilities")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 7


def test_rest_campus_facility_by_id():
    """GET /campus/facilities/BLD-04 returns Cold Vault specs."""
    resp = client.get("/campus/facilities/BLD-04")
    assert resp.status_code == 200
    data = resp.json()
    assert data["facility"]["id"] == "BLD-04"
    assert "Cold Vault" in data["facility"]["name"]


def test_rest_campus_vehicles():
    """GET /campus/vehicles returns active fleet."""
    resp = client.get("/campus/vehicles")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] >= 5


def test_rest_campus_objects():
    """GET /campus/objects returns static infrastructure."""
    resp = client.get("/campus/objects")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] >= 5

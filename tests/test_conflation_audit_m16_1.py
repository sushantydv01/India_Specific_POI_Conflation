"""Dedicated tests for Milestone 16.1 independent graph conflation audit and canonical validation."""

import json
from pathlib import Path
import duckdb
import pytest


def test_audit_report_and_verdict():
    """Verify independent audit report artifact and formal verdict."""
    audit_json_path = Path("reports/m16_1_conflation_audit.json")
    audit_md_path = Path("reports/m16_1_independent_conflation_audit.md")
    assert audit_json_path.exists(), "Audit JSON report missing"
    assert audit_md_path.exists(), "Audit Markdown report missing"

    with open(audit_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["metadata"]["formal_audit_verdict"] == "AUDIT_PASSED_WITH_CORRECTIONS"
    assert data["source_accounting_audit"]["total_source_records"] == 246856
    assert data["source_accounting_audit"]["accounting_completeness_pct"] == 100.0


def test_source_record_accounting_and_provenance():
    """Verify complete source inventory accounting: 100% of OSM and Overture records accounted for."""
    audit_json_path = Path("reports/m16_1_conflation_audit.json")
    with open(audit_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    inv = data["source_accounting_audit"]
    assert inv["expected_osm_records"] == 49036
    assert inv["accounted_osm_records"] == 49036
    assert inv["unique_osm_records"] == 49036
    assert inv["osm_missing_count"] == 0
    assert inv["osm_duplicate_assignment_count"] == 0

    assert inv["expected_overture_records"] == 197820
    assert inv["accounted_overture_records"] == 197820
    assert inv["unique_overture_records"] == 197820
    assert inv["overture_missing_count"] == 0
    assert inv["overture_duplicate_assignment_count"] == 0

    assert inv["total_canonical_entities"] == 238083
    assert inv["canonical_uuid_collisions"] == 0


def test_singleton_and_ambiguous_entity_decomposition():
    """Verify exact mathematical reconciliation of singletons, ambiguous entities, and equivalences."""
    audit_json_path = Path("reports/m16_1_conflation_audit.json")
    with open(audit_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    res = data["singleton_reconciliation_audit"]["single_source_composition"]
    disambig_single = res["disambiguated_singleton_total"]  # 226825
    unresolved_ambig = res["unresolved_ambiguous_total"]  # 2485
    multi_source_equiv = res["multi_source_equivalence_entities"]  # 8773
    total_canonical = res["sum_canonical_entities"]  # 238083

    # Check sum of resolution statuses
    assert multi_source_equiv + disambig_single + unresolved_ambig == total_canonical
    assert total_canonical == 238083

    # Single-source entities sum to 229,310
    total_single_source = disambig_single + unresolved_ambig
    assert total_single_source == 229310
    assert res["total_single_source_entities"] == 229310

    # Source breakdown
    osm_single = res["total_osm_only_entities"]  # 40263
    ov_single = res["total_overture_only_entities"]  # 189047
    assert osm_single + ov_single == total_single_source
    assert osm_single == 39107 + 1156
    assert ov_single == 187718 + 1329


def test_component_topology_reconciliation():
    """Verify component resolution reconciliation across star, 1:1, and complex topologies."""
    audit_json_path = Path("reports/m16_1_conflation_audit.json")
    with open(audit_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    comp = data["topology_reconciliation_audit"]["component_accounting"]
    one_to_one = comp["total_one_to_one_components"]  # 8662
    one_to_n = comp["total_one_to_many_stars"]  # 219
    n_to_one = comp["total_many_to_one_stars"]  # 101
    n_to_m = comp["total_many_to_many_components"]  # 13
    ambig_clust = comp["total_ambiguous_clusters"]  # 537

    # Equivalences resolved from components
    equiv_1to1 = comp["resolved_one_to_one_equivalences"]  # 8662
    equiv_1toN = comp["resolved_one_to_many_dominant_winners"]  # 69
    equiv_Nto1 = comp["resolved_many_to_one_dominant_winners"]  # 42
    assert equiv_1to1 + equiv_1toN + equiv_Nto1 == 8773

    # Ambiguous singletons resolved from components
    ambig_1toN = comp["ambiguous_one_to_many_constituent_entities"]  # 456
    ambig_Nto1 = comp["ambiguous_many_to_one_constituent_entities"]  # 179
    ambig_NtoM = comp["ambiguous_many_to_many_constituent_entities"]  # 53
    ambig_clust_pois = comp["ambiguous_clusters_constituent_entities"]  # 1797
    assert ambig_1toN + ambig_Nto1 + ambig_NtoM + ambig_clust_pois == 2485


def test_atm_relationship_accounting_and_zero_merges():
    """Verify ATM relationship accounting (362 relationships, 3 rejected edges, 0 bank-ATM merges)."""
    audit_json_path = Path("reports/m16_1_conflation_audit.json")
    with open(audit_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["atm_facility_audit"]["atm_edges_intercepted"] == 365
    assert data["atm_facility_audit"]["facility_atm_relationships_exported"] == 362
    assert data["atm_facility_audit"]["rejected_atm_edges_count"] == 3
    assert data["atm_facility_audit"]["prohibited_atm_bank_merges_in_canonical_equivalence"] == 0

    con = duckdb.connect()

    # Verify 362 FACILITY_ATM relationships in poi_relationships.parquet
    rel_count = con.execute("""
        SELECT count(*) FROM 'data/processed/canonical/poi_relationships.parquet'
        WHERE relationship_type = 'FACILITY_ATM'
    """).fetchone()[0]
    assert rel_count == 362

    # Verify 0 cross-entity ATM-to-bank merges in canonical_pois.parquet
    import re
    rows = con.execute("""
        SELECT source_names
        FROM 'data/processed/canonical/canonical_pois.parquet'
        WHERE resolution_decision = 'RESOLVED_EQUIVALENCE'
    """).fetchall()

    atm_pattern = re.compile(r"\\b(atm|cdm|automated teller machine|cash point)\\b", re.IGNORECASE)
    bank_pattern = re.compile(r"\\b(bank|branch)\\b", re.IGNORECASE)

    atm_bank_cross_merges = 0
    for (sn_json,) in rows:
        sn = json.loads(sn_json)
        osm_names = sn.get("OSM", [])
        ov_names = sn.get("OVERTURE", [])

        osm_has_atm = any(atm_pattern.search(n) for n in osm_names)
        ov_has_atm = any(atm_pattern.search(n) for n in ov_names)

        # Cross merge: one side has ATM, the other side is a bank branch without ATM
        if osm_has_atm and not ov_has_atm and any(bank_pattern.search(n) for n in ov_names):
            atm_bank_cross_merges += 1
        elif ov_has_atm and not osm_has_atm and any(bank_pattern.search(n) for n in osm_names):
            atm_bank_cross_merges += 1

    assert atm_bank_cross_merges == 0


def test_parent_child_container_relationships():
    """Verify container relationship counts: 420 PARENT_CHILD, 203 CAMPUS_FACILITY, 0 merged."""
    con = duckdb.connect()

    rel_counts = dict(con.execute("""
        SELECT relationship_type, count(*)
        FROM 'data/processed/canonical/poi_relationships.parquet'
        WHERE relationship_type IN ('PARENT_CHILD', 'CAMPUS_FACILITY')
        GROUP BY relationship_type
    """).fetchall())

    assert rel_counts.get("PARENT_CHILD", 0) == 420
    assert rel_counts.get("CAMPUS_FACILITY", 0) == 203
    assert rel_counts["PARENT_CHILD"] + rel_counts["CAMPUS_FACILITY"] == 623


def test_mutually_exclusive_edge_dispositions():
    """Verify that the 4 mutually exclusive edge dispositions sum to exactly 605,428."""
    audit_json_path = Path("reports/m16_1_conflation_audit.json")
    with open(audit_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    disp = data["edge_disposition_audit"]["mutually_exclusive_dispositions"]
    acc = disp["ACCEPTED_EQUIVALENCE"]
    par = disp["PARENT_CHILD"]
    rev = disp["REVIEW"]
    rej = disp["REJECTED"]

    assert acc == 10659
    assert par == 985
    assert rev == 956
    assert rej == 592828
    assert acc + par + rev + rej == 605428


def test_canonical_export_integrity():
    """Verify physical integrity of canonical Parquet and GeoJSON exports."""
    con = duckdb.connect()

    total_rows = con.execute("SELECT count(*) FROM 'data/processed/canonical/canonical_pois.parquet'").fetchone()[0]
    assert total_rows == 238083

    # Check BBMP bounds
    bounds = con.execute("""
        SELECT min(latitude), max(latitude), min(longitude), max(longitude)
        FROM 'data/processed/canonical/canonical_pois.parquet'
    """).fetchone()

    assert bounds[0] >= 12.8
    assert bounds[1] <= 13.2
    assert bounds[2] >= 77.4
    assert bounds[3] <= 77.8

    # Check nulls
    null_ids = con.execute("""
        SELECT count(*) FROM 'data/processed/canonical/canonical_pois.parquet'
        WHERE canonical_entity_id IS NULL OR primary_name IS NULL
    """).fetchone()[0]
    assert null_ids == 0

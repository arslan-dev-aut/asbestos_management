"""Unit tests for bulk import parsing helpers (no DB / network)."""

from backend.domains.bulk import bulk_service


def test_condition_parsing_value_and_label():
    assert bulk_service._parse_condition("GOOD") == "GOOD"
    assert bulk_service._parse_condition("Low Damage") == "LOW_DAMAGE"
    assert bulk_service._parse_condition("medium damage") == "MEDIUM_DAMAGE"
    assert bulk_service._parse_condition("not a thing") is None


def test_risk_parsing_value_and_label():
    assert bulk_service._parse_risk("HIGH") == "HIGH"
    assert bulk_service._parse_risk("Low") == "LOW"
    assert bulk_service._parse_risk("bogus") is None


def test_template_generation_csv_and_xlsx():
    csv_bytes, csv_mime, csv_name = bulk_service.generate_template("csv")
    assert b"Customer" in csv_bytes and csv_name.endswith(".csv")
    assert csv_mime == "text/csv"

    xlsx_bytes, xlsx_mime, xlsx_name = bulk_service.generate_template("xlsx")
    assert xlsx_name.endswith(".xlsx")
    assert xlsx_bytes[:2] == b"PK"  # zip/xlsx magic


def test_read_rows_csv():
    csv = (
        "Customer,Site Name,Building,Room/Location,Asset,ACM Type,Condition,Risk Score,Notes\n"
        "Acme,Site A,Boiler House,Boiler Room,,Pipe Lagging,Good,High,note one\n"
    )
    rows = bulk_service._read_rows("data.csv", csv.encode("utf-8"))
    assert len(rows) == 1
    assert rows[0]["Customer"] == "Acme"
    assert rows[0]["Risk Score"] == "High"


def test_read_rows_rejects_unknown_extension():
    import pytest

    from backend.database.exceptions import ValidationError

    with pytest.raises(ValidationError):
        bulk_service._read_rows("data.txt", b"nope")


def test_export_builder_columns():
    content, mime, name = bulk_service.build_export([["Acme", "Site A"] + [""] * 9], "csv")
    assert b"Customer" in content and b"Site A" in content
    assert name.endswith(".csv")

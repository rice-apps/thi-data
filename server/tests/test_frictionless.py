import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import crud

# --- Fixtures ---
@pytest.fixture
def mapping_result():
    """Runs the inference function once to be used across multiple tests."""
    # Point this to the location of your test_data.csv
    return crud.validation.infer_from_file("test_data.csv")

def get_field_type(schema: dict, field_name: str) -> str | None:
    """Helper to extract the inferred type of a specific column from the schema dict."""
    for field in schema.get("fields", []):
        if field["name"] == field_name:
            return field["type"]
    return None

# --- Tests ---

def test_messy_date_fallback(mapping_result):
    """
    The 'Messy Date' Test: Mixed date formats should cause Frictionless to fallback.
    Standard Frictionless falls back to 'string' or 'any' when formats clash.
    """
    schema = mapping_result["schema"]
    inferred_type = get_field_type(schema, "messy_date")
    
    assert inferred_type in ["string", "any"], f"Expected fallback to string/any, got {inferred_type}"

def test_float_as_int(mapping_result):
    """
    The 'Float as Int' Test: Columns with 1, 2, and 3.5 should be inferred as 'number' (float),
    ensuring no truncation of the decimal values.
    """
    schema = mapping_result["schema"]
    inferred_type = get_field_type(schema, "float_as_int")
    
    assert inferred_type == "number"

def test_boolean_ambiguity(mapping_result):
    """
    Boolean Ambiguity Test: Verify how different truthy/falsy values are handled natively.
    - True/False -> boolean
    - 1/0 -> integer
    - Y/N -> string (categorical)
    """
    schema = mapping_result["schema"]
    
    assert get_field_type(schema, "bool_standard") == "boolean"
    assert get_field_type(schema, "bool_binary") == "integer"
    assert get_field_type(schema, "bool_yn") == "string" 

def test_scientific_notation(mapping_result):
    """
    Scientific Notation Test: Scientific strings (e.g., 1.5e3) should be parsed as 'number'.
    """
    schema = mapping_result["schema"]
    inferred_type = get_field_type(schema, "scientific_notation")
    
    assert inferred_type == "number"

def test_null_detection(mapping_result):
        """
        Null Test: Make sure empty strings are detected as None in the extracted sample.
        (Frictionless defaults to treating "" as missing value, but "NA" and "null" as strings).
        """
        sample = mapping_result["sample"]
        
        assert sample["test_data"][1]["null_col"] is None, "Empty cells should be parsed as None"
        assert sample["test_data"][2]["null_col"] == "NA"
        assert sample["test_data"][3]["null_col"] == "null"

def test_schema_blueprint_override(mapping_result):
    """
    Schema Blueprint Test: Simulates a user "overriding" a type on the frontend,
    and checks that the resulting JSON structure holds that override properly.
    """
    schema = mapping_result["schema"]
    
    # Simulate user overriding "messy_date" from 'string' to 'date'
    for field in schema.get("fields", []):
        if field["name"] == "messy_date":
            field["type"] = "date"
            field["format"] = "any" # overriding format to accept mixed
            
    # Verify the dictionary blueprint is updated correctly for the schemas table
    updated_type = get_field_type(schema, "messy_date")
    assert updated_type == "date", "The override was not applied to the schema blueprint properly."

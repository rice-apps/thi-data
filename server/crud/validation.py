from frictionless import extract, describe

def infer_from_file(object_key: str): 
    # hardcoded, need to change!!
    file_path = "tests/test_validation_data/patient_data.csv" 
    rows = extract(file_path)
    resource = describe(file_path)
    return {
        "schema": resource.schema, 
        "sample": rows, 
    }

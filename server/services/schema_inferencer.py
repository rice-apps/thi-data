from frictionless import extract, describe

def infer_from_file(file_path: str):
    rows = extract(file_path)
    resource = describe(file_path)
    return {
        "schema": resource.schema.to_dict(),
        "sample": rows
    }

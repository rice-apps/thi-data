import sys 
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
server_dir = os.path.dirname(current_dir)
sys.path.insert(0, server_dir)

import crud

file_path = 'tests/test_validation_data/patient_data.csv'
try: 
    sampled = crud.sample_file(file_path)
    for key in sampled: 
        print(sampled[key])
        print()
except Exception as e: 
    print("An exception occurred: ", e)
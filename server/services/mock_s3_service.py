from .storage_interface import StorageService
from pathlib import Path

def MockS3Service(StorageService):

    def __init__(self, test_files_dir="tests/test_validation_data"): 
        self.base_path = Path(test_files_dir)
    
    def get_file_path(self, object_key: str): 
        file_path = self.base_path / object_key 
        if file_path.exists(): 
            return file_path 
        raise Exception("File path does not exist!") 
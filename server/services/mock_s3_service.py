from pathlib import Path
from .storage_service import StorageService

class MockS3Service(StorageService):

    def __init__(self, test_files_dir="tests/test_validation_data"): 
        self.base_path = Path.cwd() / test_files_dir
    
    def get_file_path(self, object_key: str): 
        file_path = self.base_path / object_key 
        if file_path.exists(): 
            return file_path 
        return None # Return None when file_path does not exist 
    
    
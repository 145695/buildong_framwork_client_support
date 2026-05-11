"""
Test cache path resolution
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def test_cache_path():
    """Test cache path resolution"""
    print("Testing cache path resolution...")
    
    # Test path from intelligent_rag_system.py
    cache_dir = Path(__file__).parent / "vector_cache"
    print(f"Cache dir from RAG system: {cache_dir}")
    print(f"Cache dir exists: {cache_dir.exists()}")
    
    # Test absolute path
    abs_path = cache_dir.resolve()
    print(f"Absolute cache path: {abs_path}")
    print(f"Absolute path exists: {abs_path.exists()}")
    
    # List files in cache
    if cache_dir.exists():
        files = list(cache_dir.glob("*"))
        print(f"Files in cache: {[f.name for f in files]}")
    
    print("=" * 50)

if __name__ == "__main__":
    test_cache_path()

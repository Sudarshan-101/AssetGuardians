"""FAISS index management for vector similarity search."""
import os
import pickle

class FAISSManager:
    """Manager for FAISS indexing operations."""
    
    def __init__(self, index_path=None):
        self.index = None
        self.index_path = index_path or os.getenv('FAISS_INDEX_PATH', '/app/faiss_index/index')
        self.id_map = {}  # Maps FAISS internal IDs to asset IDs
        self._load_index()
    
    def _load_index(self):
        """Load existing index from disk if available."""
        try:
            if os.path.exists(f"{self.index_path}.faiss"):
                import faiss
                self.index = faiss.read_index(f"{self.index_path}.faiss")
            
            if os.path.exists(f"{self.index_path}_map.pkl"):
                with open(f"{self.index_path}_map.pkl", 'rb') as f:
                    self.id_map = pickle.load(f)
        except Exception as e:
            print(f"Warning: Could not load FAISS index: {e}")
            self.index = None
            self.id_map = {}
    
    def _save_index(self):
        """Save index to disk."""
        try:
            if self.index is not None:
                import faiss
                os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
                faiss.write_index(self.index, f"{self.index_path}.faiss")
            
            with open(f"{self.index_path}_map.pkl", 'wb') as f:
                pickle.dump(self.id_map, f)
        except Exception as e:
            print(f"Error saving FAISS index: {e}")
    
    def add(self, vector, asset_id=None):
        """Add a vector to the index and return its ID."""
        try:
            import faiss
            import numpy as np
            
            if isinstance(vector, list):
                vector = np.array(vector, dtype=np.float32)
            
            if vector.ndim == 1:
                vector = vector.reshape(1, -1)
            
            if self.index is None:
                dimension = vector.shape[1]
                self.index = faiss.IndexFlatL2(dimension)
            
            faiss_id = self.index.ntotal
            self.index.add(vector.astype(np.float32))
            
            if asset_id is not None:
                self.id_map[faiss_id] = asset_id
            
            self._save_index()
            return faiss_id
        except Exception as e:
            print(f"Error adding to FAISS index: {e}")
            return None
    
    def build_index(self, vectors):
        """Build FAISS index from vectors."""
        try:
            import faiss
            import numpy as np
            
            vectors_array = np.array(vectors, dtype=np.float32)
            dimension = vectors_array.shape[1]
            self.index = faiss.IndexFlatL2(dimension)
            self.index.add(vectors_array)
            self._save_index()
            return True
        except Exception as e:
            print(f"Error building FAISS index: {e}")
            return False
    
    def search(self, query_vector, k=5):
        """Search for k nearest neighbors."""
        if self.index is None:
            return []
        
        try:
            import numpy as np
            
            if isinstance(query_vector, list):
                query_vector = np.array(query_vector, dtype=np.float32)
            
            if query_vector.ndim == 1:
                query_vector = query_vector.reshape(1, -1)
            
            distances, indices = self.index.search(query_vector.astype(np.float32), min(k, self.index.ntotal))
            
            results = []
            for idx in indices[0]:
                if idx >= 0 and idx in self.id_map:
                    results.append(self.id_map[idx])
            
            return results
        except Exception as e:
            print(f"Error searching FAISS index: {e}")
            return []
    
    def stats(self):
        """Get index statistics."""
        if self.index is None:
            return {"status": "not_initialized", "size": 0}
        
        try:
            return {
                "status": "ready",
                "size": self.index.ntotal,
                "dimension": self.index.d if hasattr(self.index, 'd') else None
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}


# Global instance
faiss_manager = FAISSManager()

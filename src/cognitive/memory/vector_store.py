"""
Vector Store - Long-term Memory System

ChromaDB-powered vector storage for Jarvis-like memory:
- Remembers conversations, projects, code patterns
- Enables semantic search across all memories
- Supports multiple collections (conversations, projects, code, bugs)

Boss, ab Aether ko sab yaad rahega!
"""

import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
import chromadb
from chromadb.utils import embedding_functions
import json
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class VectorStore:
    """
    Long-term memory using ChromaDB vector database
    
    Collections:
    - conversations: Chat history with embeddings
    - projects: Bug bounty projects, coding projects
    - code_patterns: Coding style, preferences, snippets
    - vulnerabilities: Found bugs, exploitation techniques
    """
    
    def __init__(
        self,
        persist_directory: Optional[str] = None,
        embedding_model: str = "all-MiniLM-L6-v2"
    ):
        """
        Initialize vector store
        
        Args:
            persist_directory: Where to store the database (default: data/memory/chroma)
            embedding_model: Sentence transformer model for embeddings
        """
        if persist_directory is None:
            persist_directory = str(Path("data/memory/chroma").absolute())
        
        os.makedirs(persist_directory, exist_ok=True)
        
        self.client = chromadb.PersistentClient(path=str(persist_directory))

        self.embedding_function = self._build_embedding_function(embedding_model)
        
        self.collections = {}
        self._initialize_collections()
        
        logger.info(f"VectorStore initialized - Memory path: {persist_directory}")

    @staticmethod
    def _build_embedding_function(embedding_model: str):
        """Pick the best embedding backend available in this environment.

        ``sentence-transformers`` (PyTorch, ~2 GB) is perfect on a desktop but far
        too heavy for a small container, so we fall back to Chroma's bundled ONNX
        MiniLM model and finally to Chroma's default hashing embeddings.
        """
        try:
            return embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=embedding_model
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"sentence-transformers unavailable ({exc}); "
                "falling back to the lightweight ONNX embedding model"
            )

        try:
            return embedding_functions.ONNXMiniLM_L6_V2()
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"ONNX embeddings unavailable ({exc}); using hash embeddings")

        return embedding_functions.DefaultEmbeddingFunction()

    
    def _initialize_collections(self):
        """Initialize default collections"""
        default_collections = [
            "conversations", "projects", "code_patterns", 
            "vulnerabilities", "personal_facts"
        ]
        for name in default_collections:
            self.get_or_create_collection(name)
    
    def get_or_create_collection(self, name: str, description: Optional[str] = None):
        """Get or create a collection by name"""
        if name in self.collections:
            return self.collections[name]
        
        try:
            self.collections[name] = self.client.get_or_create_collection(
                name=name,
                embedding_function=self.embedding_function,
                metadata={"description": description or f"Memory collection: {name}"}
            )
            return self.collections[name]
        except Exception as e:
            logger.error(f"Failed to get/create collection '{name}': {e}")
            raise
    
    def add_memory(
        self,
        collection_name: str,
        text: str,
        metadata: Optional[Dict] = None,
        memory_id: Optional[str] = None
    ) -> str:
        """
        Generic method to add memory to any collection
        """
        timestamp = datetime.now().isoformat()
        
        meta = {
            "timestamp": timestamp,
            **(metadata or {})
        }
        
        if not memory_id:
            memory_id = f"mem_{timestamp.replace(':', '-').replace('.', '-')}"
            
        collection = self.get_or_create_collection(collection_name)
        collection.add(
            documents=[text],
            metadatas=[meta],
            ids=[memory_id]
        )
        
        return memory_id

    def add_memories(
        self,
        collection_name: str,
        texts: List[str],
        metadatas: Optional[List[Dict]] = None,
        ids: Optional[List[str]] = None
    ) -> List[str]:
        """
        Add multiple memories in batch
        """
        if not ids:
            timestamp = datetime.now().isoformat().replace(':', '-').replace('.', '-')
            ids = [f"mem_{timestamp}_{i}" for i in range(len(texts))]
            
        if not metadatas:
            metadatas = [{"timestamp": datetime.now().isoformat()} for _ in texts]
            
        collection = self.get_or_create_collection(collection_name)
        collection.add(
            documents=texts,
            metadatas=metadatas,
            ids=ids
        )
        
        return ids

    def add_memories_batch(self, *args, **kwargs):
        """Alias for add_memories to match some test expectations"""
        return self.add_memories(*args, **kwargs)
    
    def add_conversation(
        self,
        user_message: str,
        ai_response: str,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Store conversation in memory
        
        Args:
            user_message: What user said
            ai_response: What AI responded
            metadata: Additional context (timestamp, session_id, etc.)
            
        Returns:
            Memory ID
        """
        timestamp = datetime.now().isoformat()
        
        combined_text = f"User: {user_message}\nAether: {ai_response}"
        
        meta = {
            "timestamp": timestamp,
            "user_message": user_message,
            "ai_response": ai_response,
            **(metadata or {})
        }
        
        memory_id = f"conv_{timestamp.replace(':', '-').replace('.', '-')}"
        
        self.collections["conversations"].add(
            documents=[combined_text],
            metadatas=[meta],
            ids=[memory_id]
        )
        
        logger.info(f"Conversation stored: {memory_id}")
        return memory_id
    
    def add_project(
        self,
        project_name: str,
        project_type: str,
        description: str,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Store project information
        
        Args:
            project_name: Name of project
            project_type: "bug_bounty", "coding", "research", etc.
            description: Project details
            metadata: Additional data (stack, findings, etc.)
            
        Returns:
            Memory ID
        """
        timestamp = datetime.now().isoformat()
        
        meta = {
            "timestamp": timestamp,
            "project_name": project_name,
            "project_type": project_type,
            **(metadata or {})
        }
        
        memory_id = f"proj_{project_name.lower().replace(' ', '_')}_{timestamp[:10]}"
        
        self.collections["projects"].add(
            documents=[description],
            metadatas=[meta],
            ids=[memory_id]
        )
        
        logger.info(f"Project stored: {project_name}")
        return memory_id
    
    def add_code_pattern(
        self,
        pattern_name: str,
        code_snippet: str,
        language: str,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Store coding pattern/preference
        
        Args:
            pattern_name: Name/description of pattern
            code_snippet: The code itself
            language: Programming language
            metadata: Additional context
            
        Returns:
            Memory ID
        """
        timestamp = datetime.now().isoformat()
        
        meta = {
            "timestamp": timestamp,
            "pattern_name": pattern_name,
            "language": language,
            **(metadata or {})
        }
        
        memory_id = f"code_{pattern_name.lower().replace(' ', '_')}_{timestamp[:10]}"
        
        self.collections["code_patterns"].add(
            documents=[f"{pattern_name}\n\n{code_snippet}"],
            metadatas=[meta],
            ids=[memory_id]
        )
        
        logger.info(f"Code pattern stored: {pattern_name}")
        return memory_id
    
    def add_vulnerability(
        self,
        vuln_type: str,
        target: str,
        description: str,
        exploitation_technique: str,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Store vulnerability finding
        
        Args:
            vuln_type: Type of vulnerability (IDOR, XSS, SQLi, etc.)
            target: Target domain/application
            description: Detailed description
            exploitation_technique: How it was exploited
            metadata: Additional data (severity, payout, etc.)
            
        Returns:
            Memory ID
        """
        timestamp = datetime.now().isoformat()
        
        meta = {
            "timestamp": timestamp,
            "vuln_type": vuln_type,
            "target": target,
            "exploitation_technique": exploitation_technique,
            **(metadata or {})
        }
        
        memory_id = f"vuln_{vuln_type.lower()}_{target.replace('.', '_')}_{timestamp[:10]}"
        
        full_text = f"""
Vulnerability: {vuln_type}
Target: {target}
Description: {description}
Exploitation: {exploitation_technique}
"""
        
        self.collections["vulnerabilities"].add(
            documents=[full_text],
            metadatas=[meta],
            ids=[memory_id]
        )
        
        logger.info(f"Vulnerability stored: {vuln_type} on {target}")
        return memory_id
    
    def add_personal_fact(
        self,
        fact_type: str,
        fact_content: str,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Store personal fact about user
        
        Args:
            fact_type: "preference", "habit", "skill", "goal", etc.
            fact_content: The actual fact
            metadata: Additional context
            
        Returns:
            Memory ID
        """
        timestamp = datetime.now().isoformat()
        
        meta = {
            "timestamp": timestamp,
            "fact_type": fact_type,
            **(metadata or {})
        }
        
        memory_id = f"fact_{fact_type}_{timestamp[:10]}"
        
        self.collections["personal_facts"].add(
            documents=[fact_content],
            metadatas=[meta],
            ids=[memory_id]
        )
        
        logger.info(f"Personal fact stored: {fact_type}")
        return memory_id
    
    def search_memories(
        self,
        collection_name: str,
        query: Optional[str] = None,
        n_results: int = 5,
        where: Optional[Dict] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Search memories using semantic similarity
        
        Args:
            collection_name: Which collection to search
            query: Search query
            n_results: Number of results to return
            where: Metadata filter
            **kwargs: Support for 'query_text' and other aliases
            
        Returns:
            Dict containing memories, ids, and metadata
        """
        # Handle aliases for query
        search_query = query or kwargs.get('query_text') or kwargs.get('query_texts')
        if isinstance(search_query, list) and search_query:
            search_query = search_query[0]
            
        if not search_query:
            logger.warning("Search query is empty")
            return {"memories": [], "ids": [], "metadatas": [], "count": 0}

        if collection_name not in self.collections:
            self.get_or_create_collection(collection_name)
        
        try:
            results = self.collections[collection_name].query(
                query_texts=[search_query],
                n_results=n_results,
                where=where
            )
            
            # Format results for consistent API
            memories = []
            for i in range(len(results['ids'][0])):
                memories.append({
                    "id": results['ids'][0][i],
                    "text": results['documents'][0][i],
                    "content": results['documents'][0][i], # support both
                    "metadata": results['metadatas'][0][i],
                    "distance": results['distances'][0][i] if 'distances' in results else None
                })
            
            logger.info(f"Found {len(memories)} memories in '{collection_name}' for query: {search_query[:50]}")
            
            # Return full structure for tests/document_rag
            return {
                "memories": memories,
                "ids": results['ids'][0],
                "documents": results['documents'][0],
                "metadatas": results['metadatas'][0],
                "count": len(memories)
            }
        
        except Exception as e:
            logger.error(f"Search failed in '{collection_name}': {e}")
            return {"memories": [], "ids": [], "metadatas": [], "count": 0}

    def get_memory(self, collection_name: str, memory_id: str) -> Optional[Dict]:
        """Retrieve a specific memory by ID"""
        try:
            collection = self.get_or_create_collection(collection_name)
            result = collection.get(ids=[memory_id])
            
            if not result['ids']:
                return None
                
            return {
                "id": result['ids'][0],
                "text": result['documents'][0],
                "content": result['documents'][0],
                "metadata": result['metadatas'][0]
            }
        except Exception as e:
            logger.error(f"Failed to get memory {memory_id}: {e}")
            return None

    def update_memory(self, collection_name: str, memory_id: str, text: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        """Update an existing memory"""
        collection = self.get_or_create_collection(collection_name)
        
        update_data = {}
        if text:
            update_data["documents"] = [text]
        if metadata:
            update_data["metadatas"] = [metadata]
            
        if not update_data:
            return False
            
        try:
            collection.update(ids=[memory_id], **update_data)
            return True
        except Exception as e:
            logger.error(f"Failed to update memory: {e}")
            return False

    def delete_memory(self, collection_name: str, memory_id: str) -> bool:
        """Delete a memory by ID"""
        try:
            collection = self.get_or_create_collection(collection_name)
            collection.delete(ids=[memory_id])
            return True
        except Exception as e:
            logger.error(f"Failed to delete memory: {e}")
            return False

    def delete_collection(self, name: str) -> bool:
        """Delete an entire collection"""
        try:
            self.client.delete_collection(name)
            if name in self.collections:
                del self.collections[name]
            return True
        except Exception as e:
            logger.error(f"Failed to delete collection {name}: {e}")
            return False

    def list_collections(self) -> List[str]:
        """List all collection names"""
        try:
            collections = self.client.list_collections()
            return [c.name for c in collections]
        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            return []

    def get_collection_stats(self, name: str) -> Dict[str, Any]:
        """Get statistics for a collection"""
        try:
            collection = self.get_or_create_collection(name)
            count = collection.count()
            return {
                "name": name,
                "count": count,
                "metadata": collection.metadata
            }
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {"name": name, "count": 0, "error": str(e)}
    
    def search_all_collections(
        self,
        query: str,
        n_results: int = 3
    ) -> Dict[str, List[Dict]]:
        """
        Search across all collections
        
        Args:
            query: Search query
            n_results: Results per collection
            
        Returns:
            Dict of collection_name -> memories
        """
        all_results = {}
        
        for collection_name in self.collections.keys():
            results = self.search_memories(query, collection_name, n_results)
            if results:
                all_results[collection_name] = results
        
        return all_results
    
    def get_recent_memories(
        self,
        collection_name: str = "conversations",
        n_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get most recent memories from a collection
        
        Args:
            collection_name: Which collection
            n_results: Number of results
            
        Returns:
            List of recent memories (sorted by timestamp)
        """
        try:
            collection = self.collections[collection_name]
            
            all_data = collection.get()
            
            if not all_data['ids']:
                return []
            
            memories = []
            for i in range(len(all_data['ids'])):
                memories.append({
                    "id": all_data['ids'][i],
                    "content": all_data['documents'][i],
                    "metadata": all_data['metadatas'][i]
                })
            
            memories.sort(
                key=lambda x: x['metadata'].get('timestamp', ''),
                reverse=True
            )
            
            return memories[:n_results]
        
        except Exception as e:
            logger.error(f"Failed to get recent memories: {e}")
            return []
    
    def get_stats(self) -> Dict[str, int]:
        """Get memory statistics"""
        stats = {}
        
        for name, collection in self.collections.items():
            try:
                count = collection.count()
                stats[name] = count
            except:
                stats[name] = 0
        
        return stats
    
    
    def persist(self):
        """Persist all changes to disk"""
        try:
            self.client.persist()
            logger.info("Vector store persisted to disk")
        except Exception as e:
            logger.error(f"Failed to persist: {e}")


_vector_store_instance = None

def get_vector_store() -> VectorStore:
    """Get global vector store instance"""
    global _vector_store_instance
    
    if _vector_store_instance is None:
        _vector_store_instance = VectorStore()
    
    return _vector_store_instance




logger.info("Vector Store module loaded - Long-term memory ready!")

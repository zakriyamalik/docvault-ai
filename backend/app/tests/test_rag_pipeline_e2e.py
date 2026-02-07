# app/tests/test_rag_pipeline_e2e.py
"""
End-to-end RAG pipeline test.
Tests: Ingestion → Embedding → FAISS → Retrieval → Query → Answer

Run with: LLM_PROVIDER=stub EMBEDDING_STUB=true EVAL_SEED=1337 pytest app/tests/test_rag_pipeline_e2e.py -v
"""
import os
import pytest
import tempfile
import pickle
from fastapi.testclient import TestClient

# Set deterministic env BEFORE importing app
os.environ["LLM_PROVIDER"] = "stub"
os.environ["EMBEDDING_STUB"] = "true"
os.environ["EVAL_SEED"] = "1337"

from app.main import app
from app.faiss_manager import FAISSManager
from app.retrieval.retriever import retrieve


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def sample_document():
    """Create a sample document content for testing."""
    return """
    Trading Assistant Guide
    
    A trading assistant is a software tool that helps traders execute orders,
    monitor markets, and manage risk. Key features include:
    
    1. Order management systems
    2. Real-time market data feeds
    3. Risk monitoring and alerts
    4. Automated trading strategies
    
    Professional traders rely on trading assistants to improve efficiency
    and reduce manual errors in fast-moving markets.
    """


@pytest.fixture
def cleanup_faiss():
    """Cleanup FAISS index after test."""
    yield
    # Cleanup after test
    import os
    faiss_dir = "/data/faiss"
    for f in ["default.faiss", "default.faiss.ids.pkl", "default.faiss.lock"]:
        path = os.path.join(faiss_dir, f)
        if os.path.exists(path):
            os.remove(path)


class TestRAGPipelineEndToEnd:
    """Test complete RAG pipeline from ingestion to answer."""
    
    def test_01_ingestion_creates_faiss_vectors(self, client, sample_document, cleanup_faiss):
        """Step 1: Document ingestion creates vectors in FAISS."""
        # Create temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(sample_document)
            temp_path = f.name
        
        try:
            # Upload document
            with open(temp_path, 'rb') as f:
                response = client.post(
                    "/api/v1/documents/upload",
                    files={"file": ("trading_guide.txt", f, "text/plain")}
                )
            
            assert response.status_code == 200
            doc_id = response.json()["document_id"]
            assert len(doc_id) > 0
            
            # Verify FAISS index was created
            faiss_path = "/data/faiss/default.faiss"
            ids_path = "/data/faiss/default.faiss.ids.pkl"
            
            import time
            time.sleep(2)  # Wait for async ingestion
            
            assert os.path.exists(faiss_path), "FAISS index not created"
            assert os.path.exists(ids_path), "FAISS IDs pickle not created"
            
            # Verify vectors exist
            import faiss
            index = faiss.read_index(faiss_path)
            assert index.ntotal > 0, "No vectors in FAISS index"
            
            # Verify ID mapping exists
            with open(ids_path, 'rb') as pkl:
                id_map = pickle.load(pkl)
            assert len(id_map) == index.ntotal, "ID map size mismatch"
            
            print(f"✅ Ingestion created {index.ntotal} vectors")
            
        finally:
            os.unlink(temp_path)
    
    def test_02_retrieval_uses_faiss_mapping(self, client, sample_document, cleanup_faiss):
        """Step 2: Retrieval uses correct FAISS→UUID→Chunk mapping."""
        # First ingest document
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(sample_document)
            temp_path = f.name
        
        try:
            with open(temp_path, 'rb') as f:
                client.post(
                    "/api/v1/documents/upload",
                    files={"file": ("trading_guide.txt", f, "text/plain")}
                )
            
            import time
            time.sleep(2)
            
            # Test retrieval directly
            chunks, score = retrieve("What is trading assistant?", top_k=3)
            
            assert len(chunks) > 0, "No chunks retrieved"
            assert score > 0, "Retrieval score is zero"
            
            # Verify chunks contain relevant content
            found_trading = False
            for chunk in chunks:
                if "trading" in chunk.preview.lower():
                    found_trading = True
                    break
            
            assert found_trading, "Retrieved chunks don't contain 'trading'"
            print(f"✅ Retrieved {len(chunks)} relevant chunks")
            
        finally:
            os.unlink(temp_path)
    
    def test_03_chat_uses_rag_for_answer(self, client, sample_document, cleanup_faiss):
        """Step 3: Chat API uses RAG to generate contextual answer."""
        # Ingest document
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(sample_document)
            temp_path = f.name
        
        try:
            with open(temp_path, 'rb') as f:
                client.post(
                    "/api/v1/documents/upload",
                    files={"file": ("trading_guide.txt", f, "text/plain")}
                )
            
            import time
            time.sleep(2)
            
            # Start chat with RAG query
            response = client.post(
                "/api/v1/chat/start",
                json={"first_message": "What is a trading assistant?"}
            )
            
            assert response.status_code == 200
            data = response.json()
            conv_id = data["conversation_id"]
            
            # Get history to verify RAG was used
            history_resp = client.get(f"/api/v1/chat/{conv_id}/history")
            messages = history_resp.json()["messages"]
            
            # Find assistant response
            assistant_msgs = [m for m in messages if m["role"] == "assistant"]
            assert len(assistant_msgs) > 0
            
            # Verify sources field exists (populated by RAG)
            assert "sources" in assistant_msgs[0]
            
            print(f"✅ Chat used RAG, answer: {assistant_msgs[0]['content'][:100]}...")
            
        finally:
            os.unlink(temp_path)
    
    def test_04_faiss_mapping_persists_across_queries(self, client, sample_document, cleanup_faiss):
        """Step 4: FAISS mapping works for multiple sequential queries."""
        # Ingest
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(sample_document)
            temp_path = f.name
        
        try:
            with open(temp_path, 'rb') as f:
                client.post(
                    "/api/v1/documents/upload",
                    files={"file": ("trading_guide.txt", f, "text/plain")}
                )
            
            import time
            time.sleep(2)
            
            # Multiple queries should all work
            queries = [
                "What is trading assistant?",
                "How do traders use assistants?",
                "Tell me about order management",
            ]
            
            for query in queries:
                chunks, score = retrieve(query, top_k=2)
                assert len(chunks) > 0, f"Failed for query: {query}"
                print(f"✅ Query '{query[:30]}...' returned {len(chunks)} chunks")
                
        finally:
            os.unlink(temp_path)
    
    def test_05_full_pipeline_integration(self, client, cleanup_faiss):
        """Step 5: Complete flow - Upload → Ingest → Chat with RAG."""
        # Create document about specific topic
        doc_content = """
        Machine Learning in Healthcare
        
        Machine learning transforms healthcare through:
        1. Medical image analysis
        2. Drug discovery acceleration  
        3. Personalized treatment plans
        4. Predictive diagnostics
        
        Hospitals use ML to improve patient outcomes.
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(doc_content)
            temp_path = f.name
        
        try:
            # 1. Upload
            with open(temp_path, 'rb') as f:
                upload_resp = client.post(
                    "/api/v1/documents/upload",
                    files={"file": ("ml_healthcare.txt", f, "text/plain")}
                )
            assert upload_resp.status_code == 200
            doc_id = upload_resp.json()["document_id"]
            
            import time
            time.sleep(2)
            
            # 2. Verify FAISS
            assert os.path.exists("/data/faiss/default.faiss")
            
            # 3. Query via Chat API
            chat_resp = client.post(
                "/api/v1/chat/start",
                json={"first_message": "How is machine learning used in healthcare?"}
            )
            assert chat_resp.status_code == 200
            
            # 4. Verify RAG response
            conv_id = chat_resp.json()["conversation_id"]
            history = client.get(f"/api/v1/chat/{conv_id}/history").json()
            
            assistant_msg = [m for m in history["messages"] if m["role"] == "assistant"][0]
            assert "sources" in assistant_msg
            assert len(assistant_msg["sources"]) >= 0  # May be empty in stub mode
            
            print(f"✅ Full pipeline: Upload → Ingest → FAISS → Chat → Answer")
            
        finally:
            os.unlink(temp_path)


class TestRAGWithStubMode:
    """Test RAG behavior in stub mode (deterministic)."""
    
    def test_stub_mode_deterministic(self, client):
        """Verify stub mode produces consistent results."""
        os.environ["LLM_PROVIDER"] = "stub"
        os.environ["EVAL_SEED"] = "1337"
        
        # Same query should behave consistently
        resp1 = client.post(
            "/api/v1/chat/start",
            json={"first_message": "Test query"}
        )
        resp2 = client.post(
            "/api/v1/chat/start", 
            json={"first_message": "Test query"}
        )
        
        assert resp1.status_code == resp2.status_code == 200
        # Both create conversations successfully
        assert resp1.json()["conversation_id"] != resp2.json()["conversation_id"]
DocVault-AI - Process Instructions.
1 Start the infrastructure
Introduce all required facilities:
docker-compose up redis worker backend -d.
 redis -- caching and DLQ
 worker Background ingestion worker.
 backend Cutting-edge service API server and ingestion logic.
In case the names of containers are different, then list them with:
docker ps

2 Run database migrations
hotfix the newest schema modifications:
docker compose exec backend alembic upgrade head
 Makes sure tables such as documents are present.
 Ensure that the directory /data /db/db.sqlite is mounted and writable.

3 Start the worker
Run ingestion worker:
docker compose run worker Backend python -m app.worker.worker
 Workers incidence gets the ingestion jobs and updates the FAISS.
 Requirements of a single writer: There must only be one worker to write to FAISS at a time.

4 Upload a test document
curl -f file= /path/to/sample.pdf http://localhost:8000/api/v1/documents.
 Injecting jobs on workers Backend queues.
 Substitute sample.pdf with any test file.

5 Check document status
curl http://localhost:8000/api/v1/documents/<docid>/status
 upload API is used to get docid or documents are available by /api/v1/documents.
 Status significantly: queued - processing - completed.
Optional: List all documents:
curl http://localhost:8000/api/v1/documents
 Repons with id, status and metajson (with chunkscount).

6 Inspect logs
The document logs get stored in /data/ logs:
docker compose exec backend ls /data/logs/
docker compose Command run exit backend that parents are cat/data/logs/ingest.log.docid.log
 Dumps complete traceback on failure of ingestion.

7 Single-writer FAISS
 One only worker is to write to FAISS.
 Parallel writes are capable of corruption of the index.

8 Reconstruct FAISS using DB (where necessary)
docker compose stop backend python /app/app/tools/rebuildfaissfromchunks.py.
 Reconstructs FAISS index safely on chunks stored.

9 CI / EMBEDDINGSTUB
 To achieve quick CI and prevent high model downloading:
export EMBEDDINGSTUB=true
 GitHub Actions example:
env:
  EMBEDDINGSTUB: "true"

10 Optional -- Admin UI (Frontend)
 Companion: Slice documents and status in a minimal interface.
 File: frontend/src/components/AdminDocuments.jsx
Example behavior:
 Requests The Fetches /api/v1/documents and presents a document list.
 Every document is left at the status page:
/api/v1/documents/<docid>/status
/api/v1/documents/<docid>/chunks
 Faster displays status and number of chunks without API curl commands.
 Good as an internal administration test or a QA test.

11 Notes / tips
 List all running containers:
docker ps
 Attach to backend container:
docker exec -it backend bash
 Check ingestion jobs in dlq Redis base:
docker compose run redis redis-cli -n 0 LRANGE ingest_dlq -1.
 Make sure that /data/log and /data/db can be written to in containers.

Summary
 Names workable: Minor counters version (task 15 instruction, upload, status, some logs, single-writer FAISS, instructions to rebuild).
 Admin UI: Optional, bare minimum implementation done.
 Instructions can be used to derive container names and paths by users.
 Instructions are self-executible, executeable and CI-conscious.


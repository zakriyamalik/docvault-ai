import logging
from app.llm.pii import redact_pii

logger = logging.getLogger("query_audit")
logger.setLevel(logging.INFO)

# You can configure file/stream handler as needed

def log_query(query: str, response: str, user_id: str = None):
    redacted_query, query_pii = redact_pii(query)
    redacted_response, response_pii = redact_pii(response)

    audit_entry = {
        "user_id": user_id,
        "query": redacted_query,
        "response": redacted_response,
        "query_pii_metadata": query_pii,
        "response_pii_metadata": response_pii
    }

    logger.info(audit_entry)

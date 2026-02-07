import { useEffect } from "react";
import { useGetDocumentStatusQuery } from "../app/api/documentsApi";

export function useDocumentStatusPolling(documentId, currentStatus) {
  const shouldPoll = ["queued", "processing", "pending"].includes(currentStatus);
  
  const { data, error, isFetching } = useGetDocumentStatusQuery(documentId, {
    skip: !documentId || !shouldPoll,
    pollingInterval: shouldPoll ? 2000 : 0, // Poll every 2 seconds
    refetchOnMountOrArgChange: true,
  });

  return {
    status: data?.status || currentStatus,
    chunksCount: data?.chunks_count,
    errorMessage: data?.error_message,
    isPolling: isFetching,
    error,
  };
}
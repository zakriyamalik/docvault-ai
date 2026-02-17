import { useCallback } from "react";
import { useDispatch } from "react-redux";
import {
  useStartConversationMutation,
  useGetHistoryQuery,
} from "../app/api/chatApi";
import {
  setCurrentConversation,
  setMessages,
  setLoading,
  setError,
} from "../features/chatSlice";

export function useStartConversation() {
  const dispatch = useDispatch();
  const [startApi] = useStartConversationMutation();

  const startConversation = useCallback(
    async (firstMessage, titlePreview = null) => {
      dispatch(setLoading(true));
      dispatch(setError(null));

      try {
        // Step 1: Start conversation
        const result = await startApi({
          firstMessage,
          titlePreview,
        }).unwrap();

        const { conversation_id } = result;

        // Step 2: Immediately fetch history to get assistant response
        // We can't use the hook here (rules of hooks), so we fetch directly
        const response = await fetch(
          `${
            import.meta.env.VITE_API_URL || "http://localhost:8000"
          }/api/chat/${conversation_id}/history`
        );
        const historyData = await response.json();

        dispatch(setCurrentConversation(conversation_id));
        dispatch(setMessages(historyData.messages));
        dispatch(setLoading(false));

        return { success: true, conversationId: conversation_id };
      } catch (err) {
        dispatch(setError(err.message || "Failed to start conversation"));
        dispatch(setLoading(false));
        return { success: false, error: err };
      }
    },
    [dispatch, startApi]
  );

  return startConversation;
}
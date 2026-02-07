import { useCallback } from "react";
import { useDispatch, useSelector } from "react-redux";
import { useSendMessageMutation } from "../app/api/chatApi";
import {
  addMessage,
  setLoading,
  setError,
  setMessages,
} from "../features/chatSlice";

export function useSendMessage() {
  const dispatch = useDispatch();
  const currentConversationId = useSelector(
    (state) => state.chat.currentConversationId
  );
  const [sendMessageApi] = useSendMessageMutation();

  const sendMessage = useCallback(
    async (content) => {
      if (!currentConversationId) {
        dispatch(setError("No active conversation"));
        return { success: false };
      }

      dispatch(setLoading(true));
      dispatch(setError(null));

      // Optimistic user message
      const optimisticUserMessage = {
        message_id: `temp-${Date.now()}`,
        role: "user",
        content,
        timestamp: new Date().toISOString(),
        sources: [],
      };
      dispatch(addMessage(optimisticUserMessage));

      try {
        const result = await sendMessageApi({
          conversationId: currentConversationId,
          content,
        }).unwrap();

        // Add assistant response
        const assistantMessage = {
          message_id: result.message_id,
          role: result.role,
          content: result.content,
          timestamp: new Date().toISOString(),
          sources: result.sources,
        };

        // Replace optimistic message with real flow
        dispatch((dispatch, getState) => {
          const currentMessages = getState().chat.messages;
          const filtered = currentMessages.filter(
            (m) => m.message_id !== optimisticUserMessage.message_id
          );
          dispatch(setMessages([...filtered, optimisticUserMessage, assistantMessage]));
        });

        dispatch(setLoading(false));
        return { success: true };
      } catch (err) {
        dispatch(setError(err.message || "Failed to send message"));
        dispatch(setLoading(false));
        return { success: false, error: err };
      }
    },
    [currentConversationId, dispatch, sendMessageApi]
  );

  return sendMessage;
}
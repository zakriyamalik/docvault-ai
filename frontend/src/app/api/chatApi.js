import { baseApi } from "./baseApi";

export const chatApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    // Start new conversation (returns conversation_id, title, first_message_id)
    startConversation: builder.mutation({
      query: ({ firstMessage, titlePreview }) => ({
        url: "/chat/start",
        method: "POST",
        body: {
          first_message: firstMessage,
          title_preview: titlePreview,
        },
      }),
      invalidatesTags: ["Conversations"],
    }),

    // Send message in existing conversation
    sendMessage: builder.mutation({
      query: ({ conversationId, content }) => ({
        url: `/chat/${conversationId}/message`,
        method: "POST",
        body: { content },
      }),
      invalidatesTags: (result, error, { conversationId }) => [
        { type: "Messages", id: conversationId },
      ],
    }),

    // Get conversation history
    getHistory: builder.query({
      query: (conversationId) => `/chat/${conversationId}/history`,
      providesTags: (result, error, conversationId) => [
        { type: "Messages", id: conversationId },
      ],
    }),

    // List all conversations
    listConversations: builder.query({
      query: () => "/chat/conversations",
      providesTags: ["Conversations"],
      transformResponse: (response) => response.conversations,
    }),

    // Delete conversation
    deleteConversation: builder.mutation({
      query: (conversationId) => ({
        url: `/chat/${conversationId}`,
        method: "DELETE",
      }),
      invalidatesTags: ["Conversations"],
    }),
  }),
});

export const {
  useStartConversationMutation,
  useSendMessageMutation,
  useGetHistoryQuery,
  useListConversationsQuery,
  useDeleteConversationMutation,
} = chatApi;
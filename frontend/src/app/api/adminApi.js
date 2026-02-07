import { baseApi } from "./baseApi";

export const adminApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    // Get DLQ items
    getDLQ: builder.query({
      query: () => "/admin/dlq",
      providesTags: ["DLQ"],
      transformResponse: (response) => response.dlq,
    }),

    // Retry DLQ item
    retryDLQ: builder.mutation({
      query: (documentId) => ({
        url: `/admin/dlq/retry/${documentId}`,
        method: "POST",
      }),
      invalidatesTags: ["DLQ", "Documents"],
    }),

    // Re-embed document
    reembedDocument: builder.mutation({
      query: (documentId) => ({
        url: `/admin/documents/${documentId}/reembed`,
        method: "POST",
      }),
      invalidatesTags: (result, error, documentId) => [
        { type: "Documents", id: documentId },
      ],
    }),
  }),
});

export const {
  useGetDLQQuery,
  useRetryDLQMutation,
  useReembedDocumentMutation,
} = adminApi;
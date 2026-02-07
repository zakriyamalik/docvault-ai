import { baseApi } from "./baseApi";

export const documentsApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    // List all documents
    listDocuments: builder.query({
      query: () => "/documents",
      providesTags: (result = []) => [
        "Documents",
        ...result.map(({ id }) => ({ type: "Documents", id })),
      ],
    }),

    // Get document status (for polling)
    getDocumentStatus: builder.query({
      query: (documentId) => `/documents/${documentId}/status`,
      providesTags: (result, error, documentId) => [
        { type: "Documents", id: documentId },
      ],
    }),

    // Get document chunks (for viewer)
    getDocumentChunks: builder.query({
      query: (documentId) => `/documents/${documentId}/chunks`,
    }),

    // Upload document
    uploadDocument: builder.mutation({
      query: (file) => {
        const formData = new FormData();
        formData.append("file", file);
        return {
          url: "/documents/upload",
          method: "POST",
          body: formData,
          headers: {},
        };
      },
      invalidatesTags: ["Documents"],
    }),

    // ✅ MISSING: Re-embed document
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
  useListDocumentsQuery,
  useGetDocumentStatusQuery,
  useGetDocumentChunksQuery,
  useUploadDocumentMutation,
  useReembedDocumentMutation, // ✅ Add this export
} = documentsApi;
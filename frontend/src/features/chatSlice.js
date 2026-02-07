import { createSlice } from "@reduxjs/toolkit";

const initialState = {
  currentConversationId: null,
  messages: [],
  isLoading: false,
  error: null,
  sidebarOpen: true,
};

const chatSlice = createSlice({
  name: "chat",
  initialState,
  reducers: {
    setCurrentConversation: (state, action) => {
      state.currentConversationId = action.payload;
      state.messages = [];
      state.error = null;
    },
    setMessages: (state, action) => {
      state.messages = action.payload;
    },
    addMessage: (state, action) => {
      state.messages.push(action.payload);
    },
    setLoading: (state, action) => {
      state.isLoading = action.payload;
    },
    setError: (state, action) => {
      state.error = action.payload;
    },
    clearError: (state) => {
      state.error = null;
    },
    toggleSidebar: (state) => {
      state.sidebarOpen = !state.sidebarOpen;
    },
    setSidebarOpen: (state, action) => {
      state.sidebarOpen = action.payload;
    },
  },
});

export const {
  setCurrentConversation,
  setMessages,
  addMessage,
  setLoading,
  setError,
  clearError,
  toggleSidebar,
  setSidebarOpen,
} = chatSlice.actions;

export default chatSlice.reducer;
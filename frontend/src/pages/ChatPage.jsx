import React, { useEffect } from "react";
import { useParams } from "react-router-dom";
import { useSelector, useDispatch } from "react-redux";
import { Menu } from "lucide-react";
import { Button } from "../components/ui/Button";
import { MessageList } from "../components/chat/MessageList";
import { ChatInput } from "../components/chat/ChatInput";
import { ConversationList } from "../components/chat/ConversationList";
import { EmptyState } from "../components/chat/EmptyState";
import { useGetHistoryQuery } from "../app/api/chatApi";
import { setMessages, setLoading, toggleSidebar } from "../features/chatSlice";
import { cn } from "../lib/utils";

export default function ChatPage() {
  const { conversationId } = useParams();
  const dispatch = useDispatch();
  
  const currentConversationId = useSelector(
    (state) => state.chat.currentConversationId
  );
  const messages = useSelector((state) => state.chat.messages);
  const isLoading = useSelector((state) => state.chat.isLoading);
  const sidebarOpen = useSelector((state) => state.chat.sidebarOpen);
  
  // Fetch history when URL changes
  const { data: historyData, isFetching } = useGetHistoryQuery(conversationId, {
    skip: !conversationId,
  });
  
  useEffect(() => {
    if (historyData?.messages) {
      dispatch(setMessages(historyData.messages));
    }
  }, [historyData, dispatch]);
  
  const showEmptyState = messages.length === 0 && !isFetching && !isLoading;
  
  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar - Desktop always visible, mobile toggleable */}
      <div
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-64 bg-background border-r transform transition-transform duration-200 ease-in-out lg:relative lg:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <ConversationList />
      </div>
      
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => dispatch(toggleSidebar())}
        />
      )}
      
      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="flex items-center gap-4 px-4 py-3 border-b bg-card">
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden"
            onClick={() => dispatch(toggleSidebar())}
          >
            <Menu className="h-5 w-5" />
          </Button>
          
          <div className="flex-1">
            <h1 className="font-semibold">
              {conversationId ? "Chat" : "New Conversation"}
            </h1>
            {conversationId && (
              <p className="text-xs text-muted-foreground">
                ID: {conversationId.slice(0, 8)}...
              </p>
            )}
          </div>
        </header>
        
        {/* Messages */}
        <div className="flex-1 overflow-hidden">
          {showEmptyState ? (
            <EmptyState />
          ) : (
            <MessageList />
          )}
        </div>
        
        {/* Input */}
        <ChatInput disabled={isLoading || isFetching} />
      </div>
    </div>
  );
}
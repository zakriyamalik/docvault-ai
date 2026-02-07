import React from "react";
import { useSelector, useDispatch } from "react-redux";
import { useNavigate, useParams } from "react-router-dom";
import { Plus, MessageSquare, Trash2, Loader2 } from "lucide-react";
import { Button } from "../ui/Button";
import { ScrollArea } from "../ui/ScrollArea";
import { Skeleton } from "../ui/Skeleton";
import { cn } from "../../lib/utils";
import {
  useListConversationsQuery,
  useDeleteConversationMutation,
} from "../../app/api/chatApi";
import { setCurrentConversation } from "../../features/chatSlice";

export function ConversationList() {
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const { conversationId: urlConversationId } = useParams();
  
  const { data: conversations = [], isLoading } = useListConversationsQuery();
  const [deleteConversation] = useDeleteConversationMutation();
  
  const currentConversationId = useSelector(
    (state) => state.chat.currentConversationId
  );
  
  const activeId = urlConversationId || currentConversationId;
  
  const handleNewChat = () => {
    dispatch(setCurrentConversation(null));
    navigate("/chat");
  };
  
  const handleSelectConversation = (id) => {
    dispatch(setCurrentConversation(id));
    navigate(`/chat/${id}`);
  };
  
  const handleDelete = async (e, id) => {
    e.stopPropagation();
    if (confirm("Delete this conversation?")) {
      await deleteConversation(id);
      if (activeId === id) {
        handleNewChat();
      }
    }
  };
  
  return (
    <div className="flex flex-col h-full bg-muted/30 border-r">
      <div className="p-4 border-b">
        <Button onClick={handleNewChat} className="w-full" variant="outline">
          <Plus className="h-4 w-4 mr-2" />
          New Chat
        </Button>
      </div>
      
      <ScrollArea className="flex-1">
        <div className="p-2 space-y-1">
          {isLoading ? (
            <>
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
            </>
          ) : conversations.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">
              No conversations yet
            </p>
          ) : (
            conversations.map((conv) => (
              <button
                key={conv.id}
                onClick={() => handleSelectConversation(conv.id)}
                className={cn(
                  "w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left text-sm transition-colors",
                  activeId === conv.id
                    ? "bg-primary text-primary-foreground"
                    : "hover:bg-muted"
                )}
              >
                <MessageSquare className="h-4 w-4 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="truncate font-medium">
                    {conv.title_preview || "New Conversation"}
                  </p>
                  <p className="text-xs opacity-70">
                    {new Date(conv.updated_at).toLocaleDateString()}
                  </p>
                </div>
                <button
                  onClick={(e) => handleDelete(e, conv.id)}
                  className={cn(
                    "opacity-0 group-hover:opacity-100 p-1 rounded",
                    "hover:bg-destructive hover:text-destructive-foreground",
                    "transition-opacity"
                  )}
                  title="Delete conversation"
                >
                  <Trash2 className="h-3 w-3" />
                </button>
              </button>
            ))
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
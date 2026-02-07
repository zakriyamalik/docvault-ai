import React, { useEffect, useRef } from "react";
import { useSelector } from "react-redux";
import { ScrollArea } from "../ui/ScrollArea";
import { MessageBubble } from "./MessageBubble";
import { Skeleton } from "../ui/Skeleton";

export function MessageList() {
  const messages = useSelector((state) => state.chat.messages);
  const isLoading = useSelector((state) => state.chat.isLoading);
  const scrollRef = useRef(null);
  
  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isLoading]);
  
  if (messages.length === 0 && !isLoading) {
    return null;
  }
  
  return (
    <ScrollArea className="flex-1 h-full">
      <div className="space-y-0 pb-4">
        {messages.map((message, index) => (
          <MessageBubble 
            key={message.message_id || index} 
            message={message}
            isStreaming={isLoading && index === messages.length - 1 && message.role === "assistant"}
          />
        ))}
        
        {isLoading && messages.length === 0 && (
          <div className="space-y-4 p-4">
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
          </div>
        )}
        
        <div ref={scrollRef} />
      </div>
    </ScrollArea>
  );
}
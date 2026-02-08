import React, { useState, useRef, useCallback } from "react";
import { useSelector } from "react-redux";
import { useNavigate } from "react-router-dom"; // <--- ADDED
import { useDropzone } from "react-dropzone";
import { Send, Paperclip, X, Loader2 } from "lucide-react";
import { Button } from "../ui/Button";
import { Textarea } from "../ui/Textarea";
import { cn } from "../../lib/utils";
import { useSendMessage } from "../../hooks/useSendMessage";
import { useStartConversation } from "../../hooks/useStartConversation";

const MAX_LENGTH = 2000;

export function ChatInput({ disabled = false }) {
  const [message, setMessage] = useState("");
  const [files, setFiles] = useState([]);
  const textareaRef = useRef(null);

  // ✅ Read conversationId from Redux at top level
  const currentConversationId = useSelector((state) => state.chat.currentConversationId);

  // ✅ navigation hook
  const navigate = useNavigate();

  const sendMessage = useSendMessage();
  const startConversation = useStartConversation();

  const onDrop = useCallback((acceptedFiles) => {
    setFiles((prev) => [...prev, ...acceptedFiles]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    noClick: true,
    disabled: disabled || files.length > 0,
  });

  const handleSubmit = async () => {
    if (!message.trim() && files.length === 0) return;
    if (disabled) return;

    const text = message.trim();
    setMessage("");
    setFiles([]);

    if (!currentConversationId) {
      await startConversation(text);
    } else {
      await sendMessage(text);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const removeFile = (index) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const charCount = message.length;
  const isOverLimit = charCount > MAX_LENGTH;

  return (
    <div
      {...getRootProps()}
      className={cn(
        "relative border-t bg-background p-4",
        isDragActive && "bg-primary/5 border-primary"
      )}
    >
      <input {...getInputProps()} />

      {files.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-3">
          {files.map((file, index) => (
            <div
              key={index}
              className="flex items-center gap-2 px-3 py-1.5 bg-muted rounded-full text-sm"
            >
              <Paperclip className="h-3 w-3" />
              <span className="max-w-[150px] truncate">{file.name}</span>
              <button
                onClick={() => removeFile(index)}
                className="hover:text-destructive"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="flex gap-2 items-end">
        <div className="flex-1 relative">
          <Textarea
            ref={textareaRef}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question... (Shift+Enter for new line)"
            className={cn(
              "min-h-[80px] resize-none pr-16",
              isOverLimit && "border-destructive focus-visible:ring-destructive"
            )}
            disabled={disabled}
            aria-label="Message input"
          />
          <span
            className={cn(
              "absolute bottom-2 right-2 text-xs",
              isOverLimit ? "text-destructive" : "text-muted-foreground"
            )}
          >
            {charCount}/{MAX_LENGTH}
          </span>
        </div>

        <div className="flex flex-col gap-2">
          <Button
            type="button"
            variant="outline"
            size="icon"
            className="shrink-0"
            // <-- REPLACED: navigate to admin page on click
            onClick={() => navigate("/admin")}
            disabled={disabled}
            title="Go to Admin to upload documents"
          >
            <Paperclip className="h-4 w-4" />
          </Button>

          <Button
            onClick={handleSubmit}
            disabled={disabled || (!message.trim() && files.length === 0) || isOverLimit}
            size="icon"
            className="shrink-0"
            title="Send message"
          >
            {disabled ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </div>
      </div>

      {isDragActive && (
        <div className="absolute inset-0 bg-primary/10 border-2 border-dashed border-primary rounded-lg flex items-center justify-center">
          <p className="text-primary font-medium">Drop files here</p>
        </div>
      )}
    </div>
  );
}

"use client";

import { useEffect, useRef, useState } from "react";
import { Bot, Send, Sparkles, User, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { useTaskStore } from "@/store/taskStore";
import type { ChatMessage } from "@/types";

interface ChatPanelProps {
  open: boolean;
  onClose: () => void;
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={cn("flex gap-2", isUser ? "flex-row-reverse" : "flex-row")}>
      <div
        className={cn(
          "flex h-7 w-7 shrink-0 items-center justify-center rounded-full",
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-muted text-foreground",
        )}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>
      <div
        className={cn(
          "max-w-[80%] rounded-lg px-3 py-2 text-sm whitespace-pre-wrap",
          isUser ? "bg-primary text-primary-foreground" : "bg-muted",
        )}
      >
        {message.content}
        {message.tool_calls && message.tool_calls.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {message.tool_calls.map((call, index) => (
              <Badge
                key={`${call.name}-${index}`}
                variant="secondary"
                className="text-[10px] font-normal"
              >
                {call.name}
              </Badge>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex gap-2">
      <div className="bg-muted flex h-7 w-7 shrink-0 items-center justify-center rounded-full">
        <Bot className="h-4 w-4" />
      </div>
      <div className="bg-muted flex items-center gap-1 rounded-lg px-3 py-3">
        <span className="bg-foreground/50 h-1.5 w-1.5 animate-bounce rounded-full [animation-delay:-0.3s]" />
        <span className="bg-foreground/50 h-1.5 w-1.5 animate-bounce rounded-full [animation-delay:-0.15s]" />
        <span className="bg-foreground/50 h-1.5 w-1.5 animate-bounce rounded-full" />
      </div>
    </div>
  );
}

export function ChatPanel({ open, onClose }: ChatPanelProps) {
  const chatHistory = useTaskStore((state) => state.chatHistory);
  const isChatLoading = useTaskStore((state) => state.isChatLoading);
  const sendChatMessage = useTaskStore((state) => state.sendChatMessage);
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [chatHistory, isChatLoading]);

  if (!open) {
    return null;
  }

  const handleSend = async (event: React.FormEvent) => {
    event.preventDefault();
    const message = input.trim();
    if (!message || isChatLoading) {
      return;
    }
    setInput("");
    // TODO v0.4: replace fetch with SSE streaming
    await sendChatMessage(message);
  };

  return (
    <aside className="bg-card flex w-full max-w-sm flex-col border-l">
      <div className="flex items-center justify-between border-b px-4 py-3">
        <div className="flex items-center gap-2">
          <Sparkles className="text-primary h-4 w-4" />
          <span className="font-medium">Taskify AI</span>
        </div>
        <Button
          variant="ghost"
          size="icon"
          onClick={onClose}
          aria-label="Close chat"
        >
          <X className="h-4 w-4" />
        </Button>
      </div>

      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto p-4">
        {chatHistory.length === 0 && (
          <div className="text-muted-foreground flex h-full flex-col items-center justify-center text-center text-sm">
            <Bot className="mb-2 h-8 w-8" />
            <p className="text-foreground font-medium">Ask about your tasks</p>
            <p className="mt-1 max-w-[16rem]">
              Try: &ldquo;How many tasks do I have?&rdquo; or &ldquo;Create a
              high priority task to review the PR&rdquo;.
            </p>
          </div>
        )}
        {chatHistory.map((message, index) => (
          <MessageBubble key={index} message={message} />
        ))}
        {isChatLoading && <TypingIndicator />}
      </div>

      <form onSubmit={handleSend} className="flex gap-2 border-t p-3">
        <Input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Ask about your tasks..."
          disabled={isChatLoading}
        />
        <Button
          type="submit"
          size="icon"
          disabled={isChatLoading || !input.trim()}
          aria-label="Send message"
        >
          <Send className="h-4 w-4" />
        </Button>
      </form>
    </aside>
  );
}

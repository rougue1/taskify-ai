"use client";

import { useEffect, useRef, useState } from "react";
import {
  Bot,
  Brain,
  ChevronRight,
  Plus,
  Send,
  Sparkles,
  Square,
  User,
  Wrench,
  X,
} from "lucide-react";
import ReactMarkdown from "react-markdown";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { useTaskStore } from "@/store/taskStore";
import type { ChatMessage } from "@/types";

// Minimal markdown renderer with utility-class-styled elements.
function Md({ children }: { children: string }) {
  return (
    <ReactMarkdown
      components={{
        p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
        ul: ({ children }) => <ul className="mb-2 list-disc list-inside space-y-0.5">{children}</ul>,
        ol: ({ children }) => <ol className="mb-2 list-decimal list-inside space-y-0.5">{children}</ol>,
        li: ({ children }) => <li>{children}</li>,
        strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
        em: ({ children }) => <em className="italic">{children}</em>,
        h1: ({ children }) => <h1 className="mb-1 text-base font-bold">{children}</h1>,
        h2: ({ children }) => <h2 className="mb-1 text-sm font-bold">{children}</h2>,
        h3: ({ children }) => <h3 className="mb-1 text-sm font-semibold">{children}</h3>,
        code: ({ children, className }) =>
          className ? (
            <code className="block bg-black/10 dark:bg-white/10 rounded p-2 overflow-x-auto text-xs font-mono">{children}</code>
          ) : (
            <code className="bg-black/10 dark:bg-white/10 rounded px-1 font-mono text-[0.85em]">{children}</code>
          ),
        pre: ({ children }) => <pre className="mb-2 overflow-x-auto rounded">{children}</pre>,
        blockquote: ({ children }) => (
          <blockquote className="border-l-2 border-current pl-2 opacity-70">{children}</blockquote>
        ),
        a: ({ href, children }) => (
          <a href={href} className="underline underline-offset-2" target="_blank" rel="noopener noreferrer">
            {children}
          </a>
        ),
      }}
    >
      {children}
    </ReactMarkdown>
  );
}

interface ChatPanelProps {
  open: boolean;
  onClose: () => void;
}

// Live "Thinking..." panel shown while the model reasons, before any answer
// token arrives. Streams reasoning into a scrollable container.
function ActiveThinking({ reasoning }: { reasoning: string }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.scrollTo({ top: ref.current.scrollHeight });
  }, [reasoning]);

  return (
    <div className="border-primary/20 bg-primary/5 rounded-lg border p-2.5">
      <div className="text-primary mb-1 flex items-center gap-1.5 text-xs font-medium">
        <Brain className="h-3.5 w-3.5 animate-pulse" />
        <span className="animate-pulse">Thinking…</span>
      </div>
      <div
        ref={ref}
        className="text-muted-foreground max-h-28 overflow-y-auto text-xs leading-relaxed whitespace-pre-wrap"
      >
        {reasoning}
      </div>
    </div>
  );
}

// Collapsed "View reasoning" disclosure shown after the answer arrives.
function ReasoningDisclosure({ reasoning }: { reasoning: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mb-1.5">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="text-muted-foreground hover:text-foreground flex items-center gap-1 text-xs"
      >
        <ChevronRight className={cn("h-3 w-3 transition-transform", open && "rotate-90")} />
        <Brain className="h-3 w-3" />
        View reasoning
      </button>
      {open && (
        <div className="text-muted-foreground border-border mt-1 max-h-40 overflow-y-auto border-l-2 pl-2 text-xs leading-relaxed">
          <Md>{reasoning}</Md>
        </div>
      )}
    </div>
  );
}

// Collapsible list of the tool calls the agent made for a message. Cards show up
// as tool_start events arrive (during streaming) and persist afterward.
function ToolCalls({ message }: { message: ChatMessage }) {
  const calls = message.tool_calls ?? [];
  const [open, setOpen] = useState(Boolean(message.streaming));
  if (calls.length === 0) return null;

  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="text-muted-foreground hover:text-foreground flex items-center gap-1 text-xs"
      >
        <ChevronRight className={cn("h-3 w-3 transition-transform", open && "rotate-90")} />
        <Wrench className="h-3 w-3" />
        {calls.length} tool {calls.length === 1 ? "call" : "calls"}
      </button>
      {open && (
        <div className="mt-1.5 space-y-1.5">
          {calls.map((call, index) => {
            const output = call.id ? message.toolOutputs?.[call.id] : undefined;
            return (
              <div
                key={`${call.name}-${index}`}
                className="border-border bg-muted/40 rounded-md border p-2 text-xs"
              >
                <div className="flex items-center gap-1.5 font-medium">
                  <Wrench className="text-primary h-3 w-3" />
                  <code>{call.name}</code>
                </div>
                {call.args && Object.keys(call.args).length > 0 && (
                  <pre className="text-muted-foreground mt-1 overflow-x-auto text-[11px] whitespace-pre-wrap">
                    {JSON.stringify(call.args)}
                  </pre>
                )}
                {output && (
                  <pre className="text-muted-foreground/80 mt-1 max-h-20 overflow-y-auto text-[11px] whitespace-pre-wrap">
                    {output}
                  </pre>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  const reasoning = message.reasoning?.trim() ?? "";
  const hasReasoning = reasoning.length > 0;
  const hasAnswer = message.content.length > 0;
  const thinking = Boolean(message.streaming) && !hasAnswer;

  return (
    <div className={cn("flex gap-2", isUser ? "flex-row-reverse" : "flex-row")}>
      <div
        className={cn(
          "flex h-7 w-7 shrink-0 items-center justify-center rounded-full",
          isUser ? "bg-primary text-primary-foreground" : "bg-muted text-foreground",
        )}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>
      <div
        className={cn(
          "max-w-[85%] rounded-lg px-3 py-2 text-sm",
          isUser ? "bg-primary text-primary-foreground" : "bg-muted",
        )}
      >
        {/* Reasoning: live panel while thinking, disclosure once answered. */}
        {!isUser && hasReasoning && thinking && <ActiveThinking reasoning={reasoning} />}
        {!isUser && hasReasoning && !thinking && (
          <ReasoningDisclosure reasoning={reasoning} />
        )}

        {/* Pre-answer feedback when the model emits no reasoning. */}
        {!isUser && thinking && !hasReasoning && (
          <div className="flex items-center gap-1 py-1">
            <span className="bg-foreground/50 h-1.5 w-1.5 animate-bounce rounded-full [animation-delay:-0.3s]" />
            <span className="bg-foreground/50 h-1.5 w-1.5 animate-bounce rounded-full [animation-delay:-0.15s]" />
            <span className="bg-foreground/50 h-1.5 w-1.5 animate-bounce rounded-full" />
          </div>
        )}

        {hasAnswer && (
          <div>
            {isUser ? (
              <div className="whitespace-pre-wrap">{message.content}</div>
            ) : (
              <Md>{message.content}</Md>
            )}
            {message.streaming && (
              <span className="animate-blink inline-block">▍</span>
            )}
          </div>
        )}

        {!isUser && <ToolCalls message={message} />}
      </div>
    </div>
  );
}

export function ChatPanel({ open, onClose }: ChatPanelProps) {
  const chatHistory = useTaskStore((state) => state.chatHistory);
  const isChatLoading = useTaskStore((state) => state.isChatLoading);
  const sendChatMessage = useTaskStore((state) => state.sendChatMessage);
  const stopStreaming = useTaskStore((state) => state.stopStreaming);
  const newConversation = useTaskStore((state) => state.newConversation);
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
    await sendChatMessage(message);
  };

  return (
    <aside className="bg-card flex w-full max-w-sm flex-col border-l">
      <div className="flex items-center justify-between border-b px-4 py-3">
        <div className="flex items-center gap-2">
          <Sparkles className="text-primary h-4 w-4" />
          <span className="font-medium">Taskify AI</span>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={newConversation}
            disabled={chatHistory.length === 0 && !isChatLoading}
            title="New conversation"
          >
            <Plus className="h-4 w-4" />
            <span className="hidden sm:inline">New</span>
          </Button>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close chat">
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto p-4">
        {chatHistory.length === 0 && (
          <div className="text-muted-foreground flex h-full flex-col items-center justify-center text-center text-sm">
            <Bot className="mb-2 h-8 w-8" />
            <p className="text-foreground font-medium">Ask about your tasks</p>
            <p className="mt-1 max-w-[16rem]">
              Try: &ldquo;How many tasks do I have?&rdquo; or &ldquo;What should I
              focus on?&rdquo;
            </p>
          </div>
        )}
        {chatHistory.map((message, index) => (
          <MessageBubble key={index} message={message} />
        ))}
      </div>

      <form onSubmit={handleSend} className="flex gap-2 border-t p-3">
        <Input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Ask about your tasks..."
          disabled={isChatLoading}
        />
        {isChatLoading ? (
          <Button
            type="button"
            size="icon"
            variant="destructive"
            onClick={stopStreaming}
            aria-label="Stop generating"
            title="Stop"
          >
            <Square className="h-4 w-4" />
          </Button>
        ) : (
          <Button
            type="submit"
            size="icon"
            disabled={!input.trim()}
            aria-label="Send message"
          >
            <Send className="h-4 w-4" />
          </Button>
        )}
      </form>
    </aside>
  );
}

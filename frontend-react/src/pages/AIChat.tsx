import { useState, useRef, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { useMutation } from "@tanstack/react-query"
import { Send, Bot, User, Sparkles, RefreshCw, Trash2 } from "lucide-react"
import { sendChatMessage } from "../api/endpoints"
import type { ChatMessage } from "../types"
import clsx from "clsx"

const SUGGESTIONS = [
  "¿Quién ganará la Champions League?",
  "¿Cuál es el equipo con mejor defensa según Elo?",
  "¿Qué equipo tiene el mejor ataque del modelo Dixon-Coles?",
  "¿Quién tiene mayor probabilidad de ser campeón del Mundial 2026?",
  "¿Cómo funciona el modelo Klement?",
  "¿Qué equipos tienen mayor probabilidad de descenso?",
  "Explica el modelo híbrido de predicción",
  "¿Cuál es la diferencia entre Elo y Dixon-Coles?",
]

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isBot = msg.role === "assistant"
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={clsx("flex gap-3", !isBot && "flex-row-reverse")}
    >
      <div
        className={clsx(
          "w-8 h-8 rounded-full flex items-center justify-center shrink-0 mt-0.5",
          isBot ? "bg-violet/10 border border-violet/20" : "bg-cyan/10 border border-cyan/20"
        )}
      >
        {isBot
          ? <Bot className="w-4 h-4 text-violet" />
          : <User className="w-4 h-4 text-cyan" />
        }
      </div>
      <div
        className={clsx(
          "max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed",
          isBot
            ? "bg-surface border border-border text-text rounded-tl-sm"
            : "bg-cyan/10 border border-cyan/20 text-text rounded-tr-sm"
        )}
      >
        {isBot && (
          <div className="flex items-center gap-1.5 mb-2">
            <Sparkles className="w-3 h-3 text-violet" />
            <span className="text-xs text-violet font-medium uppercase tracking-wider">Football AI</span>
          </div>
        )}
        <div className="whitespace-pre-wrap">{msg.content}</div>
        <div className="text-xs text-muted mt-2 text-right">
          {msg.timestamp.toLocaleTimeString("es", { hour: "2-digit", minute: "2-digit" })}
        </div>
      </div>
    </motion.div>
  )
}

function TypingIndicator() {
  return (
    <div className="flex gap-3">
      <div className="w-8 h-8 rounded-full bg-violet/10 border border-violet/20 flex items-center justify-center shrink-0">
        <Bot className="w-4 h-4 text-violet" />
      </div>
      <div className="bg-surface border border-border rounded-2xl rounded-tl-sm px-4 py-3">
        <div className="flex gap-1">
          {[0, 1, 2].map(i => (
            <motion.div
              key={i}
              className="w-2 h-2 rounded-full bg-violet"
              animate={{ y: [0, -6, 0] }}
              transition={{ duration: 0.6, delay: i * 0.1, repeat: Infinity }}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

export function AIChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content: "¡Hola! Soy Football AI Analytics. Puedo responderte preguntas sobre predicciones, equipos, modelos probabilísticos y estadísticas futbolísticas. ¿En qué te ayudo?",
      timestamp: new Date(),
    },
  ])
  const [input, setInput] = useState("")
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  const { mutate: sendMsg, isPending } = useMutation({
    mutationFn: (text: string) =>
      sendChatMessage(text, messages.map(m => ({ role: m.role, content: m.content }))),
    onSuccess: (data, text) => {
      setMessages(prev => [
        ...prev,
        {
          id: Date.now().toString(),
          role: "assistant",
          content: data.response,
          timestamp: new Date(),
        },
      ])
    },
    onError: (err) => {
      setMessages(prev => [
        ...prev,
        {
          id: Date.now().toString(),
          role: "assistant",
          content: `Lo siento, hubo un error al procesar tu pregunta: ${String(err)}`,
          timestamp: new Date(),
        },
      ])
    },
  })

  function handleSend(text?: string) {
    const msg = (text ?? input).trim()
    if (!msg || isPending) return

    setMessages(prev => [
      ...prev,
      { id: Date.now().toString(), role: "user", content: msg, timestamp: new Date() },
    ])
    setInput("")
    sendMsg(msg)
  }

  return (
    <div className="flex flex-col h-[calc(100vh-120px)] animate-fade-in">
      {/* Header */}
      <div className="card mb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-violet/10 border border-violet/20 flex items-center justify-center">
            <Bot className="w-5 h-5 text-violet" />
          </div>
          <div>
            <h2 className="font-display text-xl tracking-wider text-text">FOOTBALL AI CHAT</h2>
            <p className="text-xs text-muted">Consulta directamente el motor analítico</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1.5 text-xs text-emerald">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald animate-pulse" />
            Online
          </span>
          <button
            onClick={() => setMessages([{
              id: "welcome",
              role: "assistant",
              content: "Conversación reiniciada. ¿En qué te ayudo?",
              timestamp: new Date(),
            }])}
            className="btn-ghost p-2"
            title="Limpiar chat"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 px-1 pb-4">
        <AnimatePresence>
          {messages.map(msg => (
            <MessageBubble key={msg.id} msg={msg} />
          ))}
          {isPending && <TypingIndicator />}
        </AnimatePresence>
        <div ref={bottomRef} />
      </div>

      {/* Suggestions */}
      {messages.length <= 2 && (
        <div className="mb-3">
          <p className="text-xs text-muted mb-2 uppercase tracking-wider">Sugerencias</p>
          <div className="flex flex-wrap gap-2">
            {SUGGESTIONS.map(s => (
              <button
                key={s}
                onClick={() => handleSend(s)}
                disabled={isPending}
                className="text-xs bg-surface border border-border hover:border-violet/40 hover:text-violet text-muted px-3 py-1.5 rounded-full transition-all"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <div className="card flex items-center gap-3">
        <input
          ref={inputRef}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && !e.shiftKey && handleSend()}
          placeholder="Pregunta algo sobre el fútbol, predicciones o modelos..."
          className="flex-1 bg-transparent border-none outline-none text-sm text-text placeholder:text-muted"
          disabled={isPending}
        />
        <button
          onClick={() => handleSend()}
          disabled={!input.trim() || isPending}
          className={clsx(
            "w-9 h-9 rounded-lg flex items-center justify-center transition-all",
            input.trim() && !isPending
              ? "bg-violet hover:bg-violet/80 text-white"
              : "bg-muted/10 text-muted cursor-not-allowed"
          )}
        >
          {isPending
            ? <RefreshCw className="w-4 h-4 animate-spin" />
            : <Send className="w-4 h-4" />
          }
        </button>
      </div>
    </div>
  )
}

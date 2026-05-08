'use client';

import { useState, useRef, useEffect } from 'react';
import { parse } from 'marked';

type Message = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  status?: string;
  sources?: {
    url: string;
    title: string;
    time_ago?: string;
    trust_score?: number;
    verification_status?: string;
  }[];
  accuracy?: {
    accuracy_score: number;
    confidence_level: string;
    recommendation: string;
    validated_claims: { claim: string; source_count: number }[];
  };
  isStreaming?: boolean;
  generatedAt?: string;
  tokenUsage?: {
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
    total_cost: number;
  };
};

export default function Home() {
  const [query, setQuery] = useState('');
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: "Hello! I am an AI agent with access to live web search. Ask me anything, and I'll search the web, read the best articles, and give you a beautifully formatted answer with verified sources."
    }
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: query
    };

    const assistantMessageId = (Date.now() + 1).toString();
    const assistantMessage: Message = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      status: 'Starting agent...',
      isStreaming: true
    };

    setMessages(prev => [...prev, userMessage, assistantMessage]);
    setQuery('');
    setIsLoading(true);

    try {
      const response = await fetch(`http://localhost:8000/api/chat_stream?query=${encodeURIComponent(userMessage.content)}&no_cache=true`);

      if (!response.body) throw new Error("No response body");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        let boundary = buffer.indexOf('\n\n');
        while (boundary !== -1) {
          const chunk = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);

          if (chunk.startsWith('data: ')) {
            try {
              const data = JSON.parse(chunk.slice(6));

              setMessages(prev => prev.map(msg => {
                if (msg.id === assistantMessageId) {
                  if (data.type === 'status') {
                    return { ...msg, status: data.content };
                  } else if (data.type === 'chunk') {
                    return { ...msg, content: msg.content + data.content, status: '' };
                  } else if (data.type === 'error') {
                    return { ...msg, status: '❌ Agent Error: ' + data.content, isStreaming: false };
                  } else if (data.type === 'done') {
                    const sources = data.result?.results?.slice(0, 10)?.map((r: any) => ({
                      url: r.url,
                      title: r.title,
                      time_ago: r.time_ago || 'Recently',
                      trust_score: r.source_trust || r.trust_score,
                      verification_status: r.verification_status
                    })) || data.sources || [];

                    const fallbackContent = (!msg.content && data.result?.analysis) ? data.result.analysis : msg.content;
                    const generatedAt = data.result?.timestamp ? new Date(data.result.timestamp).toLocaleString() : new Date().toLocaleString();
                    const accuracy = data.result?.accuracy;

                    const tu = data.result?.token_usage || {};
                    const du = data.result?.discovery_token_usage || {};
                    const tokenUsage = {
                      input_tokens: (tu.input_tokens || 0) + (du.input_tokens || 0),
                      output_tokens: (tu.output_tokens || 0) + (du.output_tokens || 0),
                      total_tokens: (tu.total_tokens || 0) + (du.total_tokens || 0),
                      total_cost: (tu.total_cost || 0) + (du.total_cost || 0),
                    };

                    return {
                      ...msg,
                      content: fallbackContent,
                      sources,
                      accuracy,
                      isStreaming: false,
                      status: '',
                      generatedAt,
                      tokenUsage
                    };
                  }
                }
                return msg;
              }));
            } catch (err) {
              console.error('JSON parse error:', err);
            }
          }
          boundary = buffer.indexOf('\n\n');
        }
      }
    } catch (error: any) {
      setMessages(prev => prev.map(msg =>
        msg.id === assistantMessageId
          ? { ...msg, status: '❌ Network Error: ' + error.message, isStreaming: false }
          : msg
      ));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-slate-200 font-sans selection:bg-cyan-500/30">
      {/* Premium Header */}
      <header className="sticky top-0 z-10 backdrop-blur-md bg-slate-950/60 border-b border-slate-800/50 p-4 shadow-sm">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-cyan-400 to-blue-500 flex items-center justify-center shadow-lg shadow-cyan-500/20">
              <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
            <h1 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 to-blue-400">
              Nexus Search
            </h1>
          </div>
          <div className="text-xs font-medium px-3 py-1 rounded-full bg-slate-800/50 text-slate-400 border border-slate-700/50">
            High Accuracy Agent
          </div>
        </div>
      </header>

      {/* Main Chat Area */}
      <main className="flex-1 overflow-y-auto p-4 sm:p-6 scroll-smooth">
        <div className="max-w-4xl mx-auto flex flex-col gap-6 pb-4">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex w-full ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-in fade-in slide-in-from-bottom-4 duration-500`}
            >
              <div
                className={`flex flex-col max-w-[90%] sm:max-w-[85%] rounded-2xl p-5 sm:p-6 shadow-xl ${
                  msg.role === 'user'
                    ? 'bg-gradient-to-br from-blue-600 to-cyan-600 text-white rounded-tr-sm border border-blue-500/30 shadow-blue-900/20'
                    : 'bg-slate-800/60 backdrop-blur-sm text-slate-200 rounded-tl-sm border border-slate-700/50 shadow-slate-950/50'
                }`}
              >
                {/* Assistant Header / Status */}
                {msg.role === 'assistant' && (
                  <div className="flex items-center gap-3 mb-4 border-b border-slate-700/50 pb-3">
                    <div className="w-6 h-6 rounded-full bg-gradient-to-tr from-cyan-500 to-blue-500 flex items-center justify-center shrink-0">
                      <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                      </svg>
                    </div>
                    <div className="flex-1 flex flex-wrap items-center gap-2 justify-between">
                      {msg.status ? (
                        <div className={`text-sm font-medium flex items-center ${msg.status.includes('❌') ? 'text-red-400' : 'text-cyan-400'}`}>
                          {!msg.status.includes('❌') && (
                            <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-cyan-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                          )}
                          {msg.status}
                        </div>
                      ) : (
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-semibold text-slate-300">Verified Answer</span>
                          {msg.accuracy && (
                            <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                              msg.accuracy.accuracy_score >= 90 ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' :
                              msg.accuracy.accuracy_score >= 70 ? 'bg-amber-500/10 text-amber-400 border-amber-500/20' :
                              'bg-red-500/10 text-red-400 border-red-500/20'
                            }`}>
                              {msg.accuracy.confidence_level.split(' - ')[0]}
                            </span>
                          )}
                        </div>
                      )}
                      <div className="flex items-center gap-2">
                        {msg.tokenUsage && (
                          <span className="inline-flex items-center gap-1 text-[10px] text-slate-400 bg-slate-900/80 px-2 py-0.5 rounded-full border border-slate-700/50">
                            Tokens: <b className="text-cyan-400">{msg.tokenUsage.total_tokens}</b>
                            <span className="mx-1 text-slate-700">|</span>
                            Cost: <b className="text-emerald-400">${msg.tokenUsage.total_cost.toFixed(4)}</b>
                          </span>
                        )}
                        {msg.generatedAt && (
                          <span className="inline-flex items-center gap-1 text-[10px] text-slate-500 bg-slate-900/50 px-2 py-0.5 rounded-full border border-slate-700/50">
                            {msg.generatedAt}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                )}


                {/* Message Content */}
                <div
                  className={`markdown-body ${msg.role === 'user' ? 'text-white' : 'text-slate-200'} prose prose-invert max-w-none prose-p:leading-relaxed prose-pre:bg-slate-900/50 prose-pre:border prose-pre:border-slate-700/50 prose-a:text-cyan-400 hover:prose-a:text-cyan-300`}
                  dangerouslySetInnerHTML={{ __html: parse(msg.content) as string }}
                />

                {/* Blinking Cursor for Streaming */}
                {msg.isStreaming && !msg.status && (
                  <span className="inline-block w-2.5 h-5 bg-cyan-400 animate-pulse ml-1 align-middle rounded-sm shadow-[0_0_8px_rgba(34,211,238,0.6)]" />
                )}

                {/* Sources Area */}
                {msg.sources && msg.sources.length > 0 && (
                  <div className="mt-6 pt-5 border-t border-slate-700/50">
                    <div className="flex items-center gap-2 mb-3 text-slate-300 font-medium">
                      <svg className="w-4 h-4 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9.5a2.5 2.5 0 00-2.5-2.5H14" />
                      </svg>
                      Verified Sources
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      {msg.sources.map((s, i) => (
                        <a
                          key={i}
                          href={s.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="group flex flex-col p-3 rounded-xl bg-slate-900/40 border border-slate-700/50 hover:bg-slate-800/80 hover:border-cyan-500/50 transition-all duration-300"
                        >
                          <div className="flex items-center justify-between gap-2 mb-1">
                            <span className="text-xs font-bold text-slate-500 uppercase tracking-tighter">
                              {new URL(s.url).hostname.replace('www.', '')}
                            </span>
                            {s.trust_score !== undefined && (
                              <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-bold ${
                                s.trust_score >= 0.9 ? 'bg-emerald-500/20 text-emerald-400' :
                                s.trust_score >= 0.8 ? 'bg-cyan-500/20 text-cyan-400' :
                                'bg-slate-700 text-slate-400'
                              }`}>
                                {(s.trust_score * 100).toFixed(0)}% Trust
                              </span>
                            )}
                          </div>
                          <span className="text-sm font-medium text-slate-200 group-hover:text-cyan-400 line-clamp-1 transition-colors">
                            {s.title}
                          </span>
                          <div className="flex items-center justify-between mt-2 gap-2">
                            <div className="flex items-center gap-1.5">
                              {s.verification_status === 'verified_indicator' && (
                                <span className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-cyan-500/20 text-cyan-400">
                                  <svg className="w-2.5 h-2.5" fill="currentColor" viewBox="0 0 20 20"><path d="M6.267 3.455a3.066 3.066 0 001.745-.723 3.066 3.066 0 013.976 0 3.066 3.066 0 001.745.723 3.066 3.066 0 012.812 2.812c.051.643.304 1.254.723 1.745a3.066 3.066 0 010 3.976 3.066 3.066 0 00-.723 1.745 3.066 3.066 0 01-2.812 2.812 3.066 3.066 0 00-1.745.723 3.066 3.066 0 01-3.976 0 3.066 3.066 0 00-1.745-.723 3.066 3.066 0 01-2.812-2.812 3.066 3.066 0 00-.723-1.745 3.066 3.066 0 010-3.976 3.066 3.066 0 00.723-1.745 3.066 3.066 0 012.812-2.812zm7.44 5.252a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"></path></svg>
                                </span>
                              )}
                              <span className="text-[10px] text-slate-500 group-hover:text-slate-400">
                                {s.time_ago}
                              </span>
                            </div>
                            <svg className="w-3 h-3 text-slate-600 group-hover:text-cyan-500 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                            </svg>
                          </div>
                        </a>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
          <div ref={chatEndRef} className="h-4" />
        </div>
      </main>

      {/* Input Area */}
      <footer className="p-4 sm:p-6 bg-gradient-to-t from-slate-950 via-slate-950 to-transparent">
        <div className="max-w-4xl mx-auto">
          <form onSubmit={handleSubmit} className="relative flex items-center">
            <div className="absolute inset-0 bg-gradient-to-r from-cyan-500 to-blue-500 rounded-2xl blur opacity-20 transition-opacity duration-500"></div>
            <div className="relative flex w-full items-center bg-slate-900/80 backdrop-blur-xl border border-slate-700/50 focus-within:border-cyan-500/50 focus-within:ring-1 focus-within:ring-cyan-500/50 rounded-2xl shadow-2xl transition-all duration-300">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Ask anything..."
                required
                autoComplete="off"
                disabled={isLoading}
                className="w-full py-4 pl-6 pr-20 bg-transparent text-slate-100 placeholder-slate-400 text-base outline-none disabled:opacity-50"
              />
              <button
                type="submit"
                disabled={isLoading || !query.trim()}
                className="absolute right-2 p-2.5 bg-cyan-500 hover:bg-cyan-400 text-white rounded-xl disabled:opacity-50 disabled:hover:bg-cyan-500 transition-all duration-200 shadow-lg shadow-cyan-500/20"
              >
                <svg className="w-5 h-5 translate-x-[1px] translate-y-[-1px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
              </button>
            </div>
          </form>
          <div className="text-center mt-3 text-xs text-slate-500 font-medium">
            Results are generated by AI and may vary.
          </div>
        </div>
      </footer>
    </div>
  );
}

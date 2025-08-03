
import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ArrowRight, MessageCircle, Heart, MessageSquare, HelpCircle, Plus } from "lucide-react";
import UserMenu from "@/components/UserMenu";
import { chatAPI } from "@/apis/api";
import { type Conversation } from "@/apis/wire";

const Index = () => {
  const [query, setQuery] = useState("");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [isLoadingConversations, setIsLoadingConversations] = useState(true);
  const navigate = useNavigate();

  // Fetch conversations on component mount
  useEffect(() => {
    const fetchConversations = async () => {
      try {
        setIsLoadingConversations(true);
        const response = await chatAPI.getConversations();
        setConversations(response.conversations);
      } catch (error) {
        console.error("Failed to fetch conversations:", error);
        // Fallback to empty array if fetch fails
        setConversations([]);
      } finally {
        setIsLoadingConversations(false);
      }
    };

    fetchConversations();
  }, []);


  const handleSend = async () => {
    if (query.trim()) {
      try {
        // 1. Create a new conversation
        const conversation = await chatAPI.createConversation({ messages: [] });

        // 2. Navigate to the chat with the conversation ID and initial query
        navigate(`/chat/${conversation.id}`, { state: { initialQuery: query } });
      } catch (error) {
        console.error("Failed to create conversation:", error);
        // Fallback to the previous behavior if conversation creation fails
        navigate("/chat", { state: { initialQuery: query } });
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleSend();
    }
  };

  const handleChatClick = (conversationId: string) => {
    navigate(`/chat/${conversationId}`);
  };

  const handleQuickPrompt = async (prompt: string) => {
    try {
      // 1. Create a new conversation
      const conversation = await chatAPI.createConversation({ messages: [] });

      // 2. Navigate to the chat with the conversation ID and initial query (if any)
      if (prompt.trim()) {
        navigate(`/chat/${conversation.id}`, { state: { initialQuery: prompt } });
      } else {
        // For empty prompts (like "New Chat"), just navigate without any initial query
        navigate(`/chat/${conversation.id}`);
      }
    } catch (error) {
      console.error("Failed to create conversation:", error);
      // Fallback to the previous behavior if conversation creation fails
      if (prompt.trim()) {
        navigate("/chat", { state: { initialQuery: prompt } });
      } else {
        navigate("/chat");
      }
    }
  };

  // Quick prompt options
  const quickPrompts = [
    {
      icon: <Heart className="w-4 h-4" />,
      label: "Today's Meditation",
      prompt: "What is the importance of self control?"
    },
    {
      icon: <MessageSquare className="w-4 h-4" />,
      label: "Share thoughts",
      prompt: "Share some thoughts of Bhagavan Ramana Maharshi about wisdom."
    },
    {
      icon: <HelpCircle className="w-4 h-4" />,
      label: "Resolve confusion",
      prompt: "What are some ways to reduce confusion?"
    },
    {
      icon: <Plus className="w-4 h-4" />,
      label: "New Chat",
      prompt: ""
    }
  ];

  // Helper function to format date
  const formatTimestamp = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffInMs = now.getTime() - date.getTime();
    const diffInDays = Math.floor(diffInMs / (1000 * 60 * 60 * 24));
    const diffInHours = Math.floor(diffInMs / (1000 * 60 * 60));
    const diffInWeeks = Math.floor(diffInDays / 7);

    if (diffInHours < 1) {
      return "Just now";
    } else if (diffInHours < 24) {
      return `${diffInHours} hour${diffInHours === 1 ? '' : 's'} ago`;
    } else if (diffInDays === 1) {
      return "1 day ago";
    } else if (diffInDays < 7) {
      return `${diffInDays} days ago`;
    } else if (diffInWeeks === 1) {
      return "1 week ago";
    } else if (diffInWeeks < 4) {
      return `${diffInWeeks} weeks ago`;
    } else {
      const diffInMonths = Math.floor(diffInDays / 30);
      return `${diffInMonths} month${diffInMonths === 1 ? '' : 's'} ago`;
    }
  };

  return (
    <div className="min-h-screen flex items-start justify-center p-4 pt-16" style={{ backgroundColor: 'rgb(236, 229, 223)' }}>
      <div className="w-full max-w-6xl mx-auto">
        {/* User Menu in top right */}
        <div className="flex justify-end mb-8">
          <UserMenu />
        </div>

        <div className="text-center mb-16">
          <h1 className="text-6xl font-heading text-brand-heading mb-8">
            Mindful AI
          </h1>
        </div>

        {/* Quick Prompts */}
        <div className="max-w-2xl mx-auto mb-12">
          <div className="flex flex-wrap justify-center gap-3">
            {quickPrompts.map((prompt, index) => (
              <Button
                key={index}
                onClick={() => handleQuickPrompt(prompt.prompt)}
                variant="outline"
                className="flex items-center gap-2 px-4 py-2 rounded-full bg-white/80 hover:bg-white border-gray-200 text-brand-body font-body transition-all duration-200 hover:scale-105 hover:border-brand-button"
              >
                {prompt.icon}
                {prompt.label}
              </Button>
            ))}
          </div>
        </div>

        {/* Previous Chats Section */}
        <div className="max-w-4xl mx-auto">
          {isLoadingConversations ? (
            <div className="text-center py-8">
              <p className="text-brand-body font-body">Loading conversations...</p>
            </div>
          ) : conversations.length === 0 ? (
            <div className="text-center py-8">
              <h2 className="text-2xl font-heading text-brand-heading mb-4">No conversations</h2>
              <p className="text-brand-body font-body">Start a new conversation above!</p>
            </div>
          ) : (
            <>
              <h2 className="text-2xl font-heading text-brand-heading mb-6 text-center">Previous Conversations</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {conversations.map((conversation) => (
                  <div
                    key={conversation.id}
                    onClick={() => handleChatClick(conversation.id)}
                    className="bg-white rounded-2xl p-6 shadow-md hover:shadow-lg transition-all duration-200 cursor-pointer hover:scale-105 border border-gray-100 hover:border-brand-button"
                  >
                    <div className="flex items-start gap-3">
                      <div className="bg-orange-100 rounded-full p-2 flex-shrink-0">
                        <MessageCircle className="w-5 h-5 text-brand-button" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <h3 className="font-medium font-heading text-brand-heading mb-2 truncate">
                          {conversation.title || "Untitled Conversation"}
                        </h3>
                        <p className="text-sm text-brand-body mb-3 line-clamp-2 font-body">
                          Click to continue this conversation...
                        </p>
                        <span className="text-xs text-gray-400 font-body">
                          {formatTimestamp(conversation.created_at)}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default Index;

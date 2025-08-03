import { useState, useEffect, useCallback } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Pencil, Save, Volume2, Mic, ArrowRight } from "lucide-react";
import ChatMessage from "@/components/ChatMessage";
import ExploreMore from "@/components/ExploreMore";
import ContemplationModal from "@/components/ContemplationModal";
import InlineMeditationCreator from "@/components/InlineMeditationCreator";
import UserMenu from "@/components/UserMenu";
import { chatAPI } from "@/apis/api";
import type { Message as APIMessage, Conversation, ConversationDetailResponse, ContentGeneration } from "@/apis/wire";

interface Message {
  id: string;
  content: string;
  isUser: boolean;
  thinking?: string;
  citations?: { name: string; url: string; }[];
  mediaUrl?: string;
  mediaType?: "audio" | "video";
}

const Chat = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { conversationId } = useParams<{ conversationId: string }>();
  const [messages, setMessages] = useState<Message[]>([]);
  const [currentInput, setCurrentInput] = useState("");
  const [isThinking, setIsThinking] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [showExploreMore, setShowExploreMore] = useState(false);
  const [showContemplation, setShowContemplation] = useState(false);
  const [showMeditationCreator, setShowMeditationCreator] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [title, setTitle] = useState("New Conversation");
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [conversationDetail, setConversationDetail] = useState<ConversationDetailResponse | null>(null);
  const [questions, setQuestions] = useState<string[]>([]);
  const [isLoadingConversation, setIsLoadingConversation] = useState(false);
  const [hasProcessedInitialQuery, setHasProcessedInitialQuery] = useState(false);

  const loadConversationData = useCallback(async () => {
    if (conversationId) {
      setIsLoadingConversation(true);
      try {
        // Load existing conversation from API
        const response = await chatAPI.getConversation(conversationId);
        setConversationDetail(response);
        setTitle(response.conversation.title || "Untitled Conversation");

        // Convert API messages to local message format
        const convertedMessages: Message[] = response.messages.map((msg: APIMessage) => ({
          id: msg.id,
          content: msg.content,
          isUser: msg.role === 'user',
          citations: msg.citations || [],
        }));
        setMessages(convertedMessages);

        // Extract follow-up questions from the latest assistant message that has them
        const latestAssistantMessageWithQuestions = response.messages
          .filter((msg: APIMessage) => msg.role === 'assistant' && msg.follow_up_questions?.questions?.length)
          .pop();

        if (latestAssistantMessageWithQuestions?.follow_up_questions?.questions) {
          setQuestions(latestAssistantMessageWithQuestions.follow_up_questions.questions);
        }
      } catch (error) {
        console.error("Failed to load conversation:", error);
      } finally {
        setIsLoadingConversation(false);
      }
    }
  }, [conversationId]);

  useEffect(() => {
    loadConversationData();
  }, [loadConversationData]);

  const handleSendMessage = useCallback(async (message: string) => {
    if (!conversationId) {
      console.error("No conversation ID available");
      return;
    }

    const userMessage: Message = {
      id: Date.now().toString(),
      content: message,
      isUser: true,
    };

    setMessages(prev => [...prev, userMessage]);
    setCurrentInput("");
    setIsThinking(true);

    // Create a placeholder AI message for streaming
    const aiMessageId = `ai-${Date.now()}`;
    const aiMessage: Message = {
      id: aiMessageId,
      content: "",
      isUser: false,
      citations: [],
    };

    // Add the empty AI message that we'll update during streaming
    setMessages(prev => [...prev, aiMessage]);
    setIsThinking(false);
    setIsStreaming(true);

    try {
      // Send message to the conversation with streaming
      const response = await chatAPI.chatCompletion(
        conversationId,
        {
          message: message,
          stream: true,
          mock: false,
        },
        // onChunk callback for streaming updates
        (streamingContent: string) => {
          setMessages(prev => prev.map(msg =>
            msg.id === aiMessageId
              ? { ...msg, content: streamingContent }
              : msg
          ));
        }
      );

      setIsStreaming(false);

      // Final update with complete response data
      setMessages(prev => prev.map(msg =>
        msg.id === aiMessageId
          ? {
            ...msg,
            id: response.message_id || aiMessageId,
            content: response.message,
            citations: response.citations || [],
          }
          : msg
      ));

      // Store questions for explore more functionality
      if (response.questions && response.questions.length > 0) {
        setQuestions(response.questions);
      }

      // Update conversation title if it was generated
      if (response.title && (!conversationDetail?.conversation.title || conversationDetail.conversation.title === "New Conversation")) {
        setTitle(response.title);
        if (conversationDetail) {
          setConversationDetail({
            ...conversationDetail,
            conversation: { ...conversationDetail.conversation, title: response.title }
          });
        }
      }
    } catch (error) {
      console.error("Failed to send message:", error);
      setIsThinking(false);
      setIsStreaming(false);

      // Replace the placeholder message with an appropriate error message
      let errorMessage = "Sorry, I encountered an error while processing your message. Please try again.";

      if (error instanceof Error) {
        if (error.message.includes('Network')) {
          errorMessage = "Network error. Please check your connection and try again.";
        } else if (error.message.includes('401')) {
          errorMessage = "Authentication error. Please sign in again.";
        } else if (error.message.includes('timeout')) {
          errorMessage = "Request timed out. Please try again.";
        }
      }

      setMessages(prev => prev.map(msg =>
        msg.id === aiMessageId
          ? {
            ...msg,
            content: errorMessage
          }
          : msg
      ));
    }
  }, [conversationId]);

  // Handle initial query from navigation state
  useEffect(() => {
    const initialQuery = location.state?.initialQuery;
    if (initialQuery && conversationId && !hasProcessedInitialQuery && !isLoadingConversation) {
      setHasProcessedInitialQuery(true);
      // Instead of sending immediately, put the query in the input field
      if (initialQuery.trim()) {
        setCurrentInput(initialQuery.trim());
      }
      // Clear the navigation state to prevent re-processing on page refresh
      navigate(location.pathname, { replace: true, state: {} });
    }
  }, [conversationId, location.state?.initialQuery, hasProcessedInitialQuery, isLoadingConversation, location.pathname, navigate]);

  const handleTitleSave = async () => {
    if (conversationId && title.trim() !== (conversationDetail?.conversation.title || "")) {
      try {
        await chatAPI.updateConversationTitle(conversationId, title.trim());
        if (conversationDetail) {
          setConversationDetail({
            ...conversationDetail,
            conversation: { ...conversationDetail.conversation, title: title.trim() }
          });
        }
      } catch (error) {
        console.error("Failed to update title:", error);
        // Revert title on error
        setTitle(conversationDetail?.conversation.title || "Untitled Conversation");
      }
    }
    setIsEditingTitle(false);
  };

  const handleMicClick = () => {
    setIsRecording(!isRecording);
    if (!isRecording) {
      setTimeout(() => {
        setCurrentInput("How can I practice mindfulness in daily life?");
        setIsRecording(false);
      }, 2000);
    }
  };

  const handleExploreMore = () => {
    // Close other modals first
    setShowContemplation(false);
    setShowMeditationCreator(false);
    setShowExploreMore(!showExploreMore);
  };

  const handleMeditationGuide = () => {
    // Close other modals first
    setShowContemplation(false);
    setShowExploreMore(false);
    setShowMeditationCreator(!showMeditationCreator);
  };

  const generateContemplationCard = () => {
    // Close other modals first
    setShowExploreMore(false);
    setShowMeditationCreator(false);
    setShowContemplation(true);
  };

  const handleNewChat = () => {
    navigate("/");
  };

  return (
    <div className="min-h-screen bg-white flex flex-col">
      {/* Header */}
      <div className="p-6 bg-gradient-to-b from-white to-transparent">
        <div className="flex justify-between items-start">
          {/* Left spacer - invisible but takes up space */}
          <div className="flex items-center gap-3 opacity-0 pointer-events-none">
            <Button variant="outline" className="rounded-lg">
              <Pencil className="w-4 h-4 mr-2" />
              New Chat
            </Button>
            <UserMenu />
          </div>

          {/* Centered Title */}
          <div className="group flex items-center gap-2 absolute left-1/2 transform -translate-x-1/2">
            {isEditingTitle ? (
              <>
                <Input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="text-4xl font-light text-brand-heading h-auto p-0 border-none focus-visible:ring-0 bg-transparent shadow-none text-4xl text-center"
                  style={{ fontSize: 'inherit', lineHeight: 'inherit' }}
                  autoFocus
                  onBlur={() => handleTitleSave()}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      handleTitleSave();
                    }
                  }}
                />
                <Button onClick={() => handleTitleSave()} variant="ghost" size="icon" className="h-9 w-9 shrink-0">
                  <Save className="w-5 h-5 text-gray-500" />
                </Button>
              </>
            ) : (
              <>
                <h1 className="text-4xl font-light text-brand-heading text-center">
                  {title}
                </h1>
                <Button onClick={() => setIsEditingTitle(true)} variant="ghost" size="icon" className="h-9 w-9 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                  <Pencil className="w-5 h-5 text-gray-500" />
                </Button>
              </>
            )}
          </div>

          {/* Right side controls */}
          <div className="flex items-center gap-3">
            <Button onClick={handleNewChat} variant="outline" className="rounded-lg">
              <Pencil className="w-4 h-4 mr-2" />
              New Chat
            </Button>
            <UserMenu />
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 max-w-4xl mx-auto w-full">
        {isLoadingConversation && (
          <div className="mb-6">
            <div className="text-brand-button text-sm mb-2">Loading conversation...</div>
            <div className="animate-pulse h-4 bg-orange-200 rounded w-1/2"></div>
          </div>
        )}

        {!isLoadingConversation && messages.map((message, index) => {
          // Find the index of the latest assistant message
          const latestAssistantMessageIndex = messages.map((msg, idx) => ({ msg, idx }))
            .filter(({ msg }) => !msg.isUser)
            .pop()?.idx;

          return (
            <ChatMessage
              key={message.id}
              message={message}
              isStreaming={isStreaming && !message.isUser && index === messages.length - 1}
              showFeedback={!message.isUser && index === latestAssistantMessageIndex}
            />
          );
        })}

        {isThinking && (
          <div className="mb-6">
            <div className="text-brand-button text-sm mb-2">thinking...</div>
            <div className="animate-pulse h-4 bg-orange-200 rounded w-3/4"></div>
          </div>
        )}

        {isStreaming && !isThinking && (
          <div className="mb-6">
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 bg-brand-button rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
              <div className="w-2 h-2 bg-brand-button rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
              <div className="w-2 h-2 bg-brand-button rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
            </div>
          </div>
        )}

        {/* Inline Modals */}
        <ExploreMore
          isOpen={showExploreMore}
          onClose={() => setShowExploreMore(false)}
          onSelectQuestion={(question) => {
            setCurrentInput(question);
            setShowExploreMore(false);
          }}
          questions={questions}
          inline={true}
        />

        <InlineMeditationCreator
          isOpen={showMeditationCreator}
          onClose={() => setShowMeditationCreator(false)}
          conversationId={conversationId}
          messageId={messages.filter(msg => !msg.isUser).pop()?.id}
          existingContentGenerations={conversationDetail?.content_generations?.filter(cg => cg.content_type === 'audio' || cg.content_type === 'video') || []}
        />
      </div>

      {/* Input - positioned based on message state */}
      {messages.length === 0 ? (
        // Centered input when no messages
        <div className="flex-1 flex items-center justify-center p-6">
          <div className="relative max-w-2xl w-full mx-auto">
            <Input
              value={currentInput}
              onChange={(e) => setCurrentInput(e.target.value)}
              onKeyPress={(e) => e.key === "Enter" && handleSendMessage(currentInput)}
              placeholder="Enter your query..."
              className="text-lg py-6 pr-32 pl-6 rounded-2xl border-2 border-gray-200 shadow-lg focus:border-brand-button transition-all duration-500 font-body bg-white"
            />
            <div className="absolute right-2 top-1/2 transform -translate-y-1/2 flex gap-2">
              <Button
                onClick={() => handleSendMessage(currentInput)}
                variant="ghost"
                size="sm"
                className="rounded-full w-8 h-8 bg-brand-button text-white hover:bg-brand-button/90"
              >
                <ArrowRight className="w-5 h-5" />
              </Button>
            </div>
          </div>
        </div>
      ) : (
        // Bottom input with action buttons when messages exist
        <div className="border-t border-gray-200 p-6 transition-all duration-500 ease-in-out">
          <div className="max-w-4xl mx-auto">
            {/* Action Buttons with fade-in animation */}
            <div className="mb-4 flex flex-wrap justify-center gap-3 animate-in fade-in duration-500">
              <Button
                onClick={handleExploreMore}
                variant="outline"
                className="rounded-full text-brand-body border-brand-button hover:bg-brand-button hover:text-white transition-colors"
              >
                {showExploreMore ? 'Close explore' : 'Explore more'}
              </Button>
              <Button
                onClick={generateContemplationCard}
                variant="outline"
                className="rounded-full text-brand-body border-brand-button hover:bg-brand-button hover:text-white transition-colors"
              >
                Make contemplation card
              </Button>
              <Button
                onClick={handleMeditationGuide}
                variant="outline"
                className="rounded-full text-brand-body border-brand-button hover:bg-brand-button hover:text-white transition-colors"
              >
                {showMeditationCreator ? 'Close meditation' : 'Meditation Guide'}
              </Button>
            </div>

            <div className="relative max-w-2xl mx-auto">
              <Input
                value={currentInput}
                onChange={(e) => setCurrentInput(e.target.value)}
                onKeyPress={(e) => e.key === "Enter" && handleSendMessage(currentInput)}
                placeholder="Enter your query..."
                className="text-lg py-6 pr-32 pl-6 rounded-2xl border-2 border-gray-200 shadow-lg focus:border-brand-button transition-all duration-500 font-body bg-white"
              />
              <div className="absolute right-2 top-1/2 transform -translate-y-1/2 flex gap-2">
                <Button
                  onClick={() => handleSendMessage(currentInput)}
                  variant="ghost"
                  size="sm"
                  className="rounded-full w-8 h-8 bg-brand-button text-white hover:bg-brand-button/90"
                >
                  <ArrowRight className="w-5 h-5" />
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Full Screen Modals */}
      <ContemplationModal
        isOpen={showContemplation}
        onClose={() => setShowContemplation(false)}
        conversationId={conversationId}
        messageId={messages.filter(msg => !msg.isUser).pop()?.id}
        existingContentGenerations={conversationDetail?.content_generations?.filter(cg => cg.content_type === 'image') || []}
        onContentGenerated={() => loadConversationData()}
      />
    </div>
  );
};

export default Chat;

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ThumbsUp, ThumbsDown, Volume2, ChevronRight, FileText } from "lucide-react";
import { chatAPI } from "@/apis/api";
import { useParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";

interface CitationInfo {
  name: string;
  url: string;
}

interface Message {
  id: string;
  content: string;
  isUser: boolean;
  thinking?: string;
  citations?: CitationInfo[];
  mediaUrl?: string;
  mediaType?: "audio" | "video";
}

interface ChatMessageProps {
  message: Message;
  isStreaming?: boolean;
  showFeedback?: boolean;
}

const ChatMessage = ({
  message,
  isStreaming = false,
  showFeedback = false,
}: ChatMessageProps) => {
  const [isThinkingExpanded, setIsThinkingExpanded] = useState(false);
  const [thumbsUpClicked, setThumbsUpClicked] = useState(false);
  const [thumbsDownClicked, setThumbsDownClicked] = useState(false);
  const [speakerClicked, setSpeakerClicked] = useState(false);
  const [feedbackSubmitted, setFeedbackSubmitted] = useState<'positive' | 'negative' | null>(null);
  const [isSubmittingFeedback, setIsSubmittingFeedback] = useState(false);

  const { conversationId } = useParams<{ conversationId: string }>();

  const handleSpeak = () => {
    setSpeakerClicked(true);
    setTimeout(() => setSpeakerClicked(false), 300);
    console.log("Speaking:", message.content);
  };

  const handleFeedback = async (type: 'positive' | 'negative') => {
    if (!conversationId || isSubmittingFeedback || feedbackSubmitted) return;

    setIsSubmittingFeedback(true);

    // Visual feedback
    if (type === 'positive') {
      setThumbsUpClicked(true);
      setTimeout(() => setThumbsUpClicked(false), 300);
    } else {
      setThumbsDownClicked(true);
      setTimeout(() => setThumbsDownClicked(false), 300);
    }

    try {
      await chatAPI.submitFeedback(conversationId, {
        message_id: message.id,
        type: type,
        comment: null, // Could be extended later to collect comments
      });

      setFeedbackSubmitted(type);
    } catch (error) {
      console.error('Failed to submit feedback:', error);
      // Could add toast notification here for error handling
    } finally {
      setIsSubmittingFeedback(false);
    }
  };

  const handleThumbsUp = () => handleFeedback('positive');
  const handleThumbsDown = () => handleFeedback('negative');

  const mockThinkingSteps = [
    "Analyzing the narrative structure",
    "Considering character development",
    "Exploring thematic elements",
    "Crafting engaging dialogue",
    "Finalizing the story flow"
  ];

  if (message.isUser) {
    return (
      <div className="mb-6 flex justify-end">
        <div className="max-w-3xl">
          <div className="bg-orange-50 rounded-2xl p-6 relative border border-orange-200">
            <div className="flex justify-between items-start">
              <div className="text-brand-body flex-1 mr-4 font-body">
                <ReactMarkdown>{message.content}</ReactMarkdown>
              </div>
              <div className="flex gap-2">
                {/* <Button
                  onClick={handleSpeak}
                  variant="ghost"
                  size="sm"
                  className={`rounded-full w-8 h-8 p-0 transition-all duration-300 ${speakerClicked ? 'bg-orange-100 scale-110' : ''
                    }`}
                >
                  <Volume2 className="w-4 h-4" />
                </Button> */}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mb-6">
      <div className="max-w-3xl">
        {message.thinking && (
          <div className="mb-2">
            <Button
              onClick={() => setIsThinkingExpanded(!isThinkingExpanded)}
              variant="ghost"
              size="sm"
              className="text-brand-button text-sm p-0 h-auto hover:bg-transparent font-body"
            >
              <span>{message.thinking}</span>
              <ChevronRight className={`w-4 h-4 ml-2 transition-transform ${isThinkingExpanded ? 'rotate-90' : ''}`} />
            </Button>

            {isThinkingExpanded && (
              <div className="mt-3 ml-6 border-l-2 border-orange-200 pl-4 relative">
                {mockThinkingSteps.map((step, index) => (
                  <div key={index} className="flex items-center mb-2 relative">
                    <div className="absolute -left-5 w-2 h-2 bg-brand-button rounded-full border-2 border-white"></div>
                    <span className="text-sm text-brand-body font-body">{step}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="relative">
          <div className="flex justify-between items-start">
            <div className="text-brand-body flex-1 mr-4 leading-relaxed font-body">
              <ReactMarkdown>{message.content}</ReactMarkdown>
              {isStreaming && (
                <span className="inline-block w-2 h-5 bg-brand-button ml-1 animate-pulse"></span>
              )}
            </div>
          </div>
        </div>

        {message.citations && (
          <div className="mt-4">
            {message.citations.map((citation, index) => (
              <a
                key={index}
                href={citation.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center text-sm text-brand-button hover:underline cursor-pointer"
              >
                <FileText className="w-4 h-4 mr-2 shrink-0 text-brand-button" />
                <span className="truncate font-body">{citation.name}</span>
              </a>
            ))}
          </div>
        )}

        <div className="flex gap-2 mt-4">
          {showFeedback && (
            <>
              <Button
                onClick={handleThumbsUp}
                variant="ghost"
                size="sm"
                disabled={isSubmittingFeedback || feedbackSubmitted !== null}
                className={`rounded-full w-8 h-8 p-0 transition-all duration-300 ${thumbsUpClicked || feedbackSubmitted === 'positive'
                  ? 'bg-green-100 text-green-600 scale-110'
                  : feedbackSubmitted === 'negative'
                    ? 'opacity-50'
                    : 'hover:bg-orange-100'
                  } ${isSubmittingFeedback ? 'cursor-wait' : feedbackSubmitted ? 'cursor-not-allowed' : 'cursor-pointer'}`}
              >
                <ThumbsUp className="w-4 h-4" />
              </Button>
              <Button
                onClick={handleThumbsDown}
                variant="ghost"
                size="sm"
                disabled={isSubmittingFeedback || feedbackSubmitted !== null}
                className={`rounded-full w-8 h-8 p-0 transition-all duration-300 ${thumbsDownClicked || feedbackSubmitted === 'negative'
                  ? 'bg-red-100 text-red-600 scale-110'
                  : feedbackSubmitted === 'positive'
                    ? 'opacity-50'
                    : 'hover:bg-orange-100'
                  } ${isSubmittingFeedback ? 'cursor-wait' : feedbackSubmitted ? 'cursor-not-allowed' : 'cursor-pointer'}`}
              >
                <ThumbsDown className="w-4 h-4" />
              </Button>
            </>
          )}
        </div>

        {message.mediaUrl && (
          <div className="mt-4 p-4 bg-gray-50 rounded-lg">
            <p className="text-sm text-brand-body mb-2 font-body">
              I have created a small meditation for you. You can listen to it [here](link)
            </p>
            <div className="flex items-center gap-4">
              <div className="text-brand-button font-medium font-heading">Title of the video clip</div>
              <Button variant="ghost" size="sm">↓</Button>
            </div>
            <div className="bg-gray-200 h-32 rounded mt-2 flex items-center justify-center">
              <span className="text-gray-500 font-body">Media Player</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ChatMessage;

import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Download, Loader2, Eye, X } from "lucide-react";
import BaseModal from "./BaseModal";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { contentAPI } from "@/apis/api";
import type { ContentGeneration } from "@/apis/wire";

interface ContemplationModalProps {
  isOpen: boolean;
  onClose: () => void;
  conversationId?: string;
  messageId?: string;
  existingContentGenerations?: ContentGeneration[];
  onContentGenerated?: () => void;
}

// Custom hook for polling content status
const useContentPolling = (contentId: string | null, shouldPoll: boolean) => {
  const [status, setStatus] = useState<'pending' | 'processing' | 'complete' | 'failed' | null>(null);
  const [contentUrl, setContentUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const pollContent = useCallback(async () => {
    if (!contentId) return;

    try {
      const content = await contentAPI.getContent(contentId);
      setStatus(content.status);
      console.log("content", content);
      console.log("content.status", content.status);

      if (content.status === "complete" && "content_url" in content) {
        setContentUrl(content.content_url);
      } else if (content.status === "failed") {
        setError("Content generation failed");
      }
    } catch (err) {
      console.error("Error polling content:", err);
      setError(err instanceof Error ? err.message : "Failed to check content status");
    }
  }, [contentId]);

  useEffect(() => {
    if (!shouldPoll || !contentId) return;

    // Initial poll
    pollContent();

    // Set up polling interval
    const interval = setInterval(() => {
      pollContent();
    }, 2000); // Poll every second

    // Cleanup
    return () => clearInterval(interval);
  }, [shouldPoll, contentId, pollContent]);

  // Stop polling when complete or failed
  useEffect(() => {
    if (status === 'complete' || status === 'failed') {
      // Polling will stop naturally due to shouldPoll dependency
    }
  }, [status]);

  return { status, contentUrl, error };
};

const ContemplationModal = ({ isOpen, onClose, conversationId, messageId, existingContentGenerations = [], onContentGenerated }: ContemplationModalProps) => {
  const [fullScreen, setFullScreen] = useState(false);
  const [contentId, setContentId] = useState<string | null>(null);
  const [isInitiating, setIsInitiating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentContentUrl, setCurrentContentUrl] = useState<string | null>(null);

  // Use polling hook
  const shouldPoll = !!(contentId && !fullScreen);
  const { status, contentUrl, error: pollingError } = useContentPolling(contentId, shouldPoll);

  // Reset state when modal opens/closes
  useEffect(() => {
    if (!isOpen) {
      setFullScreen(false);
      setContentId(null);
      setCurrentContentUrl(null);
      setIsInitiating(false);
      setError(null);
    }
  }, [isOpen]);

  // Handle when content is complete
  useEffect(() => {
    if (status === 'complete' && contentUrl) {
      // Reset generation state 
      setContentId(null);
      setCurrentContentUrl(null);
      setIsInitiating(false);
      setError(null);

      // Notify parent to refresh conversation data so new thumbnail appears
      if (onContentGenerated) {
        onContentGenerated();
      }
    }
  }, [status, contentUrl, onContentGenerated]);

  // Combine errors from initiation and polling
  const displayError = error || pollingError;

  const handleGenerateCard = async () => {
    if (!conversationId || !messageId) {
      setError("Missing conversation or message information");
      return;
    }

    setIsInitiating(true);
    setError(null);

    try {
      // Start content generation
      const response = await contentAPI.createContent({
        conversation_id: conversationId,
        message_id: messageId,
        mode: "image"
      });

      setContentId(response.id);
      // Polling will start automatically via the hook
    } catch (error) {
      console.error("Failed to initiate contemplation card generation:", error);
      setError(error instanceof Error ? error.message : "Failed to start generation");
    } finally {
      setIsInitiating(false);
    }
  };

  const handleDownload = async (downloadUrl?: string) => {
    const urlToDownload = downloadUrl || contentUrl;
    if (!urlToDownload) return;

    try {
      const response = await fetch(urlToDownload);
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);

      const link = document.createElement('a');
      link.download = 'contemplation-card.png';
      link.href = url;
      link.click();

      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Failed to download image:", error);
    }
  };

  // Determine if we're in a loading state
  const isLoading = isInitiating || (contentId && status !== 'complete' && status !== 'failed');

  // Full screen view with generated image  
  const displayUrl = currentContentUrl || contentUrl;

  // Loading animation component
  const LoadingAnimation = () => {
    const getLoadingMessage = () => {
      if (isInitiating) return "Starting generation...";
      if (status === 'pending') return "Preparing your card...";
      if (status === 'processing') return "Creating your contemplation card...";
      return "Creating your contemplation card...";
    };

    return (
      <div className="flex flex-col items-center justify-center py-12">
        <div className="relative">
          {/* Outer rotating circle */}
          <div className="w-16 h-16 border-4 border-orange-200 rounded-full animate-spin border-t-brand-button"></div>
          {/* Inner pulsing circle */}
          <div className="absolute inset-2 w-12 h-12 bg-gradient-to-br from-orange-300 to-brand-button rounded-full animate-pulse"></div>
          {/* Center dot */}
          <div className="absolute inset-6 w-4 h-4 bg-white rounded-full"></div>
        </div>
        <p className="mt-4 text-brand-button text-lg font-medium">{getLoadingMessage()}</p>
        <p className="mt-2 text-brand-body text-sm">This may take a few moments (Please don't close the tab)</p>
      </div>
    );
  };

  const handleViewCard = (contentGeneration: ContentGeneration) => {
    if (contentGeneration.status === 'complete' && contentGeneration.content_url) {
      setFullScreen(true);
      setCurrentContentUrl(contentGeneration.content_url);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  // Filter for completed contemplation cards
  const completedCards = existingContentGenerations.filter(cg =>
    cg.content_type === 'image' && cg.status === 'complete' && cg.content_url
  );

  const modalContent = fullScreen && displayUrl ? (
    // Full screen view within the modal
    <div className="relative h-[85vh] flex items-center justify-center bg-gradient-to-br from-gray-900 to-black rounded-xl animate-in zoom-in-95 duration-500">
      <div className="absolute top-6 right-6 flex gap-3 z-10">
        <Button
          onClick={() => handleDownload(displayUrl)}
          variant="ghost"
          size="lg"
          className="text-white rounded-full bg-black bg-opacity-30 hover:bg-opacity-50 backdrop-blur-sm transition-all duration-200"
        >
          <Download className="w-6 h-6" />
        </Button>
        <Button
          onClick={() => {
            setFullScreen(false);
            setCurrentContentUrl(null);
            setError(null);
          }}
          variant="ghost"
          size="lg"
          className="text-white rounded-full bg-black bg-opacity-30 hover:bg-opacity-50 backdrop-blur-sm transition-all duration-200"
        >
          <X className="w-6 h-6" />
        </Button>
      </div>
      <img
        src={displayUrl}
        alt="Contemplation Card"
        className="max-w-full max-h-full object-contain rounded-xl shadow-2xl animate-in zoom-in-95 duration-700"
      />
    </div>
  ) : (
    <div>
      {displayError ? (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-red-600">{displayError}</p>
        </div>
      ) : null}

      {/* Existing Contemplation Cards */}
      {completedCards.length > 0 && (
        <div className="mb-8">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {completedCards.map((card, index) => (
              <div
                key={card.id}
                className="group relative animate-in slide-in-from-bottom-4 duration-500"
                style={{ animationDelay: `${index * 100}ms` }}
              >
                <div
                  className="aspect-square rounded-xl overflow-hidden border-2 border-orange-200 cursor-pointer hover:border-brand-button transition-all duration-300 hover:shadow-xl transform hover:scale-105"
                  onClick={() => handleViewCard(card)}
                >
                  <img
                    src={card.content_url}
                    alt="Contemplation Card"
                    className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-300"
                  />
                  <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-30 transition-all duration-300 flex items-center justify-center">
                    <Eye className="w-8 h-8 text-white opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Loading Animation - Show below thumbnails when generating */}
      {isLoading && <LoadingAnimation />}

      {/* Generate New Card Section - Only show when not loading */}
      {!isLoading && (
        <div className="text-center">
          <div className="mb-6">
            <p className="text-brand-body mb-4">
              Generate a beautiful contemplation card based on your conversation that you can save and share.
            </p>
          </div>

          <Button
            onClick={handleGenerateCard}
            disabled={!conversationId || !messageId}
            className="bg-brand-button hover:bg-brand-button/90 text-white px-8 py-3 rounded-full text-lg font-medium"
          >
            Generate New Contemplation Card
          </Button>

          {!conversationId || !messageId ? (
            <p className="mt-4 text-sm text-gray-500">
              Please start a conversation first to generate a contemplation card.
            </p>
          ) : null}
        </div>
      )}
    </div>
  );

  return (
    <BaseModal
      isOpen={isOpen}
      onClose={onClose}
      title="Contemplation Card"
      size="xlarge"
    >
      {modalContent}
    </BaseModal>
  );
};

export default ContemplationModal;

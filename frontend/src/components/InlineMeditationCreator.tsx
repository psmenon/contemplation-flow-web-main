
import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Download, Volume2, Video, Eye } from "lucide-react";
import BaseModal from "./BaseModal";
import { contentAPI } from "@/apis/api";
import type { ContentGeneration } from "@/apis/wire";

interface InlineMeditationCreatorProps {
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
      console.log("meditation content", content);
      console.log("meditation content.status", content.status);

      if (content.status === "complete" && content.content_url) {
        setContentUrl(content.content_url);
      } else if (content.status === "failed") {
        setError("Meditation guide generation failed");
      }
    } catch (err) {
      console.error("Error polling meditation content:", err);
      setError(err instanceof Error ? err.message : "Failed to check meditation guide status");
    }
  }, [contentId]);

  useEffect(() => {
    if (!shouldPoll || !contentId) return;

    // Initial poll
    pollContent();

    // Set up polling interval
    const interval = setInterval(() => {
      pollContent();
    }, 2000); // Poll every 2 seconds

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

const InlineMeditationCreator = ({
  isOpen,
  onClose,
  conversationId,
  messageId,
  existingContentGenerations = [],
  onContentGenerated
}: InlineMeditationCreatorProps) => {
  const [selectedLength, setSelectedLength] = useState("10 min");
  const [selectedFormat, setSelectedFormat] = useState("Audio");
  const [fullScreen, setFullScreen] = useState(false);
  const [contentId, setContentId] = useState<string | null>(null);
  const [isInitiating, setIsInitiating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentContentUrl, setCurrentContentUrl] = useState<string | null>(null);
  const [currentContentType, setCurrentContentType] = useState<'audio' | 'video' | null>(null);

  const lengths = ["5 min", "10 min", "15 min", "20 min"];
  const formats = ["Audio", "Video"];

  // Use polling hook - stop polling when in fullscreen
  const shouldPoll = !!(contentId && !fullScreen);
  const { status, contentUrl, error: pollingError } = useContentPolling(contentId, shouldPoll);

  // Reset state when modal opens/closes
  useEffect(() => {
    if (!isOpen) {
      setFullScreen(false);
      setContentId(null);
      setCurrentContentUrl(null);
      setCurrentContentType(null);
      setIsInitiating(false);
      setError(null);
      setSelectedLength("10 min");
      setSelectedFormat("Audio");
    }
  }, [isOpen]);

  // Handle when content is complete
  useEffect(() => {
    if (status === 'complete' && contentUrl) {
      // Reset generation state to show the new content in thumbnails
      setContentId(null);
      setCurrentContentUrl(null);
      setCurrentContentType(null);
      setIsInitiating(false);
      setError(null);
      onContentGenerated?.(); // Call the prop callback
    }
  }, [status, contentUrl, onContentGenerated]);

  // Combine errors from initiation and polling
  const displayError = error || pollingError;

  const handleGenerateGuide = async () => {
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
        mode: selectedFormat.toLowerCase() as 'audio' | 'video'
      });

      setContentId(response.id);
      // Polling will start automatically via the hook
    } catch (error) {
      console.error("Failed to initiate meditation guide generation:", error);
      setError(error instanceof Error ? error.message : "Failed to start meditation guide generation");
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
      link.download = `meditation-guide.${currentContentType === 'audio' ? 'mp3' : 'mp4'}`;
      link.href = url;
      link.click();

      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Failed to download meditation guide:", error);
    }
  };

  const handleViewGuide = (guide: ContentGeneration) => {
    if (guide.status === 'complete' && guide.content_url) {
      setFullScreen(true);
      setCurrentContentUrl(guide.content_url);
      setCurrentContentType(guide.content_type as 'audio' | 'video');
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

  // Determine if we're in a loading state
  const isLoading = isInitiating || (contentId && status !== 'complete' && status !== 'failed');

  // Full screen view with generated content
  const displayUrl = currentContentUrl || contentUrl;
  const FullScreenView = () => {
    if (!fullScreen || !displayUrl) return null;

    return (
      <div className="fixed inset-0 bg-black bg-opacity-90 flex items-center justify-center z-50">
        <div className="relative w-full h-full flex items-center justify-center">
          <div className="absolute top-4 right-4 flex gap-2">
            <Button
              onClick={() => handleDownload(displayUrl)}
              variant="ghost"
              size="sm"
              className="text-white rounded-full bg-black bg-opacity-20 hover:bg-opacity-30"
            >
              <Download className="w-6 h-6" />
            </Button>
            <Button
              onClick={() => {
                setFullScreen(false);
                setCurrentContentUrl(null);
                setCurrentContentType(null);
                setError(null);
              }}
              variant="ghost"
              size="sm"
              className="text-white rounded-full bg-black bg-opacity-20 hover:bg-opacity-30"
            >
              ×
            </Button>
          </div>

          {currentContentType === 'video' ? (
            <video
              src={displayUrl}
              controls
              className="max-w-full max-h-full object-contain rounded-lg shadow-2xl"
              preload="metadata"
            >
              Your browser does not support the video tag.
            </video>
          ) : (
            <div className="max-w-2xl w-full bg-gradient-to-br from-blue-400 to-purple-600 rounded-lg shadow-2xl p-8">
              <div className="text-white text-center">
                <div className="text-6xl mb-6">🧘‍♀️</div>
                <p className="text-2xl mb-6">Guided Meditation</p>
                <audio
                  src={displayUrl}
                  controls
                  className="w-full"
                  preload="metadata"
                >
                  Your browser does not support the audio tag.
                </audio>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  };

  // Loading animation component
  const LoadingAnimation = () => {
    const getLoadingMessage = () => {
      if (isInitiating) return "Starting generation...";
      if (status === 'pending') return "Preparing your meditation...";
      if (status === 'processing') return "Creating your guided session...";
      return "Creating your meditation guide...";
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

  // Filter for completed meditation guides (audio and video)
  const completedGuides = existingContentGenerations.filter(guide =>
    (guide.content_type === 'audio' || guide.content_type === 'video') &&
    guide.status === 'complete' &&
    guide.content_url
  );

  const modalContent = (
    <div>
      {displayError ? (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-red-600">{displayError}</p>
        </div>
      ) : null}

      {/* Existing Meditation Guides */}
      {completedGuides.length > 0 && (
        <div className="mb-8">
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
            {completedGuides.map((guide) => (
              <div key={guide.id} className="group relative">
                <div
                  className="aspect-square rounded-lg overflow-hidden border-2 border-orange-200 cursor-pointer hover:border-brand-button transition-colors bg-gradient-to-br from-blue-50 to-purple-50 flex items-center justify-center"
                  onClick={() => handleViewGuide(guide)}
                >
                  <div className="text-center">
                    {guide.content_type === "audio" ? (
                      <Volume2 className="w-12 h-12 text-brand-button mb-2 mx-auto" />
                    ) : (
                      <Video className="w-12 h-12 text-brand-button mb-2 mx-auto" />
                    )}
                    <p className="text-sm font-medium text-brand-button capitalize">{guide.content_type}</p>
                    <p className="text-xs text-brand-body">Meditation</p>
                  </div>
                  <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-20 transition-opacity duration-200 flex items-center justify-center">
                    <Eye className="w-6 h-6 text-white opacity-0 group-hover:opacity-100 transition-opacity duration-200" />
                  </div>
                </div>
                <div className="mt-2 flex items-center justify-between">
                  <p className="text-xs text-brand-body truncate">
                    {formatDate(guide.created_at)}
                  </p>
                  <Button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDownload(guide.content_url);
                    }}
                    variant="ghost"
                    size="sm"
                    className="h-6 w-6 p-0 text-brand-button hover:text-brand-button/80"
                  >
                    <Download className="w-3 h-3" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Loading Animation - Show below thumbnails when generating */}
      {isLoading && <LoadingAnimation />}

      {/* Generate New Guide Section - Only show when not loading */}
      {!isLoading && (
        <div>
          <div className="mb-6">
            <p className="text-brand-body mb-4">Choose the length of guidance</p>
            <div className="grid grid-cols-2 gap-3">
              {lengths.map((length) => (
                <Button
                  key={length}
                  onClick={() => setSelectedLength(length)}
                  variant={selectedLength === length ? "default" : "outline"}
                  className={`rounded-full ${selectedLength === length
                    ? "bg-brand-button hover:bg-brand-button/90 text-white"
                    : "border-orange-200 hover:border-brand-button"
                    }`}
                >
                  {length}
                </Button>
              ))}
            </div>
          </div>

          <div className="mb-6">
            <p className="text-brand-body mb-4">Choose the format that you want</p>
            <div className="grid grid-cols-2 gap-3">
              {formats.map((format) => (
                <Button
                  key={format}
                  onClick={() => setSelectedFormat(format)}
                  variant={selectedFormat === format ? "default" : "outline"}
                  className={`rounded-full ${selectedFormat === format
                    ? "bg-brand-button hover:bg-brand-button/90 text-white"
                    : "border-orange-200 hover:border-brand-button"
                    }`}
                >
                  {format}
                </Button>
              ))}
            </div>
          </div>

          <div className="mb-6">
            <p className="text-brand-body text-sm">
              Create a personalized meditation guide based on your conversation. This will generate a {selectedFormat.toLowerCase()} session that you can save and use for your practice.
            </p>
          </div>

          <div className="text-center">
            <Button
              onClick={handleGenerateGuide}
              disabled={!conversationId || !messageId}
              className="bg-brand-button hover:bg-brand-button/90 text-white px-8 py-3 rounded-full text-lg font-medium"
            >
              Generate New Meditation Guide
            </Button>

            {!conversationId || !messageId ? (
              <p className="mt-4 text-sm text-gray-500">
                Please start a conversation first to generate a meditation guide.
              </p>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );

  return (
    <>
      <BaseModal
        isOpen={isOpen}
        onClose={onClose}
        title="Create Meditation Guide"
      >
        {modalContent}
      </BaseModal>
      <FullScreenView />
    </>
  );
};

export default InlineMeditationCreator;

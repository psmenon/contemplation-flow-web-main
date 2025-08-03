// Export the API client
export { default as apiClient } from './client';

// Export all API functions
export {
    authAPI,
    chatAPI,
    contentAPI,
    adminAPI,
} from './api';

// Export all types
export type {
    User,
    NewUserRequest,
    LoginRequest,
    AuthResponse,
    RefreshTokenRequest,
    Message,
    Conversation,
    ConversationsListResponse,
    ConversationDetailResponse,
    UpdateConversationTitleRequest,
    MessageFeedbackRequest,
    ContentGenerationRequest,
    ContentGenerationResponse,
} from './wire';

// Export the default API object
export { default as api } from './api'; 
// User Management Interfaces
export interface User {
    id: string;
    phone_number: string;
    phone_verified: boolean;
    name: string | null;
    role: string; // "user" or "admin"
    created_at: string; // ISO timestamp
    last_active: string; // ISO timestamp
}

export interface NewUserRequest {
    phone_number: string;
    name: string;
}

export interface LoginRequest {
    phone_number: string;
    otp?: string | null;
}

export interface AuthResponse {
    access_token: string;
    refresh_token: string;
    user: User | null;
}

export interface RefreshTokenRequest {
    refresh_token: string;
}

// Content Generation Interfaces
export interface ContentGenerationRequest {
    conversation_id: string;
    message_id: string;
    mode: 'audio' | 'video' | 'image';
}

export interface ContentGenerationResponse {
    id: string;
    status: 'processing' | 'complete' | 'failed';
}

export interface ContentGeneration {
    id: string;
    status: 'processing' | 'complete' | 'failed';
    conversation_id: string;
    message_id: string;
    content_type: 'audio' | 'video' | 'image';
    created_at: string; // ISO timestamp
    content_url: string | null;
    transcript?: string | null;
}

export interface ContentGenerationListResponse {
    ids: string[];
}

// Speech Processing Interfaces
export interface TranscriptionResponse {
    text: string;
}

export interface TTSRequest {
    text: string;
}

// Chat & Conversation Interfaces
export interface CitationInfo {
    name: string;
    url: string;
}

export interface FollowUpQuestions {
    questions: string[];
}

export interface Message {
    id: string;
    role: 'user' | 'assistant';
    created_at: string; // ISO timestamp
    content: string;
    citations?: CitationInfo[] | null;
    follow_up_questions?: FollowUpQuestions | null;
}

export interface CreateConversationRequest {
    messages?: Message[] | null;
}

export interface ChatCompletionRequest {
    message: string;
    stream: boolean;
    mock?: boolean;
}

export interface ChatCompletionResponse {
    message: string;
    message_id: string;
    questions?: string[] | null;
    citations?: CitationInfo[] | null;
    title?: string | null;
}

export interface Conversation {
    id: string;
    user_id: string;
    title: string | null;
    created_at: string; // ISO timestamp
}

export interface ConversationsListResponse {
    conversations: Conversation[];
}

export interface ConversationDetailResponse {
    conversation: Conversation;
    messages: Message[];
    content_generations: ContentGeneration[];
}

export interface UpdateConversationTitleRequest {
    title: string;
}

export interface MessageFeedbackRequest {
    message_id: string;
    type: 'positive' | 'negative';
    comment?: string | null;
}

// Admin Interfaces
export interface UserWithUsage extends User {
    usage_stats: Record<string, any>;
}

export interface ListUsersResponse {
    users: UserWithUsage[];
}

export interface SourceDocument {
    id: string;
    filename: string;
    file_size_bytes: number;
    active: boolean;
    status: 'processing' | 'completed' | 'failed';
    created_at: string; // ISO timestamp
}

export interface SourceDocumentsResponse {
    files: SourceDocument[];
}

export interface UserFeedback {
    user_id: string;
    message_id: string;
    type: 'positive' | 'negative';
    comment?: string | null;
    created_at: string; // ISO timestamp
}

export interface AdminFeedbackResponse {
    feedback: UserFeedback[];
}


// These types are still used in the frontend but are not in wire.py
// They should probably be added to wire.py and generated from there in the future.

export interface UserPreferences {
    theme: 'light' | 'dark';
    notifications: boolean;
    meditationLength: number;
    preferredFormat: 'audio' | 'video';
}

export interface AIModel {
    id: string;
    name: string;
    enabled: boolean;
    provider: string;
    capabilities: string[];
}

export interface FileInfo {
    id: string;
    name: string;
    type: string;
    size: string;
    uploadDate: string;
    url?: string;
}

export interface MeditationRequest {
    length: number; // in minutes
    format: 'audio' | 'video';
    topic?: string;
    style?: string;
}

export interface MeditationResponse {
    id: string;
    status: 'pending' | 'processing' | 'completed' | 'failed';
    progress?: number;
    downloadUrl?: string;
    duration?: number;
    format: 'audio' | 'video';
}

export interface ContemplationCard {
    id: string;
    quote: string;
    background: string;
    downloadUrl?: string;
}

export interface Feedback {
    messageId: string;
    rating: 'thumbs_up' | 'thumbs_down';
    comment?: string;
}


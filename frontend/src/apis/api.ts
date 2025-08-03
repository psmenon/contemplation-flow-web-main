import apiClient from './client';
import {
    AdminFeedbackResponse,
    AuthResponse,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ContentGeneration,
    ContentGenerationRequest,
    ContentGenerationResponse,
    Conversation,
    ConversationDetailResponse,
    ConversationsListResponse,
    CreateConversationRequest,
    ListUsersResponse,
    LoginRequest,
    MessageFeedbackRequest,
    NewUserRequest,
    RefreshTokenRequest,
    SourceDocumentsResponse,
    UpdateConversationTitleRequest,
    User,
} from './wire';


// Authentication APIs
export const authAPI = {
    register: async (data: NewUserRequest): Promise<AuthResponse> => {
        const response = await apiClient.post('/auth/register', data);
        const { access_token, refresh_token, user } = response.data;
        if (access_token) localStorage.setItem('accessToken', access_token);
        if (refresh_token) localStorage.setItem('refreshToken', refresh_token);
        return { access_token, refresh_token, user };
    },
    login: async (data: LoginRequest): Promise<AuthResponse> => {
        const response = await apiClient.post('/auth/login', data);
        const { access_token, refresh_token, user } = response.data;
        if (access_token) localStorage.setItem('accessToken', access_token);
        if (refresh_token) localStorage.setItem('refreshToken', refresh_token);
        return { access_token, refresh_token, user };
    },

    logout: async () => {
        await apiClient.post('/auth/logout');
        localStorage.removeItem('accessToken');
        localStorage.removeItem('refreshToken');
    },

    getCurrentUser: async (): Promise<User> => {
        const response = await apiClient.get('/auth/me');
        return response.data;
    },

    refreshToken: async (data: RefreshTokenRequest): Promise<AuthResponse> => {
        const response = await apiClient.post('/auth/refresh', data);
        const { access_token, refresh_token, user } = response.data;
        if (access_token) localStorage.setItem('accessToken', access_token);
        return { access_token, refresh_token, user };
    },
};

// Chat APIs
export const chatAPI = {
    getConversations: async (): Promise<ConversationsListResponse> => {
        const response = await apiClient.get('/chat');
        return response.data;
    },
    createConversation: async (request: CreateConversationRequest): Promise<Conversation> => {
        const response = await apiClient.post('/chat', request);
        return response.data;
    },
    getConversation: async (id: string): Promise<ConversationDetailResponse> => {
        const response = await apiClient.get(`/chat/${id}`);
        return response.data;
    },
    chatCompletion: async (
        conversationId: string,
        request: ChatCompletionRequest,
        onChunk?: (chunk: string) => void
    ): Promise<ChatCompletionResponse> => {
        const { stream } = request;
        if (stream && onChunk) {
            // Use fetch for proper streaming support
            const response = await fetch(`${apiClient.defaults.baseURL}/chat/${conversationId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('accessToken')}`,
                },
                body: JSON.stringify(request),
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`);
            }

            if (!response.body) {
                throw new Error('No response body available for streaming');
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            let partialData = '';
            let parsedResponse: Partial<ChatCompletionResponse> = {
                message: '',
                message_id: '',
                questions: [],
                citations: [],
                title: undefined
            };
            let collectingQuestions = false;

            try {
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    const chunk = decoder.decode(value, { stream: true });
                    partialData += chunk;

                    // Split by newlines to handle multiple chunks in one read
                    const lines = partialData.split('\n');
                    partialData = lines.pop() || ''; // Keep the last incomplete line

                    for (const line of lines) {
                        if (line.trim() === '') continue;
                        if (line === '[DONE]') continue;

                        try {
                            // Handle different chunk formats
                            let content = '';

                            // Parse OpenAI-style streaming chunk (data: {...})
                            if (line.startsWith('data: ')) {
                                const jsonStr = line.slice(6);
                                if (jsonStr.trim() === '[DONE]') continue;

                                const chunkData = JSON.parse(jsonStr);
                                content = chunkData.choices?.[0]?.delta?.content || '';
                            }
                            // Handle direct JSON streaming chunks
                            else if (line.startsWith('{') && line.includes('choices')) {
                                const chunkData = JSON.parse(line);
                                content = chunkData.choices?.[0]?.delta?.content || '';
                            }
                            // Handle plain text lines (for your custom format)
                            else {
                                content = line;
                            }

                            if (content) {
                                // Handle special tags from your backend
                                if (content.includes('<message_id>') && content.includes('</message_id>')) {
                                    const match = content.match(/<message_id>(.*?)<\/message_id>/);
                                    if (match) {
                                        parsedResponse.message_id = match[1];
                                    }
                                } else if (content.includes('<title>') && content.includes('</title>')) {
                                    const match = content.match(/<title>(.*?)<\/title>/);
                                    if (match) {
                                        parsedResponse.title = match[1];
                                    }
                                } else if (content.includes('<questions>')) {
                                    // Start collecting questions - content after this will be questions
                                    collectingQuestions = true;
                                    continue;
                                } else if (content.includes('</questions>')) {
                                    // End collecting questions
                                    collectingQuestions = false;
                                    continue;
                                } else if (content.includes('<citations>')) {
                                    // Start collecting citations
                                    continue;
                                } else if (content.includes('</citations>')) {
                                    // End collecting citations
                                    continue;
                                } else if (content.startsWith('{') && content.includes('"name"')) {
                                    // Citation JSON
                                    try {
                                        const citation = JSON.parse(content);
                                        parsedResponse.citations?.push(citation);
                                    } catch (e) {
                                        // Not valid JSON, treat as regular content
                                        parsedResponse.message += content;
                                        onChunk(parsedResponse.message);
                                    }
                                } else if (collectingQuestions && content.trim() && !content.includes('<') && !content.includes('>')) {
                                    // Question content - add to questions array
                                    if (!parsedResponse.questions) {
                                        parsedResponse.questions = [];
                                    }
                                    parsedResponse.questions.push(content.trim());
                                } else if (content.trim() && !content.includes('<') && !content.includes('>')) {
                                    // Regular message content - accumulate and call onChunk
                                    parsedResponse.message += content;
                                    onChunk(parsedResponse.message);
                                } else {
                                    // Log unhandled content for debugging
                                    console.log('Unhandled streaming content:', content);
                                }
                            }
                        } catch (e) {
                            // If JSON parsing fails, treat as plain text content
                            if (collectingQuestions && line.trim() && !line.includes('<') && !line.includes('>')) {
                                // Question content - add to questions array
                                if (!parsedResponse.questions) {
                                    parsedResponse.questions = [];
                                }
                                parsedResponse.questions.push(line.trim());
                            } else if (line.trim() && !line.includes('<') && !line.includes('>')) {
                                parsedResponse.message += line;
                                onChunk(parsedResponse.message);
                            } else {
                                console.warn('Error parsing streaming chunk:', e, 'Line:', line);
                            }
                        }
                    }
                }
            } catch (streamError) {
                console.error('Streaming error:', streamError);
                throw new Error(`Streaming failed: ${streamError instanceof Error ? streamError.message : 'Unknown error'}`);
            } finally {
                reader.releaseLock();
            }

            // Validate response has required fields
            if (!parsedResponse.message_id) {
                parsedResponse.message_id = `temp-${Date.now()}`;
            }
            if (!parsedResponse.message) {
                throw new Error('No message content received from stream');
            }

            return parsedResponse as ChatCompletionResponse;
        } else {
            const response = await apiClient.post(`/chat/${conversationId}`, request);
            return response.data;
        }
    },
    deleteConversation: async (id: string): Promise<void> => {
        await apiClient.delete(`/chat/${id}`);
    },
    updateConversationTitle: async (id: string, title: string): Promise<Conversation> => {
        const request: UpdateConversationTitleRequest = { title };
        const response = await apiClient.put(`/chat/${id}/title`, request);
        return response.data;
    },
    submitFeedback: async (conversationId: string, feedback: MessageFeedbackRequest): Promise<void> => {
        await apiClient.post(`/chat/${conversationId}/feedback`, feedback);
    },
};

// Content Generation APIs
export const contentAPI = {
    createContent: async (request: ContentGenerationRequest): Promise<ContentGenerationResponse> => {
        const response = await apiClient.post('/content', request);
        return response.data;
    },
    getContent: async (contentId: string): Promise<ContentGeneration> => {
        const response = await apiClient.get(`/content/${contentId}`);
        return response.data;
    }
};

// Admin APIs
export const adminAPI = {
    listUsers: async (): Promise<ListUsersResponse> => {
        const response = await apiClient.get('/admin/users');
        return response.data;
    },
    deleteUser: async (userId: string): Promise<void> => {
        await apiClient.delete(`/admin/users/${userId}`);
    },
    deleteContent: async (contentId: string): Promise<void> => {
        await apiClient.delete(`/admin/content/${contentId}`);
    },
    getFeedback: async (): Promise<AdminFeedbackResponse> => {
        const response = await apiClient.get('/admin/feedback');
        return response.data;
    },
    listSourceData: async (): Promise<SourceDocumentsResponse> => {
        const response = await apiClient.get('/admin/source-data/list');
        return response.data;
    },
};

// Export all APIs
export default {
    auth: authAPI,
    chat: chatAPI,
    content: contentAPI,
    admin: adminAPI,
}; 
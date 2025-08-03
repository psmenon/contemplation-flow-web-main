# Backend API Requirements for Contemplation Flow Web Frontend

## 1. Introduction

This document provides a detailed specification of the backend API endpoints required by the `contemplation-flow-web` frontend. The requirements are derived from the existing frontend components, pages, and defined API communication layers. The primary source of truth for the frontend's expected API contracts is `frontend/src/apis/api.ts`.

This document is intended to be used by backend developers to implement the necessary services and by frontend developers as a reference for API interactions.

## 2. Data Models

The following TypeScript interfaces define the shape of the data exchanged between the frontend and backend.

```typescript
export interface User {
    id: string;
    email: string;
    name: string;
    preferences?: UserPreferences;
}

export interface UserPreferences {
    theme: 'light' | 'dark';
    notifications: boolean;
    meditationLength: number;
    preferredFormat: 'audio' | 'video';
}

export interface Message {
    id: string;
    content: string;
    isUser: boolean;
    timestamp: string;
    thinking?: string;
    links?: string[];
    mediaUrl?: string;
    mediaType?: 'audio' | 'video';
}

export interface Conversation {
    id: string;
    title: string;
    messages: Message[];
    createdAt: string;
    updatedAt: string;
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
```

## 3. Authentication (`/auth`)

The application requires a standard set of authentication endpoints for user management. The frontend uses a JWT stored in `localStorage` to manage sessions.

-   **Component:** `Admin.tsx` (Login Form), `App.tsx` (for user loading)
-   **API File:** `frontend/src/apis/api.ts` (`authAPI`)

| Method | Endpoint              | Description                               | Request Body                          | Response Body                     |
| :----- | :-------------------- | :---------------------------------------- | :------------------------------------ | :-------------------------------- |
| POST   | `/auth/login`         | Logs a user in.                           | `{ email, password }`                 | `{ token, user: User }`           |
| POST   | `/auth/register`      | Registers a new user.                     | `{ email, password, name }`           | `{ token, user: User }`           |
| POST   | `/auth/logout`        | Logs a user out.                          | (empty)                               | (empty)                           |
| GET    | `/auth/me`            | Retrieves the current authenticated user. | (empty)                               | `User`                            |
| POST   | `/auth/refresh`       | Refreshes the authentication token.       | (empty)                               | `{ token }`                       |

## 4. Chat (`/chat`)

The core of the application is the chat interface. These APIs manage conversations and messages.

-   **Component:** `Chat.tsx`, `Index.tsx`
-   **API File:** `frontend/src/apis/api.ts` (`chatAPI`)

| Method | Endpoint                               | Description                                     | Request Body             | Response Body        |
| :----- | :------------------------------------- | :---------------------------------------------- | :----------------------- | :------------------- |
| GET    | `/chat/conversations`                  | Get a list of all conversations for the user.   | (empty)                  | `Conversation[]`     |
| POST   | `/chat/conversations`                  | Create a new conversation.                      | `{ title?: string }`     | `Conversation`       |
| GET    | `/chat/conversations/:id`              | Get a single conversation by its ID.            | (empty)                  | `Conversation`       |
| DELETE | `/chat/conversations/:id`              | Delete a conversation.                          | (empty)                  | (empty)              |
| PUT    | `/chat/conversations/:id/title`        | Update the title of a conversation.             | `{ title: string }`      | `Conversation`       |
| POST   | `/chat/conversations/:id/messages`     | Send a new message to a conversation.           | `{ content: string }`    | `Message`            |
| POST   | `/chat/conversations/:id/stream`       | Send a message and get a streamed response.     | `{ content: string }`    | `stream of text`     |

## 5. Meditations (`/meditation`)

The application can generate personalized meditation guides.

-   **Component:** `InlineMeditationCreator.tsx` (in `Chat.tsx`), `Admin.tsx`
-   **API File:** `frontend/src/apis/api.ts` (`meditationAPI`)

| Method | Endpoint                   | Description                                  | Request Body          | Response Body             |
| :----- | :------------------------- | :------------------------------------------- | :-------------------- | :------------------------ |
| POST   | `/meditation/create`       | Request the generation of a new meditation.  | `MeditationRequest`   | `MeditationResponse`      |
| GET    | `/meditation/list`         | Get a list of all generated meditations.     | (empty)               | `MeditationResponse[]`    |
| GET    | `/meditation/:id/status`   | Get the status of a meditation generation.   | (empty)               | `MeditationResponse`      |
| GET    | `/meditation/:id/download` | Get the download URL for a meditation.       | (empty)               | `{ downloadUrl: string }` |
| DELETE | `/meditation/:id`          | Delete a generated meditation.               | (empty)               | (empty)                   |

## 6. Contemplation Cards (`/cards`)

The application can generate contemplation cards with quotes.

-   **Component:** `ContemplationModal.tsx` (in `Chat.tsx`)
-   **API File:** `frontend/src/apis/api.ts` (`cardsAPI`)

| Method | Endpoint             | Description                                  | Request Body          | Response Body               |
| :----- | :------------------- | :------------------------------------------- | :-------------------- | :-------------------------- |
| POST   | `/cards/generate`    | Generate a new contemplation card.           | `{ quote?: string }`  | `ContemplationCard`         |
| GET    | `/cards/list`        | Get a list of all generated cards.           | (empty)               | `ContemplationCard[]`       |
| GET    | `/cards/:id/download`| Get the download URL for a card.             | (empty)               | `{ downloadUrl: string }`   |
| DELETE | `/cards/:id`         | Delete a generated card.                     | (empty)               | (empty)                     |

## 7. File Management (`/files`)

The admin panel allows for file uploads, which are presumably used as context for the AI.

-   **Component:** `Admin.tsx`
-   **API File:** `frontend/src/apis/api.ts` (`fileAPI`)

| Method | Endpoint               | Description                               | Request Body       | Response Body |
| :----- | :--------------------- | :---------------------------------------- | :----------------- | :------------ |
| POST   | `/files/upload`        | Upload a new file.                        | `FormData(file)`   | `FileInfo`    |
| GET    | `/files/list`          | Get a list of all uploaded files.         | (empty)            | `FileInfo[]`  |
| GET    | `/files/:id`           | Get information about a single file.      | (empty)            | `FileInfo`    |
| GET    | `/files/:id/download`  | Download a file.                          | (empty)            | `Blob`        |
| DELETE | `/files/:id`           | Delete a file.                            | (empty)            | (empty)       |

## 8. Speech-to-Text (`/speech`)

The chat and index pages have a microphone button for voice input.

-   **Component:** `Chat.tsx`, `Index.tsx`
-   **API File:** `frontend/src/apis/api.ts` (`speechAPI`)

| Method | Endpoint             | Description                               | Request Body       | Response Body      |
| :----- | :------------------- | :---------------------------------------- | :----------------- | :----------------- |
| POST   | `/speech/transcribe` | Transcribe an audio blob to text.         | `FormData(audio)`  | `{ text: string }` |
| POST   | `/speech/stream`     | Stream audio for real-time transcription. | `FormData(audio)`  | `stream of text`   |

## 9. Text-to-Speech (`/tts`)

The application has the capability to generate audio from text, likely for reading out messages or meditations.

-   **Component:** (Not explicitly used, but defined in API)
-   **API File:** `frontend/src/apis/api.ts` (`ttsAPI`)

| Method | Endpoint           | Description                                  | Request Body            | Response Body |
| :----- | :----------------- | :------------------------------------------- | :---------------------- | :------------ |
| POST   | `/tts/generate`    | Generate speech from text.                   | `{ text, voice? }`      | `{ id }`      |
| GET    | `/tts/:id/audio`   | Get the generated audio file.                | (empty)                 | `Blob`        |

## 10. User Preferences & History (`/user`)

APIs for managing user-specific data.

-   **Component:** (UI not explicit, but APIs are defined)
-   **API File:** `frontend/src/apis/api.ts` (`userAPI`)

| Method | Endpoint             | Description                               | Request Body            | Response Body     |
| :----- | :------------------- | :---------------------------------------- | :---------------------- | :---------------- |
| GET    | `/user/preferences`  | Get the current user's preferences.       | (empty)                 | `UserPreferences` |
| PUT    | `/user/preferences`  | Update user preferences.                  | `Partial<UserPrefs>`    | `UserPreferences` |
| GET    | `/user/history`      | Get user's activity history.              | (empty)                 | `any[]`           |

## 11. Explore/Suggestions (`/explore`)

APIs for providing suggestions to the user.

-   **Component:** `ExploreMore.tsx` (in `Chat.tsx`)
-   **API File:** `frontend/src/apis/api.ts` (`exploreAPI`)

| Method | Endpoint                   | Description                               | Request Body          | Response Body |
| :----- | :------------------------- | :---------------------------------------- | :-------------------- | :------------ |
| POST   | `/explore/generate-questions` | Generate follow-up questions from context.| `{ context?: string }`| `string[]`    |
| GET    | `/explore/suggestions`     | Get generic suggestions.                  | (empty)               | `string[]`    |

## 12. Admin & Analytics (`/admin`, `/feedback`, `/analytics`)

APIs for the admin panel and for collecting feedback/analytics.

-   **Component:** `Admin.tsx`
-   **API File:** `frontend/src/apis/api.ts` (`adminAPI`, `analyticsAPI`)

| Method | Endpoint                     | Description                               | Request Body         | Response Body          |
| :----- | :--------------------------- | :---------------------------------------- | :------------------- | :--------------------- |
| GET    | `/admin/models`              | Get a list of available AI models.        | (empty)              | `AIModel[]`            |
| PUT    | `/admin/models/:id/toggle`   | Enable or disable an AI model.            | `{ enabled }`        | `AIModel`              |
| GET    | `/admin/models/status`       | Get the status of all models.             | (empty)              | `{ [key: string]: boolean }` |
| POST   | `/admin/models/:id/test`     | Test an AI model with a prompt.           | `{ prompt }`         | `{ response: string }` |
| POST   | `/feedback/message`          | Submit feedback for a message.            | `Feedback`           | (empty)                |
| GET    | `/analytics/usage`           | Get usage analytics.                      | (empty)              | `any`                  |
| GET    | `/analytics/conversations`   | Get conversation analytics.               | (empty)              | `any`                  |

## 13. Future Considerations / Missing APIs

During the analysis of the frontend code, some UI elements suggested the need for APIs that are not currently defined in `frontend/src/apis/api.ts`.

-   **Admin Panel - API Key Storage**: The `Admin.tsx` page has a section to save a third-party API key (e.g., for an LLM provider). An endpoint is needed to securely store this key on the backend.
    -   **Suggested Endpoint**: `POST /admin/config/llm-api-key`
    -   **Request Body**: `{ apiKey: string }`

-   **Analytics Data Shape**: The analytics endpoints currently return `any`. A more defined data structure should be created once the backend implementation is in progress.

This document should be considered a living document and updated as the application evolves. 
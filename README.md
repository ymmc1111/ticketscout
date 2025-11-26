# Ticket Scout - Ticket Availability Monitor (Google Cloud Deployment)

This solution deploys a React front-end (for job creation) backed by Firebase Firestore, and uses a Python Google Cloud Function for scheduled polling against the Ticketmaster API.

## 1. Prerequisites

*   **Google Cloud Project**: A project with billing enabled.
*   **Firebase/Firestore**: Firestore initialized in your Firebase project.
*   **Ticketmaster API Key**: An official API key, ideally with access to the Inventory Status API (or Partner API).
*   **Twilio Account**: For sending real SMS notifications.

## 2. File Roles

| File | Role | Deployment |
| :--- | :--- | :--- |
| `App.jsx` | User Interface (Embedded in app.py) | Hosted Web App |
| `app.py` | Flask wrapper to serve the React UI. | Hosted Web App |
| `worker.py` | Core polling logic and notification engine. | Google Cloud Function |
| `requirements.txt` | Python library dependencies. | Cloud Function/Flask environment |

## 3. Data Flow and Synchronization (CRITICAL)

The system uses two separate collections in Firestore:

1.  **Client Collection (Write-Only)**:
    *   **Path**: `/artifacts/{appId}/users/{userId}/ticket_monitors`
    *   **Function**: Where the Front-end (`App.jsx`) saves new jobs.

2.  **Worker Collection (Read/Write)**:
    *   **Path**: `worker_monitor_jobs` (Defined in `worker.py` via `MOCK_ROOT_COLLECTION` environment variable).
    *   **Function**: Where the Worker (`worker.py`) reads and updates all active jobs.

> **⚠️ MISSING DATA PIPE**: For a secure, multi-user application, a dedicated Google Cloud Function or trigger must be set up to copy new job documents from the user-specific Client Collection (1) to the Worker Collection (2) whenever a user creates a new job. This step must be implemented in your Google Cloud environment.

## 4. Worker Deployment (Google Cloud Functions)

The polling logic lives in `worker.py` and must be run on a repeating schedule.

### Step 4.1: Deploy the Cloud Function

*   **Source**: Deploy `worker.py` and `requirements.txt`.
*   **Runtime**: Select Python 3.9+ (or newest available).
*   **Entry Point**: `ticket_monitor_worker`
*   **Trigger**: HTTP (Required for Cloud Scheduler trigger).
*   **Environment Variables** (Set in Cloud Function UI):
    *   `TICKETMASTER_API_KEY`: `YOUR_TICKETMASTER_API_KEY_HERE`
    *   `MOCK_ROOT_COLLECTION`: `worker_monitor_jobs`
    *   `PROXY_URL`: `http://user:pass@proxy.example.com:port` (Highly recommended for anti-bot)

### Step 4.2: Critical Session/Anti-Bot Variables (Volatility Warning)

> **THESE VARIABLES MUST BE MANUALLY ACQUIRED FROM A LIVE BROWSER SESSION AND ARE HIGHLY VOLATILE. THEY MUST BE REFRESHED PERIODICALLY.**

*   `TM_AUTH_COOKIE`: The value of the Ticketmaster session cookie (`_tm_token`). Required for authenticated access.
*   `TM_QUEUE_TOKEN`: The value of the `queueittoken` query parameter. Required to bypass the virtual waiting room.

### Step 4.3: Twilio Credentials

*   `TWILIO_ACCOUNT_SID`: Your Twilio Account SID.
*   `TWILIO_AUTH_TOKEN`: Your Twilio Auth Token.
*   `TWILIO_FROM_NUMBER`: Your verified Twilio sender phone number (e.g., `+12025550100`).

### Step 4.4: Set up Cloud Scheduler

Create a job to trigger your Cloud Function periodically.

*   **Frequency**: Use a conservative rate (e.g., `0 * * * *` for hourly) to respect rate limits.
*   **Target**: HTTP
*   **URL**: The trigger URL of the Cloud Function deployed in Step 4.1.
*   **Auth Header**: Use an OIDC token for secure invocation. Set the audience to the Cloud Function's URL.
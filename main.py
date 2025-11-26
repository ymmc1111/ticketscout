import os
import json
import requests
import smtplib
from email.message import EmailMessage
from datetime import datetime, timezone
import random
from requests.exceptions import ProxyError, Timeout, HTTPError

# --- Google Cloud Firestore and Firebase Admin SDK Setup ---
from firebase_admin import initialize_app, firestore, messaging # ADDED: messaging
from google.cloud.exceptions import NotFound

try:
    # Initializes the Firebase Admin SDK using Application Default Credentials (GCP's Service Account)
    initialize_app()
    db = firestore.client()
except Exception as e:
    # Handle the common case where the script is run outside GCP credentials context
    print(f"Warning: Firestore Admin SDK initialization skipped/failed outside GCP: {e}")
    db = None

# --- Configuration & Environment Variables ---
TICKETMASTER_API_KEY = os.getenv("TICKETMASTER_API_KEY", "YOUR_TICKETMASTER_API_KEY")
MOCK_ROOT_COLLECTION = os.getenv("MOCK_ROOT_COLLECTION", "worker_monitor_jobs")

# Gmail Credentials
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

# Proxy Configuration
PROXY_URL = os.getenv("PROXY_URL")

# Critical Session/Anti-Bot Tokens (Manually maintained by the user)
TM_AUTH_COOKIE = os.getenv("TM_AUTH_COOKIE")
TM_QUEUE_TOKEN = os.getenv("TM_QUEUE_TOKEN")

# Target API Endpoint: Using the general Inventory Status URL but requiring the specific tokens/headers
TM_API_ENDPOINT = "https://app.ticketmaster.com/inventory-status/v1/availability"

# --- Notification Utility ---
def send_notification(job_id, contact_email, fcm_token, event_id, status, price_min, price_max):
    """Sends Gmail notification and FCM push notification."""
    
    price_range_str = f"($USD {price_min} - $USD {price_max})" if price_min else "(Price Unknown)"
    
    notification_content = (
        f"🚨 TICKET ALERT! 🚨\n"
        f"Event {event_id} status changed to: {status.replace('_', ' ')}.\n"
        f"Price Range: {price_range_str}\n"
        f"Buy Now: [Check Ticketmaster app/site]"
    )

    # --- 1. GMAIL (SMTP) Notification ---
    if GMAIL_USER and GMAIL_APP_PASSWORD and contact_email:
        msg = EmailMessage()
        msg.set_content(notification_content)
        msg['Subject'] = f"🚨 TICKET ALERT: Tickets Available for {event_id}"
        msg['From'] = GMAIL_USER
        msg['To'] = contact_email

        try:
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
                server.send_message(msg)
            print(f"Gmail notification sent to {contact_email} for job {job_id[:8]}...")
        except Exception as e:
            print(f"ERROR sending Gmail email to {contact_email}: {e}")
            if not GMAIL_APP_PASSWORD:
                 print("NOTE: Ensure GMAIL_APP_PASSWORD is correctly set as an App Password, not your main password.")
    else:
        print(f"--- MOCK EMAIL NOTIFICATION SENT ---\nTarget: {contact_email}\n{notification_content}\n-------------------------")
        if not GMAIL_USER:
            print("NOTE: Gmail credentials not configured. Set GMAIL_USER/GMAIL_APP_PASSWORD environment variables for real email.")


    # --- 2. FCM (Firebase Cloud Messaging) Push Notification ---
    if fcm_token:
        try:
            # Construct the push notification payload
            message = messaging.Message(
                notification=messaging.Notification(
                    title=f"🚨 TICKET ALERT: {event_id} 🚨",
                    body=f"Status: {status.replace('_', ' ')}. Price: {price_range_str}"
                ),
                data={
                    'jobId': job_id,
                    'eventId': event_id,
                },
                token=fcm_token,
            )
            # Send the message
            response = messaging.send(message)
            print(f"FCM Push notification sent successfully for job {job_id[:8]}...: {response}")
        except Exception as e:
            print(f"ERROR sending FCM push notification: {e}")
            print("NOTE: FCM requires the device to have the app installed, token saved to Firestore, and proper IAM permissions.")


# --- Critical Polling Logic (No changes needed here for functionality) ---
# ... (check_event_status remains the same)
def check_event_status(event_id):
    """
    Hardened check of the Ticketmaster inventory status using session tokens and proxy.
    """
    now = datetime.now(timezone.utc).isoformat()
    session = requests.Session()
    
    # --- MOCK LOGIC: If keys are missing or development ---
    if TICKETMASTER_API_KEY == "YOUR_TICKETMASTER_API_KEY":
        random.seed(event_id)
        # Simple persistence check for mock status (Simulates tickets becoming available)
        if datetime.now().minute >= 30 and random.random() < 0.6:
            status_key = "TICKETS_AVAILABLE"
            price_data = {"priceMin": round(random.uniform(50, 100), 2), 
                          "priceMax": round(random.uniform(150, 300), 2)}
        elif datetime.now().minute > 15:
            status_key = "FEW_TICKETS_LEFT"
            price_data = {"priceMin": round(random.uniform(70, 120), 2), 
                          "priceMax": round(random.uniform(180, 400), 2)}
        else:
            status_key = "TICKETS_NOT_AVAILABLE"
            price_data = {"priceMin": None, "priceMax": None}

        return status_key, {
            "status": status_key,
            "resaleStatus": "UNKNOWN",
            "priceMin": price_data["priceMin"],
            "priceMax": price_data["priceMax"],
            "last_checked": now
        }

    # --- REAL HARDENED API CALL ---

    # 1. Proxy Implementation
    if PROXY_URL:
        session.proxies = {'http': PROXY_URL, 'https': PROXY_URL}
        print(f"Using proxy: {PROXY_URL[:PROXY_URL.find('@')+1]}***@{PROXY_URL.split('@')[-1]}")


    # 2. Session & Headers (Critical for anti-bot/session maintenance)
    headers = {
        # User-Agent (Required per prompt)
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        # Cookie Header (Required per prompt)
        'Cookie': f'_tm_token={TM_AUTH_COOKIE}' if TM_AUTH_COOKIE else '',
        # Anti-Bot Header (Required per prompt)
        'x-tmpssmartqueuetoken': TM_QUEUE_TOKEN if TM_QUEUE_TOKEN else '',
        # Placeholder for other headers like x-tm-trace-id if needed
    }

    # 3. Target API & Query Parameters
    params = {
        'apikey': TICKETMASTER_API_KEY,
        'events': event_id,
        # Queue-it token must be passed as a query param (Required per prompt)
        'queueittoken': TM_QUEUE_TOKEN if TM_QUEUE_TOKEN else ''
    }
    
    response = None
    try:
        response = session.get(TM_API_ENDPOINT, params=params, headers=headers, timeout=15)
        
        # 4. Error Handling Checks (Required per prompt)
        
        # 302: Queue Redirect
        if response.status_code == 302:
            print(f"ERROR 302: Redirected to Queue for {event_id}. TM_QUEUE_TOKEN likely expired.")
            return 'QUEUE_REDIRECT', {"status": "QUEUE_REDIRECT", "last_checked": now}
        
        # 403: Forbidden (IP Ban/Expired Auth Cookie)
        if response.status_code == 403:
            print(f"ERROR 403: Forbidden access for {event_id}. Auth Cookie/IP blocked. Check TM_AUTH_COOKIE.")
            return 'FORBIDDEN', {"status": "FORBIDDEN", "last_checked": now}

        response.raise_for_status() # Raises HTTPError for 4xx/5xx responses

        data = response.json()
        
        event_data = data.get('events', [{}])[0]
        status = event_data.get('status', 'UNKNOWN')
        price_ranges = event_data.get('priceRanges', [])
        
        min_price = price_ranges[0]['min'] if price_ranges else None
        max_price = price_ranges[0]['max'] if price_ranges else None
        
        result_data = {
            "status": status,
            "resaleStatus": event_data.get('resaleStatus', 'UNKNOWN'),
            "priceMin": min_price,
            "priceMax": max_price,
            "last_checked": now
        }
        return status, result_data
            
    except ProxyError:
        print("API Request failed due to Proxy configuration error.")
        return 'PROXY_ERROR', {"status": "PROXY_ERROR", "last_checked": now}
    except HTTPError as e:
        # 429: Rate Limit Check (Required per prompt)
        if response is not None and response.status_code == 429:
             print(f"ERROR 429: Rate Limit hit for {event_id}. Status updated to RATE_LIMIT_ERROR.")
             return 'RATE_LIMIT_ERROR', {"status": "RATE_LIMIT_ERROR", "last_checked": now}
        print(f"API Request failed with HTTP Error: {e}")
        return 'API_ERROR', {"status": "API_ERROR", "last_checked": now}
    except Exception as e:
        print(f"An unexpected error occurred for {event_id}: {e}")
        return 'UNKNOWN_ERROR', {"status": "UNKNOWN_ERROR", "last_checked": now}


# --- Cloud Function Entry Point ---
def ticket_monitor_worker(request=None):
    """
    Main entry point for the scheduled Cloud Function.
    """
    if db is None:
        return "Worker not initialized. Check Firestore Admin SDK setup and environment.", 500
        
    print(f"Starting Ticketmaster monitoring job scan in collection: {MOCK_ROOT_COLLECTION}...")
    
    # Critical Check: Logging a warning if session tokens are missing
    if not TM_AUTH_COOKIE:
         print("WARNING: TM_AUTH_COOKIE is missing. Authenticated inventory checks will likely fail.")
    if not TM_QUEUE_TOKEN:
         print("WARNING: TM_QUEUE_TOKEN is missing. Worker may be redirected to the queue (302).")
    
    try:
        jobs_ref = db.collection(MOCK_ROOT_COLLECTION).where('status', '==', 'ACTIVE')
        jobs_stream = jobs_ref.stream()
        
        jobs_to_update = []
        
        for job_doc in jobs_stream:
            job_data = job_doc.to_dict()
            job_id = job_doc.id
            event_id = job_data.get('eventID')
            contact_email = job_data.get('contact') # Renamed variable to reflect content change
            fcm_token = job_data.get('fcm_token') # ASSUME FCM token is stored in the document
            
            if not event_id or not contact_email:
                print(f"Skipping job {job_id[:8]}...: Missing eventID or contact (email).")
                continue

            # 1. Check current availability
            new_status_key, new_availability_data = check_event_status(event_id)
            
            # 2. Parse the previous status for comparison
            previous_status_key = 'UNKNOWN'
            try:
                current_availability_json = job_data.get('current_availability')
                if current_availability_json:
                    previous_availability_data = json.loads(current_availability_json)
                    previous_status_key = previous_availability_data.get('status', 'UNKNOWN')
            except:
                pass 

            # 3. Determine if an action (Notification + DB Update) is needed
            
            # The trigger only fires if the status moves from unavailable/error to available/few left
            is_newly_available = (
                (new_status_key == 'TICKETS_AVAILABLE' or new_status_key == 'FEW_TICKETS_LEFT') and 
                (previous_status_key not in ['TICKETS_AVAILABLE', 'FEW_TICKETS_LEFT'])
            )
            
            needs_status_update = (new_status_key != previous_status_key) or is_newly_available 

            update_data = {
                'current_availability': json.dumps(new_availability_data)
            }
            
            if is_newly_available:
                send_notification(
                    job_id, 
                    contact_email, # Now passing email
                    fcm_token,     # Now passing FCM token
                    event_id, 
                    new_status_key, 
                    new_availability_data.get('priceMin'), 
                    new_availability_data.get('priceMax')
                )
                
                update_data['status'] = 'COMPLETE' 
                update_data['notificationSentAt'] = firestore.SERVER_TIMESTAMP
                print(f"Job {job_id[:8]}... TRIGGERED notification and marked COMPLETE.")
            
            if needs_status_update:
                jobs_to_update.append((job_id, update_data))
            
            if not is_newly_available and not needs_status_update:
                print(f"Job {job_id[:8]}... checked. Status is still {new_status_key}.")


        # Batch apply updates to Firestore for efficiency
        if jobs_to_update:
            batch = db.batch()
            for job_id, update_data in jobs_to_update:
                job_ref = db.collection(MOCK_ROOT_COLLECTION).document(job_id)
                batch.update(job_ref, update_data)
            
            batch.commit()
            print(f"Batch update completed for {len(jobs_to_update)} jobs.")
        else:
            print("No jobs required batch update.")

        return "Ticket monitor worker run successful.", 200

    except Exception as e:
        print(f"Critical error in worker: {e}")
        return f"Critical error in worker: {e}", 500


# --- Data Sync Function (from data_sync.py) ---
def sync_monitor_job(event, context):
    """
    Background Cloud Function triggered by Firestore onCreate.
    Syncs a new ticket monitor job from a user's private collection to the central worker collection.
    
    Trigger Path: /artifacts/{appId}/users/{userId}/ticket_monitors/{documentId}
    Target Path: worker_monitor_jobs/{documentId}
    
    Args:
        event (dict): The dictionary with data specific to this type of event.
        context (google.cloud.functions.Context): The Cloud Functions event context.
    """
    print(f"Sync Function Triggered! Resource: {context.resource}")
    
    if db is None:
        print("ERROR: Firestore DB not initialized.")
        return
    
    # Extract the document path and ID
    # context.resource is like: projects/PROJECT_ID/databases/(default)/documents/path/to/doc
    try:
        path_parts = context.resource.split('/documents/')[1].split('/')
        document_id = path_parts[-1]
        source_doc_path = context.resource.split('/documents/')[1]
        
        print(f"Processing Document ID: {document_id}")

        # Fetch the full document data from the source to ensure we have the latest state
        source_doc_ref = db.document(source_doc_path)
        doc_snapshot = source_doc_ref.get()
        
        if doc_snapshot.exists:
            job_data = doc_snapshot.to_dict()
            
            # Add metadata about the sync
            job_data['synced_at'] = firestore.SERVER_TIMESTAMP
            job_data['original_source_path'] = source_doc_path
            
            # Define the target collection
            # Using the same ID as the source document for consistency
            target_collection = "worker_monitor_jobs"
            target_ref = db.collection(target_collection).document(document_id)
            
            # Write to the central worker collection
            target_ref.set(job_data)
            
            print(f"SUCCESS: Synced job {document_id} to {target_collection}.")
        else:
            print(f"WARNING: Source document {source_doc_path} does not exist (maybe deleted?).")
            
    except Exception as e:
        print(f"ERROR: Failed to sync job: {e}")
        # Re-raising the exception ensures Cloud Functions retries the execution if configured
        raise e
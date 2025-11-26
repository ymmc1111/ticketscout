import os
from google.cloud import firestore

# Initialize Firestore Client
db = firestore.Client()

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
    
    # Extract the document path and ID
    # context.resource is like: projects/PROJECT_ID/databases/(default)/documents/path/to/doc
    path_parts = context.resource.split('/documents/')[1].split('/')
    document_id = path_parts[-1]
    source_doc_path = context.resource.split('/documents/')[1]
    
    print(f"Processing Document ID: {document_id}")

    try:
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
        print(f"ERROR: Failed to sync job {document_id}: {e}")
        # Re-raising the exception ensures Cloud Functions retries the execution if configured
        raise e
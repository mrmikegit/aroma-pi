#!/usr/bin/env python3
import json
import os
from pywebpush import webpush, WebPushException

VAPID_FILE = 'vapid.json'
SUBSCRIPTIONS_FILE = 'subscriptions.json'

def test_push():
    print("--- Push Notification Test Script ---")
    
    if not os.path.exists(VAPID_FILE):
        print(f"Error: {VAPID_FILE} not found. Keys generated yet?")
        return
    
    try:
        with open(VAPID_FILE) as f:
            vapid_data = json.load(f)
            private_key = vapid_data.get('privateKey')
            public_key = vapid_data.get('publicKey')
            print(f"VAPID Keys loaded.")
            print(f"Public Key: {public_key[:20]}...")
    except Exception as e:
        print(f"Error loading VAPID keys: {e}")
        return

    if not os.path.exists(SUBSCRIPTIONS_FILE):
        print(f"Error: {SUBSCRIPTIONS_FILE} not found. No subscribers yet.")
        return

    try:
        with open(SUBSCRIPTIONS_FILE) as f:
            subs = json.load(f)
    except Exception as e:
        print(f"Error loading subscriptions: {e}")
        return
        
    if not subs:
        print("No subscriptions found in file.")
        return

    print(f"Found {len(subs)} subscriptions.")
    
    message = json.dumps({"title": "Server Test", "body": "This is a direct test from the server script."})
    
    for i, sub in enumerate(subs):
        print(f"\nSubscription {i+1}:")
        endpoint = sub.get('endpoint', 'Unknown')
        print(f"Endpoint: {endpoint[:50]}...")
        
        try:
            response = webpush(
                subscription_info=sub,
                data=message,
                vapid_private_key=private_key,
                vapid_claims={"sub": "mailto:admin@example.com"}
            )
            print(f"Status Code: {response.status_code}")
            print("Success! Notification sent.")
        except WebPushException as ex:
            print(f"WebPush Failed: {ex}")
            if ex.response:
                print(f"Response: {ex.response.text}")
        except Exception as e:
            print(f"General Error: {e}")

if __name__ == "__main__":
    test_push()


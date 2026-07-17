from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import os
from dotenv import load_dotenv
from googleapiclient.errors import HttpError
from categorizer import CategorizePost
import base64
from fastapi import FastAPI
import requests
import uvicorn
from pydantic import BaseModel
import json

app = FastAPI()

load_dotenv()

client_id = os.getenv("CLIENT_ID")
print(client_id)
client_key = os.getenv("CLIENT_KEY")

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

config = {
    "installed": {
        "client_id": client_id,
        "client_secret": client_key,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"]
    }
}

flow = InstalledAppFlow.from_client_config(
    config,
    SCOPES
)

creds = flow.run_local_server(port=0)

service = build("gmail", "v1", credentials=creds)

LABEL_MAP = {
    "Important": "Label_8707031102432262693",
    "Newsletter": "Label_4919283065936577428",
    "Shopping": "Label_6626671709154876114",
    "Finance": "Label_8000216126106833058",
    "Notifications": "Label_3085830938984636436",
    "Spam": "Label_233584872602531714",
}

class Label(BaseModel):
    Important: str
    Newsletter: str
    Shopping: str
    Finance: str
    Notifications: str
    Spam: str


def get_body(payload):
    # Fall 1: direkte body data
    if "data" in payload.get("body", {}):
        data = payload["body"]["data"]
        return base64.urlsafe_b64decode(data).decode("utf-8")

    # Fall 2: multipart email
    if "parts" in payload:
        for part in payload["parts"]:
            if part["mimeType"] == "text/plain":
                data = part["body"].get("data")
                if data:
                    return base64.urlsafe_b64decode(data).decode("utf-8")

            # manchmal verschachtelt
            if "parts" in part:
                result = get_body(part)
                if result:
                    return result

    return None

@app.get("/get_labels")
def get_labels():
    global service
    labels = service.users().labels().list(userId="me").execute()

    return labels

@app.get("/remove_labels")
def remove_labels(how_many: int):
    global service
    try:
        # Call the Gmail API
        service = build("gmail", "v1", credentials=creds)
        results = (
            service.users().messages().list(userId="me", labelIds=["INBOX"], maxResults=how_many).execute()
        )
        messages = results.get("messages", [])

        if not messages:
            print("No messages found.")

        print("Messages:")
        for message in messages:
            print(f'Message ID: {message["id"]}')

            msg = service.users().messages().get(
                userId="me",
                id=message["id"],
                format="metadata"
            ).execute()

            existing_labels = msg.get("labelIds", [])
            protected = {
                "INBOX",
                "UNREAD",
                "SENT",
                "DRAFT",
                "SPAM",
                "TRASH"
            }

            remove_labels = [l for l in existing_labels if l not in protected]

            service.users().messages().modify(
                userId="me",
                id=message["id"],
                body={
                    "removeLabelIds": remove_labels
                }
            ).execute()
        
        return {
            "message": "Removed successfully"
        }

    except HttpError as error:
        # TODO(developer) - Handle errors from gmail API.
        print(f"An error occurred: {error}")

@app.get("/categorize")
def categorize(how_many: int, desired_labels: str):
    global service
    try:
        labels = json.loads(desired_labels)

        LABEL_MAP["Important"] = labels["Important"]
        LABEL_MAP["Newsletter"] = labels["Newsletter"]
        LABEL_MAP["Shopping"] = labels["Shopping"]
        LABEL_MAP["Finance"] = labels["Finance"]
        LABEL_MAP["Notifications"] = labels["Notifications"]
        LABEL_MAP["Spam"] = labels["Spam"]

        for label in labels:
            print(label)

        # Call the Gmail API
        service = build("gmail", "v1", credentials=creds)
        results = (
            service.users().messages().list(userId="me", labelIds=["INBOX"], maxResults=how_many).execute()
        )
        messages = results.get("messages", [])

        if not messages:
            print("No messages found.")

        print("Messages:")
        for message in messages:
            print(f'Message ID: {message["id"]}')
            msg = (
                service.users().messages().get(userId="me", id=message["id"], format="full").execute()
            )

            headers = msg["payload"]["headers"]

            subject = next(
                (h["value"] for h in headers if h["name"] == "Subject"),
                "(No Subject)"
            )

            text = subject + "           " + str(get_body(msg["payload"]))
            result = CategorizePost(text)
            category = result["category"].strip()

            label = LABEL_MAP.get(category, "")

            msg = service.users().messages().get(
                userId="me",
                id=message["id"],
                format="metadata"
            ).execute()

            existing_labels = msg.get("labelIds", [])

            if label in existing_labels:
                print("Already labeled, skipping")
                continue

            service.users().messages().modify(
                userId="me",
                id=message["id"],
                body={
                    "addLabelIds": [label]
                }
            ).execute()

        return {
            "message": "Funktion wurde aufgerufen",
            "how_many": how_many
        }

    except HttpError as error:
        # TODO(developer) - Handle errors from gmail API.
        print(f"An error occurred: {error}")
        return {
                "message": "Funktion wurde aufgerufen, aber ist gefailed",
                "how_many": how_many
            }


if __name__ == "__main__":
    print("API_READY", flush=True)

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000
    )

"""while True:
    user_input = input("Which action would you like to do? (Remove/Sort/Exit): ")

    if user_input == "Remove":
        how_many = input("How many?: ")
        remove_labels(int(how_many), service)
    elif user_input == "Sort":
        how_many = input("How many?: ")
        categorize(int(how_many), service)
    elif user_input == "Exit":
        break"""
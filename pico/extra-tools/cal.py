import datetime

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import dateparser

from registry import tool

SERVICE_ACCOUNT_FILE = "serv-acc.json"
SCOPES = ["https://www.googleapis.com/auth/calendar"]
CALENDAR_ID = "Your calendar ID goes here"

def parse_dt(text: str):
    dt = dateparser.parse(
        text,
        settings={
            "TIMEZONE": "Asia/Singapore",
            "RETURN_AS_TIMEZONE_AWARE": True,
            "PREFER_DATES_FROM": "future",
        },
    )
    return dt


@tool
def create_event(title: str, description: str, start: str, length: int = 30):
    """Creates a google calendar event. Title and description are self explanatory. 
    Start is the start of the event, it can be a human-readable date or time, provided as a str
    Length is the length of an event in minutes, provided as an int"""
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=SCOPES,
    )

    service = build("calendar", "v3", credentials=creds)

    start = parse_dt(start)
    print(start)

    end = start + datetime.timedelta(minutes=length)

    event = {
        "summary": title,
        "description": description,
        "start": {
            "dateTime": start.isoformat(),
            "timeZone": "UTC",
        },
        "end": {
            "dateTime": end.isoformat(),
            "timeZone": "UTC",
        },
    }

    try:
        created = (
            service.events()
            .insert(calendarId=CALENDAR_ID, body=event)
            .execute()
        )
        print(f"Created: {created.get('htmlLink')}")
    except HttpError as error:
        print(f"An error occurred: {error}")


@tool
def read_events():
    """Lists the next 10 upcoming events from the Google Calendar."""
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=SCOPES,
    )

    service = build("calendar", "v3", credentials=creds)

    try:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        events_result = (
            service.events()
            .list(
                calendarId=CALENDAR_ID,
                timeMin=now,
                maxResults=10,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])

        if not events:
            print("No upcoming events found.")
            return

        print("Next 10 upcoming events:")
        return_str  = ""
        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            summary = event.get("summary", "No Title")
            event_id = event.get("id")
            print(f"- [{event_id}] {start}: {summary}")
            return_str += (f"- [{event_id}] {start}: {summary}")
        return return_str

    except HttpError as error:
        print(f"An error occurred: {error}")


@tool
def delete_event(event_id: str):
    """Deletes a Google Calendar event using its unique event_id."""
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=SCOPES,
    )

    service = build("calendar", "v3", credentials=creds)

    try:
        service.events().delete(calendarId=CALENDAR_ID, eventId=event_id).execute()
        print(f"Successfully deleted event with ID: {event_id}")
    except HttpError as error:
        print(f"An error occurred while deleting the event: {error}")


if __name__ == "__main__":
    # main()
    pass

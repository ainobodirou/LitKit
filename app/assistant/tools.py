from langchain.tools import tool 

@tool
def create_calendar_event(
    title: str,
    start_time: str,
    end_time: str,
    attendees: list[str] | None, 
    location: str = "" | None,
) -> str:
    """Create a calendar event. Requires exact ISO datetime format."""
    # In practice, this calls the Google Calendar or Outlook API service
    return f"Event created: {title} from {start_time} to {end_time} with {len(attendees)} attendees"

@tool
def get_available_time_slots(
    attendees: list[str],
    date: str,  # ISO format: "2024-01-15"
    duration_minutes: int
) -> list[str]:
    """Check calendar availability for given attendees on a specific date."""
    # Stub: In practice, this would query calendar APIs
    return ["09:00", "14:00", "16:00"]
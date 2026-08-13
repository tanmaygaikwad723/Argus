from pydantic import BaseModel, Field
from typing import List, Optional


class QueryByActor(BaseModel):
    actor_name: str = Field(description="The name of actor of event. It can be a country, indiviual or organization")
    occured_after: Optional[str] = Field(
        default=None,
        description=(
            "Only include events after this date, formatted YYYY-MM-DD. "
            "Omit this parameter entirely if the user did not mention a start date."
        ),
    )
    occured_before: Optional[str] = Field(
        default=None,
        description=(
            "Only include events before this date, formatted YYYY-MM-DD. "
            "Omit this parameter entirely if the user did not mention an end date."
        ),
    )
    occured_on: Optional[str] = Field(
        default=None,
        description="Only include events on this exact date, formatted YYYY-MM-DD. Omit if not specified.",
    )


class QueryByActorNameandWords(BaseModel):
    actor_names: List[str] = Field(description="The name of actors who participated in the event. It can be a country, an individual  or an organization")
    words: List[str] = Field(description="The words or specific phrases that are related to the event.")
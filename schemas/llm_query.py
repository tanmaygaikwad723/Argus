from pydantic import BaseModel, Field
from typing import List, Optional, Generic, TypeVar



class DateFilterMixin(BaseModel):
    occured_after: Optional[str] = Field(
        default=None,
        description=(
            "Only include events happened/occured after this date, formatted YYYY-MM-DD."
            "Omit this parameter entirely if the user did not mention a start date."
        ),
    )
    occured_before: Optional[str] = Field(
        default=None,
        description=(
            "Only include events happened/occured before this date, formatted YYYY-MM-DD."
            "Omit this parameter entirely if the user did not mention a end date."
        ),
    )
    occured_on: Optional[str] = Field(
        default=None,
        description=(
            "Only include events happened/occured on this data, formatted YYYY-MM-DD."
            "Omit this parameter entirely if the user did not mention a date."
        )
    )


class QueryByActor(DateFilterMixin):
    actor_name: str = Field(description="The name of actor of event. It can be a country, indiviual or organization")


class QueryByActorNameandWords(DateFilterMixin):
    actor_names: List[str] = Field(description="The name of actors who participated in the event. It can be a country, an individual  or an organization")
    words: List[str] = Field(description="The words or specific phrases that are related to the event.")

    
class QueryByLocationandwords(DateFilterMixin):
    event_words : List[str] = Field("The word or specific phrases that are related to the event.")
    location: str = Field("The name of the location where the event has occured.")
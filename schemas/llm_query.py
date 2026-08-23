from pydantic import BaseModel, Field
from typing import List, Optional



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


class EventWordsFilterMixin(BaseModel):
    event_words: List[str] = Field("The word or specific phrases that are related to the event.")
    all: Optional[bool] = Field(default=True, description="Boolean field that indicates whether the event summary should " \
                                                "contain all the event words of the list or any one of them.")


class QueryByActor(DateFilterMixin):
    actor_name: str = Field(description="The name of actor of event. It can be a country, indiviual or organization")


class QueryByActorNameandWords(DateFilterMixin, EventWordsFilterMixin):
    actor_names: List[str] = Field(description="The name of actors who participated in the event. It can be a country, an individual  or an organization")

    
class QueryByLocationandwords(DateFilterMixin, EventWordsFilterMixin):
    location: str = Field("The name of the location where the event has occured.")


class QueryByEventwords(DateFilterMixin,EventWordsFilterMixin):
    pass


class QueryByLocation(DateFilterMixin):
    location: str = Field(description="The name of the location where the event has occured")
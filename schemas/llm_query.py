from pydantic import BaseModel, Field
from typing import List

class QueryByActor(BaseModel):
    actor_name: str = Field(description="The name of actor of event. It can be a country, indiviual or organization")


class QueryByActorNameandWords(BaseModel):
    actors: List[str] = Field(description="The name of actors who participated in the event. It can be a country, an individual  or an organization")
    words: List[str] = Field(description="The words or specific phrases that are related to the event.")
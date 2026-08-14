from langchain_core.tools import BaseTool
from schemas.llm_query import QueryByActor, QueryByActorNameandWords, QueryByLocationandwords
from pydantic import BaseModel
from agent.semantic_layer import query_by_actor, query_by_actor_and_eventword, query_by_event_and_location
from typing import Type, List, Optional
from datetime import date as date_type, datetime


def safe_parse_date(value: str | None) -> date_type | None:
    """
    Converts a date string to a date object.
    Handles the common LLM quirk of sending the literal string
    'None' / 'null' / '' instead of omitting the field or using real null.
    """
    if value is None:
        return None
    if isinstance(value, str) and value.strip().lower() in ("none", "null", ""):
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


class QueryByActorTool(BaseTool):
    name: str = "Query_by_actor_name"
    description: str = (
        "Use this tool to find events involving a specific actor, "
        "optionally filtered by date range or an exact date."
    )
    args_schema: Type[BaseModel] = QueryByActor


    def _run(
            self,
            actor_name:str,
            occured_on: Optional[str] = None,
            occured_before: Optional[str] = None,
            occured_after: Optional[str] = None
    )->List[dict]:
        """Using the tool"""
        after  = safe_parse_date(occured_after)
        before = safe_parse_date(occured_before)
        on     = safe_parse_date(occured_on)

        return query_by_actor(
            actor_name,
            occured_after=after,
            occured_before=before,
            occured_on=on,
        ).result_set


class QueryByActorAndWordsTool(BaseTool):
    name: str = "Query_by_actor_names_and_words"
    description: str = (
        "Use this tool when you have information about actors as well as certain words that are related to event."
        "Optionally filtered by date range or exact date."
    )
    args_schema: Type[BaseModel] = QueryByActorNameandWords

    def _run(
            self,
            actor_names:List[str],
            words: List[str],
            occured_on: Optional[str] = None,
            occured_before: Optional[str] = None,
            occured_after: Optional[str] = None,
    )->List[dict]:
        """Using the tool"""
        on = safe_parse_date(occured_on)
        before = safe_parse_date(occured_before)
        after = safe_parse_date(occured_after)
        return query_by_actor_and_eventword(
            actor_names, 
            words,
            occured_on=on,
            occured_before=before,
            occured_after=after
            ).result_set


class QueryByLocationandWordsTool(BaseTool):
    name: str = "Query_by_eventwords_and_location"
    description: str = (
    "Use this tool when you have information about the location where the event happened as well as certain words that are related to event."
    "Optionally filtered by date range or exact date"
    )
    args_schema: Type[BaseModel] = QueryByLocationandwords

    def _run(
            self,
            event_words: List[str],
            location: str,
            occured_on: Optional[str] = None,
            occured_before: Optional[str] = None,
            occured_after: Optional[str] = None,
    ) -> List[dict]:
        """Using the tool"""
        on = safe_parse_date(occured_on)
        before = safe_parse_date(occured_before)
        after = safe_parse_date(occured_after)
        return query_by_event_and_location(
            event_words, 
            location,
            occured_after=after, 
            occured_before=before, 
            occured_on=on
            ).result_set

    
    
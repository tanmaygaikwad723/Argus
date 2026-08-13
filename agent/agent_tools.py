from langchain_core.tools import BaseTool
from schemas.llm_query import QueryByActor, QueryByActorNameandWords
from pydantic import BaseModel
from agent.semantic_layer import query_by_actor, query_by_actor_and_eventword, store_event_article_pairs
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

        response = query_by_actor(
            actor_name,
            occured_after=after,
            occured_before=before,
            occured_on=on,
        )
        events_list = store_event_article_pairs(response)
        return events_list


class QueryByActorAndWordsTool(BaseTool):
    name: str = "Query_by_actor_names_and_words"
    description: str = (
        "Useful when you have information about actors as well as certain words that are related to event to query information about event."
    )
    args_schema: Type[BaseModel] = QueryByActorNameandWords

    def _run(
            self,
            actor_names:List[str],
            words: List[str],
    )->List[dict]:
        """Using the tool"""
        response = query_by_actor_and_eventword(actor_names, words)
        events_list = store_event_article_pairs(response)
        return events_list
    
    
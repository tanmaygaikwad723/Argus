from langchain_core.tools import BaseTool
from schemas.llm_query import QueryByActor, QueryByActorNameandWords

from pydantic import BaseModel
from agent.semantic_layer import query_by_actor, query_by_actor_and_eventword, store_event_article_pairs

from typing import Type, List


class QueryByActorTool(BaseTool):
    name: str = "Query by actor name"
    description: str = (
        "Useful when you are given only the name of actor, to extract or query information about any event."
    )
    args_schema: Type[BaseModel] = QueryByActor


    def _run(
            self,
            actor_name:str,
    )->List[dict]:
        """Using the tool"""
        response = query_by_actor(actor_name)
        events_list = store_event_article_pairs(response)
        return events_list


class QueryByActorAndWordsTool(BaseTool):
    name: str = "Query by actor names and words."
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
    
    
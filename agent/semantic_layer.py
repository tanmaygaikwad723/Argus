from db.connection import graph
from typing import List, Optional, Callable
from datetime import date
from db.connection import graph as native_graph
from falkordb.graph import Graph
from functools import wraps
from dataclasses import dataclass, field


@dataclass
class QueryParts:
    match: str
    return_clause: str
    where: List[str] = field(default_factory=list)
    params: dict = field(default_factory=dict)
    graph: Graph = native_graph


def with_date_filter(func: Callable) -> Callable:
    """ 
    Wraps a semantic layer function that returns QueryParts object.
    Injects occured_after / occured_before / occured_on filtering on e.date,
    assembles the final cypher query string and executes it.
    """
    @wraps(func)
    def wrapper(
            *args,
            occured_after: Optional[date] = None,
            occured_before: Optional[date] = None,
            occured_on: Optional[date] = None,
            **kwargs,
    ):
        parts = func(*args, **kwargs)

        if occured_after and occured_before:
            if occured_after >=  occured_before:
                raise ValueError("occured after date must be less than occured before date")
            parts.where.append("e.date > date($occured_after) AND e.date < date($occured_before)")
            parts.params["occured_after"] = occured_after.isoformat()
            parts.params["occured_before"] = occured_before.isoformat()
        elif occured_before:
            parts.where.append("e.date < date($occured_before)")
            parts.params["occured_before"] = occured_before.isoformat()
        elif occured_after:
            parts.where.append("e.date > date($occured_after)")
            parts.params["occured_after"] = occured_after.isoformat()
        elif occured_on:
            parts.where.append("e.date = date($occured_on)")
            parts.params["occured_on"] = occured_on.isoformat()

        query = parts.match + "\n"
        if parts.where:
            query += "WHERE " + " AND ".join(parts.where) + "\n"

        query += parts.return_clause

        return parts.graph.query(query, params=parts.params)
    
    return wrapper


@with_date_filter
def query_by_actor(actor_name: str) -> QueryParts:
    return QueryParts(
        match="MATCH (a:Actor)-[r:PARTICIPATED_IN]->(e:Event)",
        where=["toLower(a.name) CONTAINS $name", "e.summary IS NOT NULL"],
        return_clause= """ 
        OPTIONAL MATCH (e)<-[r2:MENTIONS]-(n:NewsArticle)
        OPTIONAL MATCH (n)<-[r3:PUBLISHED]-(p:Publisher)
        RETURN flex.json.toJson({event: CASE WHEN e IS NOT NULL THEN properties(e) ELSE {} END,
            participated_rel: CASE WHEN r IS NOT NULL THEN properties(r) ELSE {} END,
            actor: CASE WHEN a IS NOT NULL THEN properties(a) ELSE {} END,
            mentions_rel: CASE WHEN r2 IS NOT NULL THEN properties(r2) ELSE {} END,
            article: CASE WHEN n IS NOT NULL THEN properties(n) ELSE {} END,
            published_rel: CASE WHEN r3 IS NOT NULL THEN properties(r3) ELSE {} END,
            publisher: CASE WHEN p IS NOT NULL THEN properties(p) ELSE {} END}) AS graph_context LIMIT 10
            """,
        params= {"name": actor_name.lower()}
    )


@with_date_filter
def query_by_actor_and_eventword(actor_names:List[str], event_words:List[str], all:bool=True):
    return QueryParts(
        match = "MATCH (a:Actor)-[r:PARTICIPATED_IN]->(e:Event)",
        where = ["ANY(name in $actors WHERE toLower(a.name) CONTAINS name)",
                 "e.summary IS NOT NULL",
                 "ALL(word IN $words WHERE toLower(e.summary) CONTAINS word)" if all else "ANY(word IN $words WHERE toLower(e.summary) CONTAINS word)"],
        return_clause = """ 
        OPTIONAL MATCH (e)<-[r2:MENTIONS]-(n:NewsArticle)
        OPTIONAL MATCH (n)<-[r3:PUBLISHED]-(p:Publisher)
        RETURN flex.json.toJson({event: CASE WHEN e IS NOT NULL THEN properties(e) ELSE {} END,
        participated_rel: CASE WHEN r IS NOT NULL THEN properties(r) ELSE {} END,
        actor: CASE WHEN a IS NOT NULL THEN properties(a) ELSE {} END,
        mentions_rel: CASE WHEN r2 IS NOT NULL THEN properties(r2) ELSE {} END,
        article: CASE WHEN n IS NOT NULL THEN properties(n) ELSE {} END,
        published_rel: CASE WHEN r3 IS NOT NULL THEN properties(r3) ELSE {} END,
        publisher: CASE WHEN p IS NOT NULL THEN properties(p) ELSE {} END}) AS graph_context LIMIT 10
        """,
        params={"actors": [names.lower() for names in actor_names], "words": [words.lower() for words in event_words]}
    )


@with_date_filter
def query_by_event_and_location(event_words:List[str], location:str, all:bool=True):
    return QueryParts(
        match = "MATCH (e:Event)-[r:OCCURED_AT]->(l:Location)",
        where = ["ALL(word IN $words WHERE toLower(e.summary) CONTAINS word)" if all else "ANY(word IN $words WHERE toLower(e.summary) CONTAINS word)",
                 "e.summary IS NOT NULL",
                 "toLower(l.name) CONTAINS $location"],
        return_clause = """ 
        OPTIONAL MATCH (e)<-[r2:MENTIONS]-(n:NewsArticle)
        OPTIONAL MATCH (n)<-[r3:PUBLISHED]-(p:Publisher)
        OPTIONAL MATCH (e)<-[r4:PARTICIPATED_IN]-(a:Actor)
        RETURN flex.json.toJson({event: CASE WHEN e IS NOT NULL THEN properties(e) ELSE {} END,
        occured_at_rel: CASE WHEN r IS NOT NULL THEN properties(r) ELSE {} END,
        location: CASE WHEN l IS NOT NULL THEN properties(l) ELSE {} END,
        mentions_rel: CASE WHEN r2 IS NOT NULL THEN properties(r2) ELSE {} END,
        article: CASE WHEN n IS NOT NULL THEN properties(n) ELSE {} END,
        published_rel: CASE WHEN r3 IS NOT NULL THEN properties(r3) ELSE {} END,
        publisher: CASE WHEN p IS NOT NULL THEN properties(p) ELSE {} END,
        participated_rel: CASE WHEN r4 IS NOT NULL THEN properties(r4) ELSE {} END,
        actor: CASE WHEN a IS NOT NULL THEN properties(a) ELSE {} END}) AS graph_context LIMIT 10
        """,
        params = {"words":[w.lower() for w in event_words], "location": location.lower()}
    )

@with_date_filter
def query_by_event(event_words:List[str], all:bool = True) -> QueryParts:
    return QueryParts(
        match= "MATCH (e:Event)",
        where= ["ALL(word IN $words WHERE toLower(e.summary) CONTAINS word)" if all else "ANY(word IN $words WHERE toLower(e.summary) CONTAINS word)",
                 "e.summary IS NOT NULL"],
        return_clause= """ 
        OPTIONAL MATCH (e)<-[r:PARTICIPATED_IN]-(a:Actor)
        OPTIONAL MATCH (e)<-[r2:MENTIONS]-(n:NewsArticle)
        RETURN flex.json.toJson({
            event: CASE WHEN e IS NOT NULL THEN properties(e) ELSE {} END,
            participated_rel: CASE WHEN r IS NOT NULL THEN properties(r) ELSE {} END,
            actor: CASE WHEN a IS NOT NULL THEN properties(a) ELSE {} END,
            mentions_rel: CASE WHEN r2 IS NOT NULL THEN properties(r2) ELSE {} END,
            article: CASE WHEN n IS NOT NULL THEN properties(n) ELSE {} END
        }) AS graph_context LIMIT 10
        """,
        params={"words": [word.lower() for word in event_words]}) 


@with_date_filter
def query_by_location(location:str) -> QueryParts:
    return QueryParts(
        match = "MATCH (l:Location)<-[r:OCCURED_AT]-(e:Event)",
        where = ["toLower(l.name) CONTAINS $location", "e.summary IS NOT NULL"],
        return_clause = """ 
        OPTIONAL MATCH (e)<-[r2:PARTICIPATED_IN]-(a:Actor)
        OPTIONAL MATCH (e)<-[r3:MENTIONS]-(n:NewsArticle)
        RETURN flex.json.toJson({
        event: CASE WHEN e IS NOT NULL THEN properties(e) ELSE {} END,
        participated_rel: CASE WHEN r2 IS NOT NULL THEN properties(r2) ELSE {} END,
        actor: CASE WHEN a IS NOT NULL THEN properties(a) ELSE {} END,
        occured_rel: CASE WHEN r IS NOT NULL THEN properties(r) ELSE {} END,
        location: CASE WHEN l IS NOT NULL THEN properties(l) ELSE {} END,
        mentions_rel: CASE WHEN r3 IS NOT NULL THEN properties(r3) ELSE {} END,
        article: CASE WHEN n IS NOT NULL THEN properties(n) ELSE {} END
        }) AS graph_context LIMIT 10
    """ ,
    params={"location": location}
    )
from db.connection import graph
from typing import List, Optional, Callable
from datetime import date
from db.models import Event, Actor, NewsArticle, Publisher
from db.connection import graph as native_graph
from falkordb.graph import Graph
from falkordb.query_result import QueryResult
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
            if occured_after <= occured_before:
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
def query_by_actor(actor_name: str, graph:Graph=native_graph) -> QueryParts:
    return QueryParts(
        match="MATCH (a:Actor)-[r:PARTICIPATED_IN]->(e:Event)",
        where=["toLower(a.name) CONTAINS $name", "e.summary IS NOT NULL"],
        return_clause= """ 
        OPTIONAL MATCH (e)<-[r2:MENTIONS]-(n:NewsArticle)
        OPTIONAL MATCH (n)<-[r3:PUBLISHED]-(p:Publisher)
        RETURN [a, r, e, r2, n, r3, p] AS row LIMIT 10
        """,
        params= {"name": actor_name.lower()}
    )


def store_event_article_pairs(response:QueryResult):
    return_list = []
    if len(response.result_set) > 1:
        for i in range(len(response.result_set)):
            for row in response.result_set[i]:
                actor, participation, event, mentions, article,  publish, publisher = row
                actor_obj = Actor(name=actor.properties["name"], country_code=actor.properties["country_code"], type=actor.properties["type"])
                event_obj = Event(external_id=event.properties["externalid"], date=event.properties["date"], quad_class=event.properties["quad_class"],\
                                num_mentions=event.properties["num_mentions"], isrootevent=event.properties["isrootevent"],\
                                goldsteinscale=event.properties["goldsteinscale"], summary=event.properties["summary"])
                publisher_obj = Publisher(name=publisher.properties["name"])
                article_obj = NewsArticle(url=article.properties["url"])
                return_list.append({'actor':actor_obj, 'event':event_obj, 'newsarticle':article_obj, 'publisher':publisher_obj})
    else: 
        return []
    return return_list


def query_by_actor_and_eventword(actor_names:List[str], event_words:List[str], graph:Graph=native_graph):
    params = {
        "actors":[names.lower() for names in actor_names],
        "words":[words.lower() for words in event_words]
	}
    query = """ 
		MATCH (a:Actor)-[r:PARTICIPATED_IN]->(e:Event)
			WHERE ANY(name IN $actors WHERE toLower(a.name) CONTAINS name) 
			AND e.summary IS NOT NULL 
			AND ALL(word IN $words WHERE toLower(e.summary) CONTAINS word)
			OPTIONAL MATCH (e)<-[r2:MENTIONS]-(n:NewsArticle)
			OPTIONAL MATCH (n)<-[r3:PUBLISHED]-(p:Publisher)
			RETURN [a, r, e, r2, n, r3, p] AS row LIMIT 10
		"""
    return graph.query(query, params=params)




    
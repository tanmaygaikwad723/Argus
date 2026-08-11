from db.connection import graph
from typing import List
from db.models import Event, Location, Actor, NewsArticle, Publisher
from db.connection import graph as native_graph
from falkordb.graph import Graph
from falkordb.query_result import QueryResult


def query_by_actor(actor_name:str, graph:Graph=native_graph):
    params = {
        "name":actor_name.lower()
    }
    query = """
	MATCH (a:Actor)-[r:PARTICIPATED_IN]->(e:Event)
    WHERE toLower(a.name) CONTAINS $name AND e.summary IS NOT NULL
    OPTIONAL MATCH (e)<-[r2:MENTIONS]-(n:NewsArticle)
    OPTIONAL MATCH (n)<-[r3:PUBLISHED]-(p:Publisher)
    RETURN [a, r, e, r2, n, r3, p] AS row LIMIT 10
	"""
    return graph.query(query, params=params)


def store_event_article_pairs(response:QueryResult):
    return_list = []
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




    
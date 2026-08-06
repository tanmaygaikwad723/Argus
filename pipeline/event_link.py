import pandas as pd
import numpy as np
from falkordb import FalkorDB
from dataclasses import dataclass
from falkordb_orm import node, relationship, property
from datetime import date
from falkordb.graph import Graph
from falkordb.node import Node
from collections import Counter
from db.models import Event, Actor
from pathlib import Path
from tqdm.notebook import tqdm
from falkordb.query_result import QueryResult
from typing import List, Dict
import os
from db.connection import graph

def print_node_details(response_obj:QueryResult):
    for row in response_obj.result_set:
        for node in row:
            if isinstance(node, Node):
                print(f"Node type : {node.labels}")
                print(f" Node properties : {node.properties}")
            else:
                print(f"Edge : {node}")


def query_events(graph:Graph, ext_list:List[str])->List[Event]:
    query = """ 
    MATCH (e:Event)
    WHERE e.externalid IN $ext_list
    RETURN
        e.externalid AS externalid,
        toString(e.date) AS date,
        e.quad_class AS quad_class,
        e.num_mentions AS num_mentions,
        e.goldsteinscale AS goldstein_scale,
        e.isrootevent AS isrootevent
    """
    events_list = []
    params = {
        'ext_list': ext_list
    }
    response = graph.query(query, params=params)
    for row in response.result_set:
        externalid, date_str, quad_class, num_mentions, goldsteinscale, is_root = row
        if externalid is None:
            continue
        events_list.append(
            Event(
                external_id = externalid,
                date = date_str,
                quad_class= int(quad_class) if quad_class is not None else 0,
                num_mentions= int(num_mentions) if num_mentions is not None else 0,
                goldsteinscale= float(goldsteinscale) if goldsteinscale is not None else 0.0,
                isrootevent= int(is_root) if is_root is not None else 0
            )
        )
        
    return events_list



def query_actors(graph:Graph, event_list:List[Event]) -> List[List[Actor]]:
    if not event_list:
        return []
    ext_list = [e.external_id for e in event_list]
    query = """ 
    MATCH (e:Event)<-[r:PARTICIPATED_IN]-(a:Actor) WHERE e.externalid IN $ext_list
    RETURN
        e.externalid AS event_id,
        a.name as actor_name,
        a.type as actor_type,
        a.country_code as actor_country_code
    """

    params = {
        'ext_list': ext_list
    }
    response = graph.query(query, params=params)

    result : Dict[str, List[Actor]] = {e.external_id: [] for e in event_list}
    seen: Dict[str, List[str]] = {e.external_id: [] for e in event_list}

    for row in response.result_set:
        (event_id, actor_name, actor_type, actor_country_code) = row

        if actor_name not in seen[event_id]:
            result[event_id].append(Actor(name=actor_name, type=actor_type, country_code=actor_country_code))
            seen[event_id].append(actor_name)
        else:
            continue

        if event_id not in result:
            continue

    return result


def match_actors(actors_dict:dict):
    actors_name_list = []
    for event in actors_dict:
        actors_name_list.append([a.name for a in actors_dict[event]])
    return Counter(actors_name_list[0]) == Counter(actors_name_list[1])


def match_actor_type(actors_dict:dict):
    actor_type_list = []
    for event in actors_dict:
        actor_type_list.append([a.type for a in actors_dict[event]])
    return Counter(actor_type_list[0]) == Counter(actor_type_list[1])


def match_swap_actors(actors_dict:dict):
    actor_list = []
    for event in actors_dict:
        actor_list.append([a.name for a in actors_dict[event]])
    return list(reversed(actor_list[0])) == actor_list[1]


def link_events(graph:Graph, article_mentioned_events:dict):
    created_relations = 0
    total_possible_relations = 0
    for article in article_mentioned_events:
        temp_event_list = list(article_mentioned_events[article])
        len_temp_list = len(temp_event_list)
        total_possible_relations += int((len_temp_list*(len_temp_list-1))/2)
        for i in range(len(temp_event_list)-1):
            for j in range(i+1, len(temp_event_list)):
                event_link_score = 0.4
                id_pairs = [temp_event_list[i], temp_event_list[j]]
                events_list = query_events(graph, id_pairs)
                if len(events_list) != 2:
                    continue
                actors_list = query_actors(graph, events_list)
                if match_actors(actors_list):
                    event_link_score += 0.3
                elif match_actor_type(actors_list):
                    event_link_score += 0.25
                elif match_swap_actors(actors_list):
                        event_link_score += 0.2
                if event_link_score >= 0.6:
                    event_link_query ="""
                    MATCH (e1:Event {externalid: $ext1})
                    MATCH (e2:Event {externalid: $ext2})
                    MERGE (e1)-[r:RELATED_TO]->(e2)
                    ON CREATE SET r.link_score = $link_score,
                                  r.created_at = localdatetime()
                    ON MATCH SET  r.link_score = $link_score
                    """
                    params = {
                        'ext1':id_pairs[0],
                        'ext2':id_pairs[1],
                        'link_score':event_link_score
                    }
                    response = graph.query(event_link_query, params=params)
                    if response.relationships_created == int(1):
                        created_relations += 1
    return created_relations, total_possible_relations


def create_relations_from_file(graph:Graph, dir_path:Path):
    total_possible_relations = 0
    created_relations = 0
    files = list(file for file in Path(dir_path).iterdir() if file.is_file())
    for file in tqdm(files, leave=True, dynamic_ncols=True):
        data = pd.read_csv(file, encoding="utf-8", on_bad_lines="skip")
        event_link_pairs = {}
        for link in data["MentionIdentifier"].unique():
            event_link_pairs[link] = set(str(eid) for eid in data[data["MentionIdentifier"] == link]["GlobalEventID"])
            
        int1, int2 = link_events(graph=graph, article_mentioned_events=event_link_pairs)
        total_possible_relations += int2
        created_relations += int1

    print(f"The total possible relations that could have been created were : {total_possible_relations}.\n\
          But the actual total number of relations created are : {created_relations}")

    
if __name__ == "__main__":
    BASE_DIR = Path(__file__).resolve().parent.parent
    mentions_path = BASE_DIR / "gdelt_raw" / "mentions" / "2026"
    create_relations_from_file(graph, mentions_path)
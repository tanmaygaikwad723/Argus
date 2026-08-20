from db.connection import graph as native_graph
from falkordb.graph import Graph
from db.models import Event, Actor
from typing import List, Set, Tuple, Dict
from collections import Counter
from tqdm.notebook import tqdm
import pandas as pd
from pathlib import Path
import os


def fetch_existing_event_ids(event_ids: Set[str], chunk_size:int = 5000, graph:Graph = native_graph) -> Set[str]:
    """ 
    Checks which event IDs actually exist in the database in the bulk.
    """
    existing_ids = set()
    event_ids_list = list(event_ids)

    query = """ 
	MATCH (e:Event)
    WHERE e.externalid IN $ext_list
    RETURN e.externalid AS externalid
	"""
    for i in range(0, len(event_ids), chunk_size):
        chunk = event_ids_list[i : i + chunk_size]
        response = graph.query(query, params={"ext_list": chunk})
        for row in response.result_set:
            if row[0] is not None:
                existing_ids.add(str(row[0]))
    return existing_ids



def fetch_actors_batch(existing_event_ids:Set[str], chunk_size:int = 5000, graph:Graph = native_graph):
    """ 
    Fetches actors only for verified existing events in batch.
    """
    actor_map: Dict[str, List[dict]] = {eid : [] for eid in existing_event_ids}
    event_ids_list = list(existing_event_ids)

    query = """ 
		MATCH (e:Event)<-[p:PARTICIPATED_IN]-(a:Actor)
    WHERE e.externalid IN $ext_list
    RETURN e.externalid AS event_id, a.name as name, a.type AS type
		"""

    for i in range(0, len(event_ids_list), chunk_size):
        chunk = event_ids_list[i : i + chunk_size]
        response = graph.query(query, params={"ext_list": chunk})
        seen_actors = set()
        for row in response.result_set:
            event_id, actor_name, actor_type = row[0], row[1], row[2]
            key = (event_id, actor_name)
            if key not in seen_actors:
                actor_map[event_id].append({"name": actor_name, "type": actor_type})
                seen_actors.add(key)

    return actor_map

        
def compute_link_score(actors1:List[dict], actors2:List[dict]) -> float:
    """ Calculates the heuristic link score"""
    score = 0.4
    if not actors1 or not actors2:
        return score
    names1 = [a["name"] for a in actors1]
    names2 = [b["name"] for b in actors2]
    types1 = [a["type"] for a in actors1]
    types2 = [b["type"] for b in actors2]

    if Counter(names1) == Counter(names2):
        score += 0.3
    if Counter(types1) == Counter(types2):
        score += 0.25
    elif list(reversed(names1)) == names2:
        score += 0.2

    return score


def batch_create_relations(relations: List[dict], batch_size: int = 2000, graph:Graph = native_graph) -> int:
    """ Create relationships in bulk using UNWIND"""
    query = """ 
    UNWIND $batch AS item
    MATCH (e1:Event {externalid: item.ext1})
    MATCH (e2:Event {externalid: item.ext2})
    MERGE (e1)-[r:RELATED_TO]->(e2)
    ON CREATE SET r.link_score = item.score, r.created_at = localdatetime()
    ON MATCH SET r.link_score = item.score
    """

    total_created = 0
    for i in range(0, len(relations), batch_size):
        chunk = relations[i : i + batch_size]
        response = graph.query(query, params={"batch": chunk})
        total_created += getattr(response, "realationships_created", 0)

    return total_created


def process_mentions_file(file_path: Path, graph:Graph = native_graph) -> Tuple[int, int]:

    data = pd.read_csv(file_path,
                       usecols=["MentionIdentifier", "GlobalEventID"],
                       dtype={"MentiondIdentifier": str, "GlobalEventID": str},
                       on_bad_lines="skip").dropna()

    article_events = data.groupby("MentionIdentifier")["GlobalEventID"].unique().to_dict()
    candidate_pairs: Set[Tuple[str, str]] = set()
    all_candidate_events: Set[str] = set()
    total_possible_relations = 0

    for event_ids in article_events.values():
        n = len(event_ids)
        if n < 2:
            continue

        total_possible_relations += (n * (n - 1)) // 2
        for i in range(n - 1):
            for j in range(i + 1, n):
                u, v = event_ids[i], event_ids[j]
                if u != v:
                    pair = (u, v) if u < v else (v, u)
                    candidate_pairs.add(pair)
                    all_candidate_events.add(u)
                    all_candidate_events.add(v)

    if not candidate_pairs:
        return 0, total_possible_relations

    existing_event_ids = fetch_existing_event_ids(all_candidate_events)

    valid_pairs = [
        (u, v) for (u, v) in candidate_pairs
        if u in existing_event_ids and v in existing_event_ids
    ]

    if not valid_pairs:
        return 0, total_possible_relations


    valid_event_ids = {eid for pair in valid_pairs for eid in pair}
    actor_map = fetch_actors_batch(valid_event_ids)

    relations_to_create = []
    for ext1, ext2 in valid_pairs:
        actors1 = actor_map.get(ext1, [])
        actors2 = actor_map.get(ext2, [])
        score = compute_link_score(actors1, actors2)
        if score >= 0.6:
            relations_to_create.append({"ext1": ext1, "ext2": ext2, "score": score})

    created_relations = batch_create_relations(relations_to_create)
    return created_relations, total_possible_relations    



def create_relations_from_file(dir_path: Path, graph:Graph = native_graph):
    total_possible = 0
    total_created = 0
    files = [f for f in dir_path.iterdir() if f.is_file()]

    for file in tqdm(files, leave=True, dynamic_ncols=True):
        created, possible = process_mentions_file(file)
        total_created += created
        total_possible += possible

    print(f"Total possible pairs evaluated: {total_possible}\n"
          f"Total relationships created: {total_created}")

    
if __name__ == "__main__":
    BASE_DIR = Path(__file__).resolve().parent.parent
    mentions_path = BASE_DIR / "gdelt_raw" / "mentions" / "2026"
    create_relations_from_file(native_graph, mentions_path)
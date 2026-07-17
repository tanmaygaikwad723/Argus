from db.connection import graph as native_graph
from falkordb import graph
from pathlib import Path
import pandas as pd
from tqdm import tqdm


def check_mentions_exist(news_url:str, event_id:str, graph:graph=native_graph)-> bool:
  query = """ 
    MATCH (n:NewsArticle)-[r:MENTIONS]->(e:Event)
    WHERE n.url=$url AND e.externalid=$externalid
    RETURN  COUNT(r) > 0 as relationexist
  	"""
  params = {
      "url":news_url,
      "externalid": event_id
		}
  
  response = graph.query(query, params=params)
  return response.result_set[0][0]


def create_mentions_pair(data:pd.DataFrame):
    event_link_pairs = {}
    for link in data["MentionIdentifier"].unique():
      event_link_pairs[link] = set(str(eid) for eid in data[data["MentionIdentifier"] == link]["GlobalEventID"])
    return event_link_pairs

def add_mentions_props(params:dict, graph:graph=native_graph):
    query = """MATCH (e:Event {externalid:$GlobalEventID}), (n:NewsArticle {url:$MentionIdentifier})
    MERGE (e)<-[r:MENTIONS]-(n)
    SET
		r.sentence_id=$SentenceID,
        r.mention_type=$MentionType,
        r.inraw_text=$InRawText,
        r.confidence=$Confidence,
        r.doc_len=$MentionDocLen
    """
    response = graph.query(query, params=params)
    return response


def add_mentions_properties(dir_path):
	total_mentions_instances = 0
	mention_properties_added = 0
	files = list(Path(dir_path).iterdir())
	for file in tqdm(files, leave=True, dynamic_ncols=True):
		data = pd.read_csv(file, on_bad_lines="skip", encoding="utf-8")
		event_link_pairs = create_mentions_pair(data)
		for link in event_link_pairs:
			for event in event_link_pairs[link]:
				if check_mentions_exist(link, event):
					total_mentions_instances += 1
					link_check = data["MentionIdentifier"] == link
					event_check = data["GlobalEventID"] == int(event)
					row = data[link_check & event_check].sort_values(by="Confidence", ascending=False)\
						.drop(columns=["MentionDocTranslationInfo", "Extras"]).iloc[0, :]
					params = {
						"GlobalEventID": str(row["GlobalEventID"]),
						"MentionIdentifier":str(row["MentionIdentifier"]),
						"MentionType":row["MentionType"],
						"InRawText":row["InRawText"],
						"MentionDocLen":row["MentionDocLen"],
						"SentenceID":row["SentenceID"],
						"Confidence":row["Confidence"]
					}
					response = add_mentions_props(params)
					if response.properties_set == "5.0":
						mention_properties_added += 1
				else:
					continue
	print(f"Total mentions relationships found = {total_mentions_instances}")
	print(f"Total mentions relationships where properties were added = {mention_properties_added}")
	

if __name__ == "__main__":
    dir_path = "../gdelt_raw/mentions/2026"
    add_mentions_properties(dir_path)
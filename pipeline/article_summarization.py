import torch
device = "cuda" if torch.cuda.is_available() else "cpu"
import pandas as pd
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, pipeline
import socket
from falkordb import FalkorDB, graph, Edge, Node
from falkordb import QueryResult
from typing import List
from google.colab import userdata
from dataclasses import dataclass
import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import trafilatura
import logging
import waybackpy
from trafilatura.settings import use_config
from concurrent.futures import ThreadPoolExecutor
from trafilatura import extract, fetch_url
from trafilatura.downloads import add_to_compressed_dict, buffered_downloads, load_download_buffer
from collections import OrderedDict


model_name = "sshleifer/distilbart-cnn-12-6"
hf_token = userdata.get("HF_TOKEN")

tokenizer = AutoTokenizer.from_pretrained(model_name, token=hf_token)
device = "cuda" if torch.cuda.is_available() else "cpu"
model = AutoModelForSeq2SeqLM.from_pretrained(model_name, token=hf_token).to(device)

print(f"Model and tokenizer loaded successfully on {device}.")

falkordb_username = userdata.get("FALKORDB_USERNAME")
falkordb_token = userdata.get("FALKORDB_TOKEN")

host = "srisx-2401-4900-1c44-42f0-59d1-a720-5a99-5686.run.pinggy-free.link"
port = 42391

try:
    sock = socket.create_connection((host, port), timeout=10)
    print("TCP connection works")
    sock.close()
except Exception as e:
    print(f"TCP failed: {e}")

db = FalkorDB(host=host, port=port, username='default', password=falkordb_token, ssl=False, socket_timeout=5)
print("FalkorDB client initialized successfully using 'default' mapping!")

native_graph = db.select_graph("Geopolitics")
native_graph


def query_mentions_relation(graph:graph=native_graph):
  query = """
  MATCH (e:Event)<-[r:MENTIONS]-(n:NewsArticle)
  WITH e, COLLECT(r) as relations, COUNT(DISTINCT n) AS article_count, COLLECT(DISTINCT n) AS articles
  WHERE article_count > 0 AND e.summary IS NULL
  RETURN {event_id: e.externalid, relations: relations, articles: articles} AS result
  ORDER BY rand()
  LIMIT 32
  """
  try:
    response = graph.query(query)
  except TimeoutError as e:
    print(f"Timeout error occurred")
    return None
  return response

def print_details(query_result:QueryResult):
  for objs in query_result.result_set:
    for obj in objs:
      event_dict = {obj["event_id"]: zip(obj["relations"], obj["articles"])}
      print(event_dict)

def zip_event_details(result:QueryResult):
  events_dict = {}
  for objs in result.result_set:
    for obj in objs:
      events_dict[obj["event_id"]] = list(zip(obj["relations"], obj["articles"]))
  return events_dict

def calculate_event_article_link_score(events_info:dict):
  event_article_links = {}
  for event in events_info.keys():
    event_article_links[event] = []

    for relation, article in events_info[event]:
      event_link_score = 0
      try:
        props = relation.properties
        if int(props.get('confidence', 0)) > 60:
          event_link_score += 0.35
        if int(props.get('mention_type', 0)) == 3:
          event_link_score += 0.25
        if int(props.get('inraw_text', 0)):
          event_link_score += 0.2
        if int(props.get('sentence_id', 99)) <= 10:
          event_link_score += 0.1
        if int(props.get('doc_len', 0)) >= 4000:
          event_link_score += 0.05
        elif int(props.get('doc_len', 0)) < 4000:
          event_link_score += 0.025
      except (AttributeError, ValueError, TypeError) as e:
        print(f"Error processing relation: {e}")

      url = article.properties.get('url', 'No URL')
      event_article_links[event].append((url, event_link_score))

  return event_article_links

def create_event_link_dataframe(event_article_score:dict):
  flattened_data = []
  for event_id, articles in event_article_score.items():
    for url, score in articles:
      flattened_data.append({'Event_ID': event_id, 'URL': url, 'Score': score})

  scores_df = pd.DataFrame(flattened_data)

  scores_df = scores_df[scores_df['Score'] > 0.30].copy()

  scores_df['Max_Event_Score'] = scores_df.groupby('Event_ID')['Score'].transform('max')

  scores_df = scores_df.sort_values(
        by=['Max_Event_Score', 'Event_ID', 'Score'],
        ascending=[False, True, False]
    ).drop(columns=['Max_Event_Score']).reset_index(drop=True)

  return scores_df

def summarize_batched_articles(articles: List[str]):
    """Standard batch summarization with safety truncation."""
    if not articles:
        return []

    encoded = tokenizer(
        articles,
        padding=True,
        truncation=True,
        max_length=1024,
        return_tensors="pt"
    ).to(device)

    summarized = model.generate(
        input_ids=encoded["input_ids"],
        attention_mask=encoded["attention_mask"],
        max_length=300,
        min_length=100
    )

    return tokenizer.batch_decode(summarized, skip_special_tokens=True)

def process_single_article(text: str, max_chunk_len: int = 1024) -> str:
    """Helper to recursively chunk and summarize a single long text until it fits."""
    inputs = tokenizer(text, return_tensors="pt", add_special_tokens=False)
    input_ids = inputs["input_ids"][0]

    if len(input_ids) <= max_chunk_len:
        return text

    chunks = []
    for i in range(0, len(input_ids), max_chunk_len):
        chunk_ids = input_ids[i : i + max_chunk_len]
        chunks.append(tokenizer.decode(chunk_ids, skip_special_tokens=True))

    chunk_summaries = summarize_batched_articles(chunks)
    combined_summary = " ".join(chunk_summaries)

    return process_single_article(combined_summary, max_chunk_len)

def full_pipeline_summarize(articles: List[str]):
    """Processes a list of articles: chunks long ones, then summarizes everything in a final batch."""
    processed_texts = []
    for text in articles:
        if len(tokenizer.encode(text, add_special_tokens=False)) > 1024:
            processed_texts.append(process_single_article(text))
        else:
            processed_texts.append(text)

    return summarize_batched_articles(processed_texts)

def extract_article_text(article_link:str):
  html_content = fetch_url(url=article_link)
  extracted_text = extract(html_content, favor_precision=True)
  return extracted_text

logging.getLogger('trafilatura').setLevel(logging.CRITICAL)

THREADS = 10
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'

session = requests.Session()
session.headers.update({
    'User-Agent': USER_AGENT,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
})

adapter = HTTPAdapter(pool_connections=THREADS, pool_maxsize=THREADS, max_retries=Retry(total=3, backoff_factor=1))
session.mount("http://", adapter)
session.mount("https://", adapter)

new_config = use_config()
if not new_config.has_section('download'):
    new_config.add_section('download')
new_config.set('download', 'user-agent', USER_AGENT)

def scrape_single_article(url):
    """Manual fetch using requests session to bypass 403s."""
    html_content = None
    try:
        resp = session.get(url, timeout=15, allow_redirects=True)
        if resp.status_code == 200:
            html_content = resp.text

        if not html_content:
            try:
                wayback = waybackpy.Url(url, USER_AGENT)
                archive = wayback.near()
                if archive:
                    wb_resp = session.get(archive.archive_url, timeout=15)
                    if wb_resp.status_code == 200: html_content = wb_resp.text
            except Exception: pass

        if html_content:
            return url, trafilatura.extract(html_content, favor_precision=True, config=new_config)
        return url, None
    except Exception: return url, None

def fetch_news_article_parallel(articles_df):
    links = articles_df["URL"].unique().tolist()
    results = {}
    print(f"[NEW SCRAPER] Fetching {len(links)} unique URLs...")
    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        thread_results = list(executor.map(scrape_single_article, links))
    for url, text in thread_results:
        results[url] = text
    return results

def add_batched_event_summaries(params:dict, graph:graph=native_graph):
  query = """
  UNWIND $rows AS row
  MATCH (e:Event {externalid: row.GlobalEventID})
  SET
  e.summary = row.summary
  """
  response = graph.query(query, params=params)
  return response

def add_summaries_to_db():
    graph_query_result = query_mentions_relation()
    zipped_event_details = zip_event_details(graph_query_result)
    event_link_scores = calculate_event_article_link_score(zipped_event_details)
    event_links_df = create_event_link_dataframe(event_link_scores)

    if event_links_df.empty:
        return None

    # Ensuring we call the specific NEW scraper function
    extracted_content_map = fetch_news_article_parallel(event_links_df)
    event_links_df["Article_Text"] = event_links_df["URL"].map(extracted_content_map)

    events_to_summarize = event_links_df[event_links_df["Article_Text"].notna()].reset_index(drop=True)

    if events_to_summarize.empty:
        print("No articles could be scraped in this iteration.")
        return None

    event_summaries = full_pipeline_summarize(events_to_summarize["Article_Text"].to_list())
    summaries_df = pd.DataFrame(event_summaries, columns=["summary"])

    full_events_df = pd.concat([events_to_summarize, summaries_df], axis=1)
    events_list = [{"GlobalEventID": str(row["Event_ID"]), "summary": row["summary"]} for _, row in full_events_df.iterrows()]

    return add_batched_event_summaries(params={"rows": events_list}), len(events_list)

events_summary_count = 0
for i in range(200):
    print(f"Sequence {i+1}/100...")
    query_response, summarized_event = add_summaries_to_db()

    if query_response is not None:
        events_summary_count += summarized_event

    if events_summary_count > 0 and events_summary_count % 10 == 0:
        print(f"Current progress: {events_summary_count} summaries set.")
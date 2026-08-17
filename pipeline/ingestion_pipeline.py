import pandas as pd
import numpy as np
from falkordb import FalkorDB
from datetime import date
from pathlib import Path
from urllib.parse import urlparse
from tqdm.notebook import tqdm
from db.connection import graph


EVENT_COLUMNS = [
    'GlobalEventID', 'Day', 'MonthYear', 'Year', 'FractionDate',
    'Actor1Code', 'Actor1Name', 'Actor1CountryCode', 'Actor1KnownGroupCode', 'Actor1EthnicCode', 'Actor1Religion1Code', 'Actor1Religion2Code', 'Actor1Type1Code', 'Actor1Type2Code', 'Actor1Type3Code',
    'Actor2Code', 'Actor2Name', 'Actor2CountryCode', 'Actor2KnownGroupCode', 'Actor2EthnicCode', 'Actor2Religion1Code', 'Actor2Religion2Code', 'Actor2Type1Code', 'Actor2Type2Code', 'Actor2Type3Code',
    'IsRootEvent', 'EventCode', 'EventBaseCode', 'EventRootCode', 'QuadClass', 'GoldsteinScale', 'NumMentions', 'NumSources', 'NumArticles', 'AvgTone',
    'Actor1Geo_Type', 'Actor1Geo_FullName', 'Actor1Geo_CountryCode', 'Actor1Geo_ADM1Code', 'Actor1Geo_ADM2Code', 'Actor1Geo_Lat', 'Actor1Geo_Long', 'Actor1Geo_FeatureID',
    'Actor2Geo_Type', 'Actor2Geo_FullName', 'Actor2Geo_CountryCode', 'Actor2Geo_ADM1Code', 'Actor2Geo_ADM2Code', 'Actor2Geo_Lat', 'Actor2Geo_Long', 'Actor2Geo_FeatureID',
    'ActionGeo_Type', 'ActionGeo_FullName', 'ActionGeo_CountryCode', 'ActionGeo_ADM1Code', 'ActionGeo_ADM2Code', 'ActionGeo_Lat', 'ActionGeo_Long', 'ActionGeo_FeatureID',
    'DATEADDED', 'SOURCEURL'
]

def classify_actor(actor_code: str, actor_type1: str) -> str:
    """
    Classifies the actor into one of the following categories based on its code, and type1 property
    [Nation, Individual, Goverment, Military, Rebel groups, political party, Organization, Civilian]
    """
    iso3166_alpha3 = [
    "ABW", "AFG", "AGO", "AIA", "ALA", "ALB", "AND", "ARE", "ARG", "ARM",
    "ASM", "ATA", "ATF", "ATG", "AUS", "AUT", "AZE", "BDI", "BEL", "BEN",
    "BES", "BFA", "BGD", "BGR", "BHR", "BHS", "BIH", "BLM", "BLR", "BLZ",
    "BMU", "BOL", "BRA", "BRB", "BRN", "BTN", "BVT", "BWA", "CAF", "CAN",
    "CCK", "CHE", "CHL", "CHN", "CIV", "CMR", "COD", "COG", "COK", "COL",
    "COM", "CPV", "CRI", "CUB", "CUW", "CXR", "CYM", "CYP", "CZE", "DEU",
    "DJI", "DMA", "DNK", "DOM", "DZA", "ECU", "EGY", "ERI", "ESH", "ESP",
    "EST", "ETH", "FIN", "FJI", "FLK", "FRA", "FRO", "FSM", "GAB", "GBR",
    "GEO", "GGY", "GHA", "GIB", "GIN", "GLP", "GMB", "GNB", "GNQ", "GRC",
    "GRD", "GRL", "GTM", "GUF", "GUM", "GUY", "HKG", "HMD", "HND", "HRV",
    "HTI", "HUN", "IDN", "IMN", "IND", "IOT", "IRL", "IRN", "IRQ", "ISL",
    "ISR", "ITA", "JAM", "JEY", "JOR", "JPN", "KAZ", "KEN", "KGZ", "KHM",
    "KIR", "KNA", "KOR", "KWT", "LAO", "LBN", "LBR", "LBY", "LCA", "LIE",
    "LKA", "LSO", "LTU", "LUX", "LVA", "MAC", "MAF", "MAR", "MCO", "MDA",
    "MDG", "MDV", "MEX", "MHL", "MKD", "MLI", "MLT", "MMR", "MNE", "MNG",
    "MNP", "MOZ", "MRT", "MSR", "MTQ", "MUS", "MWI", "MYS", "MYT", "NAM",
    "NCL", "NER", "NFK", "NGA", "NIC", "NIU", "NLD", "NOR", "NPL", "NRU",
    "NZL", "OMN", "PAK", "PAN", "PCN", "PER", "PHL", "PLW", "PNG", "POL",
    "PRI", "PRK", "PRT", "PRY", "PSE", "PYF", "QAT", "REU", "ROU", "RUS",
    "RWA", "SAU", "SDN", "SEN", "SGP", "SGS", "SHN", "SJM", "SLB", "SLE",
    "SLV", "SMR", "SOM", "SPM", "SRB", "SSD", "STP", "SUR", "SVK", "SVN",
    "SWE", "SWZ", "SXM", "SYC", "SYR", "TCA", "TCD", "TGO", "THA", "TJK",
    "TKL", "TKM", "TLS", "TON", "TTO", "TUN", "TUR", "TUV", "TWN", "TZA",
    "UGA", "UKR", "UMI", "URY", "USA", "UZB", "VAT", "VCT", "VEN", "VGB",
    "VIR", "VNM", "VUT", "WLF", "WSM", "YEM", "ZAF", "ZMB", "ZWE"
]

    code  = (actor_code  or "").strip().upper()
    type1 = (actor_type1 or "").strip().upper()

    # Pure nation state: exactly 3-char ISO code, no type suffix
    if len(code) == 3 and code in iso3166_alpha3 and not type1:
        return "NATION"

    # Explicit individual
    if type1 == "IND":
        return "INDIVIDUAL"

    # Government / state institutions
    if type1 in {"GOV"}:
        return "GOVERNMENT"

    # Military / security forces
    if type1 in {"MIL", "AMN", "COP"}:
        return "MILITARY"

    # Non-state armed actors
    if type1 in {"REB", "CRM"}:
        return "REBEL"

    # Political actors
    if type1 in {"OPP", "PTY"}:
        return "POLITICAL"

    # Organisations
    if type1 in {"IGO", "NGO", "MED", "EDU", "BUS"}:
        return "ORGANIZATION"

    # Population-level actors
    if type1 in {"CVL", "GRP"}:
        return "CIVILIAN"

    return "UNKNOWN"


def event_ingestion_pipeline(data:pd.DataFrame):
    """ 
    Filter geopolitically significant events and add their data to the graph
    """
    num_sources_filter = data["NumArticles"] >= 4
    filtered_data = data[num_sources_filter]
    event_significance_filter = (filtered_data["GoldsteinScale"] <= -7.0) | (filtered_data["GoldsteinScale"] >= 7.0)
    goldstein_filtered_data = filtered_data[event_significance_filter]
    critical_roots = ['15', '14', '16', '17', '18', '19', '20']
    category_filter = (goldstein_filtered_data['QuadClass'] == 4) | (goldstein_filtered_data['EventRootCode'].astype(str).isin(critical_roots))
    category_filtered_events = goldstein_filtered_data[category_filter]
    if len(filtered_data) == 0:
        # print(f"No signifincant event found.")
        return 0
    
    success = 0
    skipped = 0
    for index, row in category_filtered_events.iterrows():
        if pd.isna(row.get("GlobalEventID")) or pd.isna(row.get("Day")) or pd.isna(row.get("SOURCEURL")):
            skipped += 1
            continue

        ext_id = str(int(row["GlobalEventID"]))
        evt_date = str(row["Day"])
        evt_year = int(row["Year"])
        news_url = str(row["SOURCEURL"])
        evt_num_mentions = int(row["NumMentions"])
        quad_class = int(row["QuadClass"])
        goldsteinscale = float(row["GoldsteinScale"])
        isroot = int(row["IsRootEvent"])

        try:
            publisher = urlparse(news_url).netloc or "Unknown Publisher"
        except:
            publisher = "Unknown Publisher"

        query = """
        MERGE (e:Event {externalid: $ext_id, date: date($date)})
        SET e.quad_class = $quad_class, e.num_mentions = $evt_num_mentions, e.goldsteinscale = $goldsteinscale, e.isrootevent = $isroot

        MERGE (y:Year {value: $evt_year})

        MERGE (p:Publisher {name: $publisher})

        MERGE (n:NewsArticle {url: $news_url})

        MERGE (n)-[:MENTIONS]->(e)
        MERGE (n)<-[:PUBLISHED]-(p)
        MERGE (e)-[:OCCURED_IN_YEAR]->(y)
        """

        params = {
            'ext_id': ext_id,
            'quad_class':quad_class,
            'date':evt_date,
            'evt_num_mentions':evt_num_mentions,
            'goldsteinscale': goldsteinscale,
            'isroot': isroot,
            'evt_year': evt_year,
            'publisher': publisher,
            'news_url': news_url
        }


        actor1_code = str(row["Actor1Code"]) if not pd.isna(row["Actor1Code"]) else None
        actor1_name = str(row["Actor1Name"]) if not pd.isna(row["Actor1Name"]) else None
        actor1_type1_code = str(row["Actor1Type1Code"]) if not pd.isna(row["Actor1Type1Code"]) else None
        actor1_type = classify_actor(actor1_code, actor1_type1_code)
        actor1_country_code = str(row["Actor1CountryCode"]) if not pd.isna(row["Actor1CountryCode"]) else None

        actor2_code = str(row["Actor2Code"]) if not pd.isna(row["Actor2Code"]) else None
        actor2_name = str(row["Actor2Name"]) if not pd.isna(row["Actor2Name"]) else None
        actor2_type1_code = str(row["Actor2Type1Code"]) if not pd.isna(row["Actor2Type1Code"]) else None
        actor2_type = classify_actor(actor2_code, actor2_type1_code)
        actor2_country_code = str(row["Actor2CountryCode"]) if not pd.isna(row["Actor2CountryCode"]) else None

        if actor1_country_code is None:
            actor1_country_code = ""

        if actor1_code and actor1_name:
            query += """ 
            MERGE (a1:Actor {name:$actor1_name, country_code:$actor1_country_code})
            SET a1.type = $actor1_type

            MERGE (a1)-[:PARTICIPATED_IN]->(e)
            """
            params["actor1_name"] = actor1_name
            params["actor1_country_code"] = actor1_country_code
            params["actor1_type"] = actor1_type

        if actor2_country_code is None:
            actor2_country_code = ""
          
        if actor2_name and actor2_code:
            query += """
            MERGE (a2:Actor {name:$actor2_name, country_code:$actor2_country_code})
            SET a2.type = $actor2_type

            MERGE (a2)-[:PARTICIPATED_IN]->(e)
    """
            params["actor2_name"] = actor2_name
            params["actor2_type"] = actor2_type
            params["actor2_country_code"] = actor2_country_code


        loc_name = str(row["ActionGeo_FullName"]) if not pd.isna(row["ActionGeo_FullName"]) else None
        loc_lat = str(row["ActionGeo_Lat"]) if not pd.isna(row["ActionGeo_Lat"]) else None
        loc_long = str(row["ActionGeo_Long"]) if not pd.isna(row["ActionGeo_Long"]) else None
        loc_type = str(row["ActionGeo_Type"]) if not pd.isna(row["ActionGeo_Type"]) else None

        if loc_name:
            query += """ 
            MERGE (l:Location {name:$loc_name}) """
            params["loc_name"] = loc_name

            if loc_long is not None and loc_lat is not None:
                query += """    
            SET l.latitude = $loc_lat, l.longitude = $loc_long, l.type = $loc_type
"""
            params["loc_type"] = loc_type
            params["loc_lat"] = loc_lat
            params["loc_long"] = loc_long

            query += """MERGE (e)-[:OCCURED_AT]->(l)"""

        try:
            graph.query(query, params=params)
            success += 1
            # if success %50 == 0:
                # print(f"Streamed {success} events to docker database.")
        except Exception as e:
            print(f"An error of type : {e} occured.")

    return success


def events_data_ingestion_pipeline(dir_path:str):
    """ 
    Iterate over all the events files and their data to the graph database
    """
    directory = Path(dir_path)

    total_rows_processed = 0
    files = list(file for file in directory.iterdir() if file.is_file())

    for file in tqdm(files, desc="Processing CSV files", leave=True, dynamic_ncols=True):
        try:
            data = pd.read_csv(file, encoding="utf-8", on_bad_lines="skip")
        except Exception as e:
            print(f"Error occured during reading file : {file}, error : {e}.")
            continue
        rows_success = event_ingestion_pipeline(data)
        # print(f"Number of events successfully added from file : {file} is  {rows_success}")
        total_rows_processed += rows_success

    print(f"Total number of events processed is : {total_rows_processed}")


if __name__ == "__main__":
        BASE_DIR = Path(__file__).resolve().parent.parent
        events_dir = BASE_DIR / "gdelt_raw" / "events" / "2026"
        events_data_ingestion_pipeline(events_dir)
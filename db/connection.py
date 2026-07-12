from falkordb import FalkorDB
from config import DB_HOST, DB_PORT, GRAPH_NAME


_db = FalkorDB(host=DB_HOST, port=DB_PORT)
graph = _db.select_graph(GRAPH_NAME)

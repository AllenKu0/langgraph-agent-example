from psycopg_pool import ConnectionPool
from langgraph.checkpoint.mongodb import MongoDBSaver
from pymongo import MongoClient


class ExternalSaver:
    def __init__(self, db_url):
        self.mongodb_client = MongoClient(db_url)
    
    def get_checkpointer(self):
        checkpointer = MongoDBSaver(self.mongodb_client)
        return checkpointer  
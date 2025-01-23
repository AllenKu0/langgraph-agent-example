from langgraph.checkpoint.mongodb import MongoDBSaver
from pymongo import MongoClient


class ExternalSaver:
    def __init__(self, db_url):
        self.mongodb_client = MongoClient(db_url)
        self.db = self.mongodb_client["ai_agent_db"]
        self.collection = self.db["chat_history"]
        # user test
        self.user_id = "test_user"
    def get_checkpointer(self):
        checkpointer = MongoDBSaver(self.mongodb_client)
        return checkpointer
    
    def insert_thread(self, thread_id, chat_history, now_graph_index):
        self.collection.insert_one({"user_id": self.user_id, "threads": [{"thread_id": thread_id, "chat_history": chat_history, "now_graph_index": now_graph_index, "is_initailized": False}]})
    
    def update_thread_initailized(self, thread_id, is_initailized):
        filter_query = {"user_id": self.user_id, "threads.thread_id": thread_id}
        update_query = {"$set": {"threads.$.is_initailized": is_initailized}}
        self.collection.update_one(filter_query, update_query)
        
    def create_thread(self, thread_id, chat_history, now_graph_index):
        filter_query = {"user_id": self.user_id}
        update_query = {"$push": {"threads":{"thread_id": thread_id, "chat_history": chat_history, "now_graph_index": now_graph_index, "is_initailized": False}}}
        self.collection.update_one(filter_query, update_query)
        
    def update_thread(self, thread_id, chat_history, now_graph_index):
        filter_query = {"user_id": self.user_id, "threads.thread_id": thread_id}
        update_query = {"$set": {"threads.$.chat_history": chat_history, "threads.$.now_graph_index": now_graph_index}}
        self.collection.update_one(filter_query, update_query)
        
    def get_thread(self, thread_id):
        try: 
            thread = self.collection.find_one({"user_id": self.user_id, "threads.thread_id": thread_id})
            filter_query = {"user_id": self.user_id}
            projection = {"threads": {"$elemMatch": {"thread_id": thread_id}}, "_id": 0}
            result = self.collection.find_one(filter_query, projection)
        
            # If result exists, return the thread, otherwise return None
            if result and "threads" in result:
                return result
            else:
                print(f"Thread with thread_id '{thread_id}' not found.")
                return None
        except Exception as e:
                print(f"get_chat_history Error: {e}")    
                return None
        
    def get_all_thread_id(self):
        user_data  = self.collection.find_one({"user_id": self.user_id}, {"threads.thread_id": 1, "_id": 0})
        if user_data and "threads" in user_data:
            thread_ids = [thread["thread_id"] for thread in user_data["threads"] if "thread_id" in thread]
            return thread_ids
        else:
            return [] 
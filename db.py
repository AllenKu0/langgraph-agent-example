from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


class ExternalSaver:
    def __init__(self, db_url, kwargs):
        self.pool = ConnectionPool(
            conninfo=db_url,
            max_size=20,
            kwargs=kwargs,
        )
    
    def get_checkpointer(self):
        checkpointer = PostgresSaver(self.pool)
        checkpointer.setup()
        return checkpointer  
        
    # async def get_async_checkpointer():
    #     async with AsyncPostgresSaver(
    #         conninfo=self.db_url,
    #         max_size=20,
    #         kwargs=self.kwargs,
    #     ) as pool:
    #         checkpointer = pool
    #         await checkpointer.setup()
    #         return checkpointer   




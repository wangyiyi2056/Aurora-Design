import asyncio
from aurora_ext.rag.storage.networkx_graph import NetworkXGraphStorage
import json

async def test():
    storage = NetworkXGraphStorage("rag_graph", {"working_dir": "./data/rag"})
    await storage._ensure_loaded()
    res = await storage.get_connected_subgraph("*", max_nodes=5)
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    asyncio.run(test())

import asyncio
from aurora_ext.rag.storage.networkx_graph import NetworkXGraphStorage

async def test():
    # Use existing test-kb to load the graph
    storage = NetworkXGraphStorage("rag_graph", {"working_dir": "./data/rag"})
    await storage._ensure_loaded()
    print("Graph loaded. Nodes:", len(storage._graph.nodes))
    
    try:
        res = await storage.get_connected_subgraph("*")
        print("Success!", len(res["nodes"]))
    except Exception as e:
        print("Error!", repr(e))
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())

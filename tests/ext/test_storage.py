from aurora_ext.storage.chroma_store import ChromaVectorStore


def test_chroma_store_add_and_search():
    store = ChromaVectorStore(collection_name="test-store")
    vectors = [[1.0] + [0.0] * 383, [0.0] * 384]
    ids = store.add_vectors(
        vectors=vectors,
        texts=["hello world", "aurora is great"],
        metadatas=[{"tag": "a"}, {"tag": "b"}],
    )
    assert len(ids) == 2
    results = store.search(vector=vectors[0], top_k=2)
    assert len(results) <= 2

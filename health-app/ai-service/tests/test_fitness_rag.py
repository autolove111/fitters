from fitness_rag import retrieve_fitness_guidance


def test_retrieves_relevant_guidance_for_knee_and_strength_context():
    citations = retrieve_fitness_guidance(
        query="beginner with knee discomfort needs a safe weekly strength and aerobic plan",
        limit=3,
    )

    assert len(citations) >= 2
    joined = " ".join(item["text"].lower() for item in citations)
    assert "strength" in joined
    assert "moderate" in joined or "aerobic" in joined
    assert all(item["source"] for item in citations)

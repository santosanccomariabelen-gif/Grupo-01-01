from agent.infrastructure.search.hybrid import fuse_rankings, keyword_scores


def test_keyword_scores_prefer_chunks_with_rare_question_words():
    chunk_texts = ["el plazo del reclamo es de 15 días", "el banco atiende el reclamo", "contracargo de una compra"]
    scores = keyword_scores("contracargo de una compra", chunk_texts)
    assert scores.index(max(scores)) == 2
    assert scores[0] < scores[2]


def test_keyword_scores_ignore_accents_and_case():
    scores = keyword_scores("debito", ["Tarjeta de DÉBITO", "Tarjeta de crédito"])
    assert scores[0] > 0
    assert scores[1] == 0


def test_fuse_rankings_rewards_ids_ranked_high_in_both_lists():
    fused = fuse_rankings([["a", "b", "c"], ["b", "d", "a"]])
    assert [item_id for item_id, _ in fused][:2] == ["b", "a"]

from agent.infrastructure.llm.foundry_chat_model import partial_reply


def test_partial_reply_includes_the_text_still_being_written():
    assert partial_reply('{"intent": "greeting", "answer": "Ho') == {"intent": "greeting", "answer": "Ho"}
    assert partial_reply('{"intent": "salu') == {"intent": "salu"}
    assert partial_reply("") == {}

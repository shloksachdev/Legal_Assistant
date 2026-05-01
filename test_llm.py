import os
from dotenv import load_dotenv
load_dotenv()

from langchain_huggingface import HuggingFaceEndpoint, ChatHuggingFace
from langchain_core.messages import HumanMessage
llm = HuggingFaceEndpoint(repo_id="HuggingFaceH4/zephyr-7b-beta", max_new_tokens=10)
chat = ChatHuggingFace(llm=llm)
print(chat.invoke([HumanMessage(content="Hello")]))

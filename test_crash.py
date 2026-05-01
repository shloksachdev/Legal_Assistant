import sys
import traceback

def main():
    try:
        from templex.agent import chat_agent
        print("Agent loaded.")
        sid = chat_agent.create_session()
        print(f"Session {sid} created. Querying...")
        res = chat_agent.chat(sid, "fetch live cases for property taxation")
        print("Response received:")
        print(res)
    except Exception as e:
        print("EXCEPTION CAUGHT:")
        traceback.print_exc()

if __name__ == "__main__":
    main()

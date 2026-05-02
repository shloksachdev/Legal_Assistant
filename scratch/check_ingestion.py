from templex.db.connection import KuzuConnection

def check_ingestion():
    try:
        conn = KuzuConnection.get_connection()
        
        # Count Work nodes
        res = conn.execute("MATCH (n:Work) RETURN count(n)")
        work_count = res.get_next()[0]
        
        # Count Expression nodes
        res = conn.execute("MATCH (n:Expression) RETURN count(n)")
        expr_count = res.get_next()[0]
        
        # Count Action nodes
        res = conn.execute("MATCH (n:Action) RETURN count(n)")
        action_count = res.get_next()[0]
        
        print(f"Work nodes: {work_count}")
        print(f"Expression nodes: {expr_count}")
        print(f"Action nodes: {action_count}")
        
    except Exception as e:
        print(f"Error checking ingestion: {e}")

if __name__ == "__main__":
    check_ingestion()

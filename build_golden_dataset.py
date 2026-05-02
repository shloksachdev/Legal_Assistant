"""Golden Dataset Pre-Ingestion Script.

Uses the High-Confidence Autonomous Research Pipeline to bulk-ingest the most 
critical and frequently queried Indian laws, bypassing live search latency for these topics.
"""

from templex.llm.research import ResearchPipeline

GOLDEN_DATASET_QUERIES = [
    {
        "intent": "Bharatiya Nyaya Sanhita 2023",
        "queries": [
            "Bharatiya Nyaya Sanhita 2023 ANDD BNS",
            "BNS chapter 2 punishment",
            "Bharatiya Nyaya Sanhita sexual offences",
        ]
    },
    {
        "intent": "Indian Penal Code 1860",
        "queries": [
            "Indian Penal Code 1860 ANDD IPC",
            "IPC section 302 murder",
            "IPC section 124A sedition",
        ]
    },
    {
        "intent": "Bharatiya Nagarik Suraksha Sanhita 2023",
        "queries": [
            "Bharatiya Nagarik Suraksha Sanhita 2023 ANDD BNSS",
            "BNSS arrest procedure",
            "BNSS bail provisions",
        ]
    },
    {
        "intent": "Constitution of India Article 21 Right to Life",
        "queries": [
            "Constitution of India Article 21",
            "Right to life and personal liberty",
            "Article 21 due process of law",
        ]
    },
    {
        "intent": "Constitution of India Article 14 Equality",
        "queries": [
            "Constitution of India Article 14",
            "Right to equality before law",
            "Article 14 reasonable classification",
        ]
    },
    {
        "intent": "Kesavananda Bharati v. State of Kerala",
        "queries": [
            "Kesavananda Bharati v. State of Kerala",
            "Basic structure doctrine Supreme Court",
            "Kesavananda Bharati judgment",
        ]
    },
    {
        "intent": "Justice K.S. Puttaswamy v. Union of India",
        "queries": [
            "Justice K.S. Puttaswamy v. Union of India",
            "Right to privacy Article 21",
            "Puttaswamy Aadhaar judgment",
        ]
    },
    {
        "intent": "Navtej Singh Johar v. Union of India",
        "queries": [
            "Navtej Singh Johar v. Union of India",
            "Section 377 decriminalization",
            "Navtej Johar LGBT rights",
        ]
    }
]

def main():
    print("="*60)
    print("Starting Golden Dataset Pre-Ingestion")
    print("="*60)
    
    for item in GOLDEN_DATASET_QUERIES:
        intent = item["intent"]
        queries = item["queries"]
        
        print(f"\n[Golden Dataset] Processing topic: {intent}")
        print("-" * 40)
        
        try:
            result = ResearchPipeline.execute_indian_law_research(
                original_prompt=intent,
                queries=queries,
                doctypes="judgments,laws",
                scope=None  # No session scope during baseline ingestion
            )
            print(result)
        except Exception as e:
            print(f"Failed to process {intent}: {e}")

if __name__ == "__main__":
    main()

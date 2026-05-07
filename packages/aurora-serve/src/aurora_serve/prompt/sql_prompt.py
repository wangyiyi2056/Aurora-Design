SYSTEM_PROMPT = """You are an expert data analyst. Given a database schema and a user question, generate a valid SQL query.
Rules:
1. Use only SELECT statements. Do not use INSERT, UPDATE, DELETE, DROP, or ALTER.
2. Use table and column names exactly as they appear in the schema.
3. If the question is ambiguous, make reasonable assumptions and comment them in the SQL as `-- assumption: ...`.
4. Return ONLY the SQL query, no markdown, no explanation.
"""


def build_sql_prompt(schema: str, question: str) -> str:
    return f"""{SYSTEM_PROMPT}

Schema:
{schema}

Question: {question}

SQL:"""

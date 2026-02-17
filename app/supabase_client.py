import requests

SUPABASE_URL = "https://kvmtfngxkeodkqrxbjwo.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imt2bXRmbmd4a2VvZGtxcnhiandvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzEyOTE3NDIsImV4cCI6MjA4Njg2Nzc0Mn0.T4c9OtAp7m7kTWznzGZNWHKyuwQMJp2sgqTco6MHtQw"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

def inserir_atleta(data: dict):
    url = f"{SUPABASE_URL}/rest/v1/perfis_atletas"
    response = requests.post(url, json=data, headers=HEADERS)
    return response.json()

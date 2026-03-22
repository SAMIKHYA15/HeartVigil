from supabase_client import supabase
from datetime import datetime

def save_health_data(data: dict, user_id: str):
    print(f"[DEBUG] Inserting for user_id: {user_id}")
    
def save_health_data(data: dict, user_id: str):
    """Save form data to Supabase (no validation for now)."""
    row = {
        "user_id": user_id,
        "created_at": datetime.utcnow().isoformat(),
        "source": "manual",
        **data
    }
    # Ensure optional fields are present (None is fine)
    optional = ["fbs","restecg","oldpeak","slope","ca","thal"]
    for f in optional:
        if f not in row:
            row[f] = None

    try:
        result = supabase.table("health_records").insert(row).execute()
        return True, result.data[0]
    except Exception as e:
        return False, str(e)
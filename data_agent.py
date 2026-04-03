from supabase_client import supabase
from datetime import datetime
from typing import Tuple, Dict, Any, Optional

class DataAgent:
    """Data Agent - Filing clerk and gatekeeper for health data"""

    VALIDATION_RULES = {
        "age": {"min": 1, "max": 100, "required": True, "type": int},
        "sex": {"allowed": [0, 1, "Male", "Female"], "required": True, "type": int},
        "cp": {"allowed": [0, 1, 2, 3], "required": True, "type": int},
        "trestbps": {"min": 80, "max": 200, "required": True, "type": int},
        "chol": {"min": 100, "max": 600, "required": True, "type": int},
        "fbs": {"allowed": [0, 1], "required": False, "type": int},
        "restecg": {"allowed": [0, 1, 2], "required": False, "type": int},
        "thalach": {"min": 60, "max": 220, "required": True, "type": int},
        "exang": {"allowed": [0, 1], "required": True, "type": int},
        "oldpeak": {"min": 0.0, "max": 6.2, "required": False, "type": float},
        "slope": {"allowed": [0, 1, 2], "required": False, "type": int},
        "ca": {"min": 0, "max": 3, "required": False, "type": int},
        "thal": {"allowed": [1, 2, 3], "required": False, "type": int}
    }

    REQUIRED_FIELDS = [
        "age", "sex", "cp", "trestbps", "chol", "thalach", "exang"
    ]

    @staticmethod
    def _convert_sex(value):
        if isinstance(value, str):
            lower = value.lower()
            if lower in ["male", "m"]:
                return 1
            elif lower in ["female", "f"]:
                return 0
        return value

    @staticmethod
    def validate_value(field: str, value: Any) -> Tuple[bool, Optional[str], Optional[Any]]:
        if field not in DataAgent.VALIDATION_RULES:
            return True, None, value

        rules = DataAgent.VALIDATION_RULES[field]

        if field == "sex":
            value = DataAgent._convert_sex(value)

        if rules.get("required", False):
            if value is None or value == "" or value == "N/A":
                return False, f"{field} is required and cannot be empty or N/A", None

        if value is None or value == "" or value == "N/A":
            if not rules.get("required", False):
                return True, None, None
            return False, f"{field} cannot be N/A", None

        try:
            expected_type = rules.get("type")
            if expected_type == int:
                value = int(float(value))
            elif expected_type == float:
                value = float(value)

            if "allowed" in rules:
                if value not in rules["allowed"]:
                    allowed_str = [str(x) for x in rules["allowed"]]
                    return False, f"{field} must be one of {', '.join(allowed_str)}", None

            if "min" in rules and value < rules["min"]:
                return False, f"{field} cannot be less than {rules['min']}", None
            if "max" in rules and value > rules["max"]:
                return False, f"{field} cannot be greater than {rules['max']}", None

        except (ValueError, TypeError):
            return False, f"{field} must be a valid number", None

        return True, None, value

    @staticmethod
    def validate_all(data: Dict[str, Any]) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        cleaned = {}
        for required_field in DataAgent.REQUIRED_FIELDS:
            if required_field not in data:
                return False, f"Missing required field: {required_field}", {}

        for field, value in data.items():
            if field in DataAgent.VALIDATION_RULES:
                is_valid, error, converted = DataAgent.validate_value(field, value)
                if not is_valid:
                    return False, error, {}
                cleaned[field] = converted
            else:
                cleaned[field] = value

        return True, None, cleaned

    @staticmethod
    def save_health_data(data: Dict[str, Any], user_id: str, source: str = "manual") -> Tuple[bool, Any]:
        is_valid, error_message, cleaned_data = DataAgent.validate_all(data)
        if not is_valid:
            return False, f"Validation error: {error_message}"

        row = {
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
            "source": source,
        }

        for field, value in cleaned_data.items():
            if field in DataAgent.VALIDATION_RULES:
                expected_type = DataAgent.VALIDATION_RULES[field].get("type")
                if expected_type == int and value is not None:
                    row[field] = int(float(value))
                elif expected_type == float and value is not None:
                    row[field] = float(value)
                else:
                    row[field] = value
            else:
                row[field] = value

        optional = ["fbs", "restecg", "oldpeak", "slope", "ca", "thal"]
        for f in optional:
            if f not in row:
                row[f] = None

        try:
            result = supabase.table("health_records").insert(row).execute()
            return True, result.data[0] if result.data else {"message": "Inserted successfully"}
        except Exception as e:
            return False, f"Database error: {str(e)}"

    @staticmethod
    def get_user_records(user_id: str, limit: int = 100) -> Tuple[bool, Any]:
        try:
            result = supabase.table("health_records")\
                .select("*")\
                .eq("user_id", user_id)\
                .order("created_at", desc=True)\
                .limit(limit)\
                .execute()
            return True, result.data
        except Exception as e:
            return False, f"Error fetching records: {str(e)}"

    @staticmethod
    def get_latest_record(user_id: str) -> Tuple[bool, Any]:
        try:
            result = supabase.table("health_records")\
                .select("*")\
                .eq("user_id", user_id)\
                .order("created_at", desc=True)\
                .limit(1)\
                .execute()
            if result.data:
                return True, result.data[0]
            return True, None
        except Exception as e:
            return False, f"Error fetching latest record: {str(e)}"

    # ========== PHASE 2 ADDITION ==========
    @staticmethod
    def compute_delta(current_values: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        Fetch previous submission and compute changes between current and previous.
        Returns delta object with per-field changes.
        """
        # Fetch previous submission (second latest, since current is being saved)
        try:
            response = supabase.table("health_records")\
                .select("*")\
                .eq("user_id", user_id)\
                .order("created_at", desc=True)\
                .limit(2)\
                .execute()
            
            records = response.data
            if len(records) < 2:
                return {"has_previous": False}
            
            previous = records[1]  # Second most recent
        except Exception as e:
            print(f"Error fetching previous record: {e}")
            return {"has_previous": False}
        
        delta = {"has_previous": True}
        
        # Fields to track
        tracked_fields = [
            "age", "sex", "cp", "trestbps", "chol", "fbs",
            "restecg", "thalach", "exang", "oldpeak", "slope", "ca", "thal"
        ]
        
        # Helper to determine direction for each field
        def get_direction(field, prev_val, curr_val):
            if prev_val is None or curr_val is None:
                return None
            
            # For these fields, higher is better
            higher_is_better = ["thalach"]
            # For these fields, lower is better
            lower_is_better = ["trestbps", "chol", "oldpeak", "ca"]
            
            if field in higher_is_better:
                if curr_val > prev_val:
                    return "improved"
                elif curr_val < prev_val:
                    return "worsened"
                else:
                    return "stable"
            elif field in lower_is_better:
                if curr_val < prev_val:
                    return "improved"
                elif curr_val > prev_val:
                    return "worsened"
                else:
                    return "stable"
            else:
                # For categorical fields, just track change without direction
                if curr_val != prev_val:
                    return "changed"
                else:
                    return "stable"
        
        # Build delta for each field
        for field in tracked_fields:
            prev_val = previous.get(field)
            curr_val = current_values.get(field)
            
            if prev_val is not None and curr_val is not None:
                change = curr_val - prev_val if isinstance(prev_val, (int, float)) else None
                direction = get_direction(field, prev_val, curr_val)
                
                delta[field] = {
                    "prev": prev_val,
                    "curr": curr_val,
                    "change": change,
                    "direction": direction
                }
        
        return delta


# Backward compatibility wrapper
def save_health_data(data: dict, user_id: str, source: str = "manual"):
    return DataAgent.save_health_data(data, user_id, source)


# Phase 2 wrapper
def compute_delta(current_values: dict, user_id: str):
    return DataAgent.compute_delta(current_values, user_id)
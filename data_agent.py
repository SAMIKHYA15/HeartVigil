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
        """Convert "Male"/"Female" to 1/0 for storage."""
        if isinstance(value, str):
            lower = value.lower()
            if lower == "male":
                return 1
            elif lower == "female":
                return 0
        return value

    @staticmethod
    def validate_value(field: str, value: Any) -> Tuple[bool, Optional[str], Optional[Any]]:
        """
        Validate a single field against its rules.
        Returns (is_valid, error_message, converted_value)
        """
        if field not in DataAgent.VALIDATION_RULES:
            return True, None, value

        rules = DataAgent.VALIDATION_RULES[field]

        # Special handling for sex: convert string to int if needed
        if field == "sex":
            value = DataAgent._convert_sex(value)

        # Required field check
        if rules.get("required", False):
            if value is None or value == "" or value == "N/A":
                return False, f"{field} is required and cannot be empty or N/A", None

        # If value is None and optional, skip further checks
        if value is None or value == "" or value == "N/A":
            if not rules.get("required", False):
                return True, None, None
            return False, f"{field} cannot be N/A", None

        # Type conversion and validation
        try:
            expected_type = rules.get("type")
            if expected_type == int:
                value = int(float(value))
            elif expected_type == float:
                value = float(value)

            if "allowed" in rules:
                if value not in rules["allowed"]:
                    # Provide a user-friendly allowed list
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
        """
        Validate all fields in the data dictionary.
        Returns (is_valid, error_message, cleaned_data)
        """
        cleaned = {}
        # Check required fields exist
        for required_field in DataAgent.REQUIRED_FIELDS:
            if required_field not in data:
                return False, f"Missing required field: {required_field}", {}

        # Validate each field
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
        """
        Validate and save health data to Supabase.

        Returns:
            (success, result_or_error_message)
        """
        # Validation and cleaning
        is_valid, error_message, cleaned_data = DataAgent.validate_all(data)
        if not is_valid:
            return False, f"Validation error: {error_message}"

        # Prepare row
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

        # Ensure optional fields are present (None is fine)
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
        """Retrieve health records for a specific user."""
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
        """Get the most recent health record for a user."""
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


# Backward compatibility wrapper for app.py
def save_health_data(data: dict, user_id: str, source: str = "manual"):
    return DataAgent.save_health_data(data, user_id, source)
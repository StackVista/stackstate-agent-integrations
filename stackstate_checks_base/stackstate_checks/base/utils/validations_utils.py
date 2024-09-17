
from pydantic import field_validator, BaseModel, ValidationInfo, ConfigDict
from typing import Any
from pydantic_core import PydanticUndefined


class CheckBaseModel(BaseModel):
    # CheckBaseModel extends the BaseModel of pydantic with some default behaviors and backwards compatibility
    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="before")
    @classmethod
    def use_default_value(cls, value: Any, info: ValidationInfo) -> Any:

        # NOTE: All fields that are optional for values, will assume the value in
        # "default" (if defined in "Field") if "None" is informed as "value". That
        # is, "None" is never assumed if passed as a "value".
        if (
                cls.model_fields[info.field_name].get_default() is not PydanticUndefined
                and not cls.model_fields[info.field_name].is_required()
                and value is None
        ):
            return cls.model_fields[info.field_name].get_default()
        else:
            return value

    def get(self, field: str, default: Any = None) -> Any:
        if hasattr(self, field):
            return getattr(self, field)
        else:
            return default

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

import numpy as np
from pydantic import BaseModel, ConfigDict


class StrictParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BaseEffect(ABC):
    effect_id: ClassVar[str]
    display_name: ClassVar[str]
    description: ClassVar[str]
    category: ClassVar[str]
    implementation_version: ClassVar[int] = 1
    uses_seed: ClassVar[bool] = False
    params_model: ClassVar[type[StrictParams]]

    def default_params(self) -> dict[str, Any]:
        return self.params_model().model_dump()

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        return self.params_model.model_validate(params).model_dump()

    def params_schema(self) -> dict[str, Any]:
        return self.params_model.model_json_schema()

    @abstractmethod
    def apply(
        self,
        image: np.ndarray,
        params: dict[str, Any],
        seed: int | None = None,
    ) -> np.ndarray:
        raise NotImplementedError

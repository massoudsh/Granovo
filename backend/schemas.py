from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Finite = Annotated[float, Field(allow_inf_nan=False)]
Polymer = Literal["PE", "PP", "PET", "PS", "PVC", "ABS"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(Input):
    email: Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, min_length=3, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")]
    password: Annotated[str, StringConstraints(min_length=12, max_length=128)]


class Registration(Login):
    factory_name: Text


class Machine(Input):
    name: Text
    temperature_min: Annotated[Finite, Field(ge=0, le=500)]
    temperature_max: Annotated[Finite, Field(gt=0, le=500)]
    rpm_max: Annotated[Finite, Field(gt=0, le=3000)]
    pressure_max: Annotated[Finite, Field(gt=0, le=2000)]

    @model_validator(mode="after")
    def ordered_limits(self):
        if self.temperature_min >= self.temperature_max:
            raise ValueError("Minimum temperature must be below maximum")
        return self


class Material(Input):
    machine_id: Annotated[str, StringConstraints(min_length=1, max_length=36)]
    polymer: Polymer
    purity_pct: Annotated[Finite, Field(ge=0, le=100)]
    moisture_pct: Annotated[Finite, Field(ge=0, le=100)]


class Batch(Material):
    code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    produced_on: date
    phase: Literal["baseline", "pilot"]
    temperature_c: Annotated[Finite, Field(ge=0, le=500)]
    screw_rpm: Annotated[Finite, Field(gt=0, le=3000)]
    pressure_bar: Annotated[Finite, Field(gt=0, le=2000)]
    total_kg: Annotated[Finite, Field(gt=0, le=10000000)]
    rejected_kg: Annotated[Finite, Field(ge=0, le=10000000)]

    @model_validator(mode="after")
    def valid_result(self):
        if self.rejected_kg > self.total_kg:
            raise ValueError("Rejected mass cannot exceed total mass")
        if self.produced_on > date.today():
            raise ValueError("Production date cannot be in the future")
        return self


class Verification(Input):
    quality_verified: bool

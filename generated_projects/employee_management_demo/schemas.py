from pydantic import BaseModel, Field
from typing import Optional
from decimal import Decimal

class EmployeeBase(BaseModel):
    name: str = Field(..., min_length=1, description="Full name of the employee")
    salary: Decimal = Field(..., gt=0, decimal_places=2, description="Employee's salary")

class EmployeeCreate(EmployeeBase):
    """Schema for creating a new employee."""
    pass

class EmployeeUpdate(BaseModel):
    """Schema for updating an existing employee."""
    name: Optional[str] = Field(None, min_length=1, description="Full name of the employee")
    salary: Optional[Decimal] = Field(None, gt=0, decimal_places=2, description="Employee's salary")

class Employee(EmployeeBase):
    """Schema for reading an employee, including the ID."""
    id: int = Field(..., gt=0, description="Unique identifier of the employee")

    class Config:
        orm_mode = True # To allow Pydantic to read ORM models (e.g., SQLAlchemy)
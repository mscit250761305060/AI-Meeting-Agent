from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, EmailStr
from typing import List, Dict, Set, Optional

app = FastAPI(
    title="Employee Management System API",
    description="A simple API for managing employee data with in-memory storage."
)

# In-memory storage for employees
# Each employee is a dictionary matching the EmployeeBase schema
employees: List[Dict[str, str]] = []

# Pydantic models for request and response bodies
class EmployeeBase(BaseModel):
    """Base model for an employee."""
    name: str
    email: EmailStr
    department: str

class EmployeeCreate(EmployeeBase):
    """Model for creating a new employee."""
    pass # Inherits all fields from EmployeeBase

class EmployeeUpdate(BaseModel):
    """Model for updating an existing employee. All fields are optional."""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    department: Optional[str] = None

class DashboardStats(BaseModel):
    """Model for dashboard statistics."""
    total_employees: int
    departments: int # Count of unique departments
    active_users: int # In this context, total employees are considered 'active' and 'unique' individuals

# Helper function to validate employee_id and retrieve employee
def _get_employee_or_404(employee_id: int) -> Dict[str, str]:
    """
    Checks if an employee_id is valid and returns the employee dictionary.
    Raises HTTPException if not found.
    """
    if not (0 <= employee_id < len(employees)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with ID {employee_id} not found."
        )
    return employees[employee_id]

# 1. GET /employees
@app.get("/employees", response_model=List[EmployeeBase])
async def get_all_employees():
    """
    Retrieves a list of all employees in the system.
    """
    return employees

# 2. POST /employees
@app.post("/employees", response_model=EmployeeBase, status_code=status.HTTP_201_CREATED)
async def create_employee(employee: EmployeeCreate):
    """
    Adds a new employee to the system.
    The new employee is appended to the in-memory list.
    """
    employees.append(employee.model_dump()) # Use model_dump for Pydantic V2+
    return employee

# 3. PUT /employees/{employee_id}
@app.put("/employees/{employee_id}", response_model=EmployeeBase)
async def update_employee(employee_id: int, employee_update: EmployeeUpdate):
    """
    Updates an existing employee's details by their integer index (employee_id).
    Only provided fields will be updated.
    """
    existing_employee = _get_employee_or_404(employee_id)

    # Update only the fields that were provided in the request body
    update_data = employee_update.model_dump(exclude_unset=True) # Exclude fields not set in the request
    existing_employee.update(update_data)

    return existing_employee

# 4. DELETE /employees/{employee_id}
@app.delete("/employees/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_employee(employee_id: int):
    """
    Deletes an employee from the system by their integer index (employee_id).
    """
    _get_employee_or_404(employee_id) # Ensure employee exists
    employees.pop(employee_id)
    # FastAPI automatically handles 204 No Content for routes that don't return content
    # or if an HTTPException is raised.

# 5. GET /dashboard-stats
@app.get("/dashboard-stats", response_model=DashboardStats)
async def get_dashboard_stats():
    """
    Returns various statistics for the employee management system dashboard.
    Includes total employees, count of unique departments, and active users.
    """
    total_employees = len(employees)

    # Count unique departments
    unique_departments: Set[str] = set()
    for emp in employees:
        unique_departments.add(emp["department"])
    
    num_unique_departments = len(unique_departments)

    # In this simplified system, all employees are considered 'active' and 'unique individuals'.
    active_users = total_employees

    return DashboardStats(
        total_employees=total_employees,
        departments=num_unique_departments,
        active_users=active_users
    )

# Mount static files (must be kept last)
app.mount("/", StaticFiles(directory=".", html=True), name="static")

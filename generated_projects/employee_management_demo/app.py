
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()



employees = []

@app.get("/")
def home():
    return FileResponse("index.html")


@app.get("/employees")
def get_employees():
    return employees


@app.post("/employees")
def add_employee(employee: dict):

    employees.append(employee)

    return {
        "message": "Employee Added",
        "employee": employee
    }


@app.put("/employees/{employee_id}")
def update_employee(employee_id: int, employee: dict):

    if employee_id < len(employees):
        employees[employee_id] = employee

    return {
        "message": "Employee Updated"
    }


@app.delete("/employees/{employee_id}")
def delete_employee(employee_id: int):

    if employee_id < len(employees):
        employees.pop(employee_id)

    return {
        "message": "Employee Deleted"
    }

app.mount("/", StaticFiles(directory=".", html=True), name="static")
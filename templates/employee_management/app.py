from fastapi import FastAPI

app = FastAPI()

employees = []

@app.get("/")
def home():
    return {
        "message": "Employee Management Demo"
    }

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
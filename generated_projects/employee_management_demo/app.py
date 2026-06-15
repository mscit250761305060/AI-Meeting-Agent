from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

items = []

@app.get("/")
def home():
    return {
        "project": "Employee Management System"
    }

@app.get("/items")
def get_items():
    return items

@app.post("/items")
def create_item(item: dict):
    items.append(item)
    return {
        "message": "Created",
        "item": item
    }

@app.put("/items/{item_id}")
def update_item(item_id: int, item: dict):

    if item_id < len(items):
        items[item_id] = item

    return {
        "message": "Updated"
    }

@app.delete("/items/{item_id}")
def delete_item(item_id: int):

    if item_id < len(items):
        items.pop(item_id)

    return {
        "message": "Deleted"
    }

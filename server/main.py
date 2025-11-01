from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
import database
from database import User
from schema import Item, UpdateItem

app = FastAPI()
session = database.get_session()

origins = [
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods
    allow_headers=["*"], # Allows all headers
)

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/api/users")
def get_all_users():
    statement = select(User)
    users = session.scalars(statement).all()
    return users

@app.post("/api/user/create")
def create_data(items: Item):
    new_user = User(first_name=items.first_name, last_name=items.last_name, age=items.age)
    session.add(new_user)
    session.commit()
    return {"message": "User created successfully!"}


@app.get("/api/user/{user_id}")
def get_user(user_id: int):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.put("/api/user/{user_id}")
def update_user(user_id: int, item: UpdateItem):
    user = session.get(User, user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.first_name = item.first_name if item.first_name else user.first_name
    user.last_name = item.last_name if item.last_name else user.last_name
    user.age = item.age if item.age else user.age

    session.add(user)
    session.commit()
    session.refresh(user)

    return user

@app.delete("/api/user/{user_id}")
def delete_user(user_id: int):
    user = session.get(User, user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    session.delete(user)
    session.commit()

    return {"message": "User deleted successfully"}
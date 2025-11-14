from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import uuid4
import os
import asyncpg
import asyncio

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/reviews")

app = FastAPI(title="reviews-svc")

async def get_pool():
    if not hasattr(app.state, "pool"):
        app.state.pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    return app.state.pool

@app.on_event("startup")
async def startup(): await get_pool()

class UserCreate(BaseModel):
    name: str = Field(min_length=1)

class User(BaseModel):
    id: str
    name: str

class ReviewCreate(BaseModel):
    userId: str
    bookId: str  # OLID
    rating: int = Field(ge=1, le=5)
    text: str = Field(min_length=1)

class Review(BaseModel):
    id: str
    userId: str
    bookId: str
    rating: int
    text: str

@app.post("/api/reviews/users", response_model=User, status_code=201)
async def create_user(body: UserCreate):
    uid = str(uuid4())
    pool = await get_pool()
    async with pool.acquire() as con:
        await con.execute("INSERT INTO users(id,name) VALUES($1,$2)", uid, body.name)
    return User(id=uid, name=body.name)

@app.post("/api/reviews/reviews", response_model=Review, status_code=201)
async def create_review(body: ReviewCreate):
    rid = str(uuid4())
    pool = await get_pool()
    async with pool.acquire() as con:
        u = await con.fetchval("SELECT 1 FROM users WHERE id=$1", body.userId)
        if not u:
            raise HTTPException(status_code=404, detail="User not found")
        await con.execute(
            "INSERT INTO reviews(id,user_id,book_olid,rating,txt) VALUES($1,$2,$3,$4,$5)",
            rid, body.userId, body.bookId, body.rating, body.text
        )
    return Review(id=rid, userId=body.userId, bookId=body.bookId, rating=body.rating, text=body.text)

@app.get("/api/reviews/reviews", response_model=List[Review])
async def list_reviews(bookId: str = Query(...), limit: int = 10, offset: int = 0):
    pool = await get_pool()
    async with pool.acquire() as con:
        rows = await con.fetch(
           "SELECT id,user_id,book_olid,rating,txt FROM reviews WHERE book_olid=$1 ORDER BY id LIMIT $2 OFFSET $3"
            ,bookId, limit, offset
            #
        )
    return [Review(id=r["id"], userId=r["user_id"], bookId=r["book_olid"], rating=r["rating"], text=r["txt"]) for r in rows]

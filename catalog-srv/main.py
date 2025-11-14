#@app.get("/api/catalog/books/{olid}")
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
import httpx

app = FastAPI(title="Catalog Service", version="1.0.0")
class SearchItem(BaseModel): 
    id: str  # OLID
    title: Optional[str]
    authors: List[str] = []
    first_publish_year: Optional[int]

class SearchResponse(BaseModel):
    query: str
    page: int
    limit: int
    total_found: int
    items: List[SearchItem]

class BookDetail(BaseModel):
    id: str
    title: Optional[str]
    description: Optional[str]
    authors: List[str] = []
    subjects: List[str] = []
    publish_date: Optional[str]

# SEARCH ENDPOINT
@app.get("/api/catalog/search", response_model=SearchResponse)
async def search_books(
    q: str = Query(..., min_length=1, description="Search term"),
    limit: int = Query(10, ge=1, le=50, description="Max items to return"),
    page: int = Query(1, ge=1, description="Pagination")
):
    url = "https://openlibrary.org/search.json"
    headers = {"User-Agent": "book-explorer/1.0 (cloud assignment)"}
    params = {"q": q, "page": page}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params, headers=headers)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Open Library unavailable: {str(e)}")

    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="Upstream API error")

    data = resp.json()
    docs = data.get("docs", [])
    total = data.get("numFound", 0)

    items = []
    for d in docs[:limit]:
        # --- FIX FOR UnboundLocalError & empty list ---
        
        # 1. Try the most reliable single edition key
        olid = d.get("cover_edition_key") 
        
        # 2. If not found, try the first from the list of all edition keys
        if not olid:
            edition_keys = d.get("edition_key")
            if edition_keys and len(edition_keys) > 0:
                olid = edition_keys[0]
        if not olid:     
            work_key = d.get("key", "").split('/')[-1]
            if work_key:
                olid = work_key
        # 3. If still no ID found, skip this item
        if not olid:
            continue

        items.append(SearchItem(
            id=olid, # Use the now-guaranteed 'olid' variable
            title=d.get("title"),
            authors=d.get("author_name") or [],
            first_publish_year=d.get("first_publish_year")
        ))
    

    return SearchResponse(
        query=q,
        page=page,
        limit=limit,
        total_found=total,
        items=items
    )
# BOOK DETAILS ENDPOINT


@app.get("/api/catalog/books/{olid}", response_model=BookDetail)
async def get_book_details(olid: str):
    url = f"https://openlibrary.org/books/{olid}.json"
    headers = {"User-Agent": "book-explorer/1.0 (cloud assignment)"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Open Library unavailable: {str(e)}")

    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="Book not found")

    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="Open Library error")

    data = resp.json()

    # optional fields: all books doesnt have description
    desc = data.get("description")
    if isinstance(desc, dict):
        desc = desc.get("value", None)

    authors = []
    for a in data.get("authors", []):
        key = a.get("key")
        if key:
            authors.append(key.replace("/authors/", ""))

    return BookDetail(
        id=olid,
        title=data.get("title"),
        description=desc,
        authors=authors,
        subjects=data.get("subjects") or [],
        publish_date=data.get("publish_date")
    )

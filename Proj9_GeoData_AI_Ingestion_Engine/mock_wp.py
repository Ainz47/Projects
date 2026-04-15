from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import json

app = FastAPI(title="Mock WordPress REST API")
security = HTTPBasic()

# Fake database to keep track of things in memory
db = {
    "media_counter": 100,
    "posts_counter": 500,
    "listings": {} # Maps place_ids to post_ids
}

# --- Authentication (Simulating WP Application Passwords) ---
def verify_auth(credentials: HTTPBasicCredentials = Depends(security)):
    if credentials.username != "mock_admin" or credentials.password != "mock_password":
        raise HTTPException(status_code=401, detail="Unauthorized")
    return credentials.username

# --- Mock WP Media Library ---
@app.post("/wp/v2/media", status_code=201)
async def upload_media(request: Request, username: str = Depends(verify_auth)):
    db["media_counter"] += 1
    print(f"📸 Mock WP received an image upload! Assigned ID: {db['media_counter']}")
    return {"id": db["media_counter"], "source_url": "http://mock-wp.local/image.jpg"}

# --- Mock WP Custom Post Type (Directory Listings) ---
@app.get("/wp/v2/directory_listing")
async def check_existing_post(meta_key: str = None, meta_value: str = None, username: str = Depends(verify_auth)):
    # Simulating the idempotency check
    if meta_key == "place_id" and meta_value in db["listings"]:
        print(f"🔍 Checking Place ID: Found existing post {db['listings'][meta_value]}")
        return [{"id": db["listings"][meta_value]}]
    
    print(f"🔍 Checking Place ID: Nothing found. Safe to create new.")
    return []

@app.post("/wp/v2/directory_listing", status_code=201)
async def create_new_post(request: Request, username: str = Depends(verify_auth)):
    data = await request.json()
    db["posts_counter"] += 1
    new_post_id = db["posts_counter"]
    
    print("\n" + "="*50)
    print(f"🤝 Mock WP received CREATE request. Assigning new ID: {new_post_id}")
    print("="*50)
    print(json.dumps(data, indent=4)) # This is the flex!
    print("="*50 + "\n")
    
    # THE FIX: Record the place_id -> post_id mapping for idempotency checks.
    place_id = data.get("meta", {}).get("place_id")
    if place_id:
        db["listings"][place_id] = new_post_id
        print(f"✍️  Mock DB recorded mapping: {place_id} -> {new_post_id}")

    return {"id": new_post_id, "status": "publish"}

@app.post("/wp/v2/directory_listing/{post_id}", status_code=200)
async def update_existing_post(post_id: int, request: Request, username: str = Depends(verify_auth)):
    data = await request.json()
    print("\n" + "="*50)
    print(f"🔄 Mock WP received UPDATE request for existing ID: {post_id}")
    print("="*50)
    print(json.dumps(data, indent=4))
    print("="*50 + "\n")
    return {"id": post_id, "status": "publish"}
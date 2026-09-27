"""In-memory stand-in for the WordPress endpoints the pipeline uses. Run: py -m uvicorn mock_wp:app"""
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials

USERNAME, PASSWORD = "mock_admin", "mock_password"


def create_app() -> FastAPI:
    app = FastAPI(title="Mock WordPress REST API")
    security = HTTPBasic()
    state = {"next_media": 100, "next_post": 500, "posts": {}, "media": {}}
    app.state.wp = state

    def auth(creds: HTTPBasicCredentials = Depends(security)):
        if (creds.username, creds.password) != (USERNAME, PASSWORD):
            raise HTTPException(401, "Unauthorized")

    @app.post("/wp/v2/media", status_code=201, dependencies=[Depends(auth)])
    async def upload_media(request: Request):
        body = await request.body()
        if not body:
            raise HTTPException(400, "Empty upload")
        state["next_media"] += 1
        state["media"][state["next_media"]] = len(body)
        return {"id": state["next_media"]}

    @app.get("/wp/v2/directory_listing", dependencies=[Depends(auth)])
    async def list_listings(place_id: str | None = None):
        posts = [p for p in state["posts"].values() if not place_id or p["meta"].get("place_id") == place_id]
        return [{"id": p["id"], "featured_media": p.get("featured_media", 0)} for p in posts]

    @app.post("/wp/v2/directory_listing", status_code=201, dependencies=[Depends(auth)])
    async def create_listing(request: Request):
        data = await request.json()
        state["next_post"] += 1
        post = {"featured_media": 0, **data, "id": state["next_post"]}
        state["posts"][post["id"]] = post
        return post

    @app.post("/wp/v2/directory_listing/{post_id}", dependencies=[Depends(auth)])
    async def update_listing(post_id: int, request: Request):
        if post_id not in state["posts"]:
            raise HTTPException(404, "No such post")
        data = await request.json()
        post = state["posts"][post_id]
        meta = {**post.get("meta", {}), **data.pop("meta", {})}
        post.update(data)
        post["meta"] = meta
        return post

    return app


app = create_app()

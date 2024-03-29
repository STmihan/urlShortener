import validators
import requests
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from starlette.datastructures import URL

from . import crud, models, schemas
from .database import SessionLocal, engine
from .config import get_settings

app = FastAPI()
models.Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_admin_info(db_url: models.URL) -> schemas.URLInfo:
    base_url = URL(get_settings().base_url)
    admin_endpoint = app.url_path_for(
        "administration info", secret_key=db_url.secret_key
    )
    db_url.url = str(base_url.replace(path=db_url.key))
    db_url.admin_url = str(base_url.replace(path=admin_endpoint))
    return db_url


def check_website_exists(target_url: str):
    try:
        response = requests.get(target_url)
        try:
            response.raise_for_status()
            return True
        except requests.exceptions.HTTPError:
            return False
    except requests.exceptions.ConnectionError:
        return False


def raise_not_found(request):
    message = f"URL '{request.url}' doesn't exist"
    raise HTTPException(status_code=404, detail=message)


def raise_bad_request(message):
    raise HTTPException(status_code=400, detail=message)


@app.get("/")
def read_root():
    return "Welcome to the URL shortener API."


@app.post("/url", response_model=schemas.URLInfo)
def create_url(url: schemas.URLBase, db: Session = Depends(get_db)):
    if not validators.url(url.target_url):
        raise_bad_request(message="Your provided URL is not valid.")
    db_url = crud.create_db_url(db=db, url=url)
    return get_admin_info(db_url)


@app.post("/url/{custom_key}", response_model=schemas.URLInfo)
def create_url_custom_key(custom_key: str, url: schemas.URLBase, db: Session = Depends(get_db)):
    if not validators.url(url.target_url):
        raise_bad_request(message="Your provided URL is not valid.")
    if crud.get_db_url_by_key(db=db, url_key=custom_key):
        raise_bad_request(message="Your provided custom key has already been taken.")
    db_url = crud.create_db_url(db=db, url=url, custom_key=custom_key)
    return get_admin_info(db_url)


@app.get("/{url_key}")
def forward_to_target_url(
        url_key: str,
        request: Request,
        db: Session = Depends(get_db)
):
    db_url = crud.get_db_url_by_key(db=db, url_key=url_key)
    if db_url:
        crud.update_db_clicks(db=db, db_url=db_url)
        if check_website_exists(db_url.target_url):
            return RedirectResponse(db_url.target_url)
        else:
            raise_bad_request(message="Target URL does not exist.")
    else:
        raise_not_found(request)


@app.get(
    "/admin/{secret_key}",
    name="administration info",
    response_model=schemas.URLInfo
)
def get_url_info(secret_key: str, request: Request, db: Session = Depends(get_db)):
    db_url = crud.get_db_url_by_secret_key(db=db, secret_key=secret_key)
    if db_url:
        return get_admin_info(db_url)
    else:
        raise_not_found(request=request)


@app.delete("/admin/{secret_key}")
def delete_url(secret_key: str, request: Request, db: Session = Depends(get_db)):
    db_url = crud.deactivate_db_url_by_secret_key(db=db, secret_key=secret_key)
    if db_url:
        message = f"Successfully deleted shortened URL for '{db_url.target_url}'."
        return {"detail": message}
    else:
        raise_not_found(request=request)


@app.get("/peek/{url_key}", response_model=schemas.URLBase)
def peek_target_url(url_key: str, request: Request, db: Session = Depends(get_db)):
    db_url = crud.get_db_url_by_key(db=db, url_key=url_key)
    if db_url:
        return db_url
    else:
        raise_not_found(request=request)




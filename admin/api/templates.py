"""
API endpoints для шаблонов
"""
from fastapi import APIRouter

router = APIRouter()

# Заглушка - будет реализовано в следующих задачах
@router.get("/")
async def get_templates():
    return {"message": "Templates API - в разработке"}

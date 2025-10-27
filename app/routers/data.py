from fastapi import APIRouter

router = APIRouter()

@router.get("/data")
async def get_data():
    # TODO: Implementar
    return {"message": "Data endpoint"}
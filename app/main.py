from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.supabase_client import inserir_atleta


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PerfilAtletaCreate(BaseModel):
    nome: str
    idade: int
    sexo: str
    nivel: str
    esporte_id: str
    modalidade_id: str


@app.get("/")
def root():
    return {"status": "online"}


@app.post("/atletas")
def criar_atleta(perfil: PerfilAtletaCreate):

    data = perfil.dict()
    resultado = inserir_atleta(data)

    return {
        "status": "atleta_criado",
        "dados": resultado
    }

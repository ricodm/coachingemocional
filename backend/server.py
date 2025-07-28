from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime
from openai import OpenAI

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# OpenAI setup
try:
    openai_client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
except Exception as e:
    print(f"Warning: OpenAI client initialization failed: {e}")
    openai_client = None

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Define Models
class Message(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    content: str
    is_user: bool
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ChatRequest(BaseModel):
    session_id: str
    message: str

class ChatResponse(BaseModel):
    session_id: str
    response: str
    message_id: str

class Session(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = "anonymous"  # Por enquanto todos são anônimos
    created_at: datetime = Field(default_factory=datetime.utcnow)
    summary: Optional[str] = None
    messages_count: int = 0

# Ramana Maharshi inspired therapeutic prompts
RAMANA_SYSTEM_PROMPT = """
Você é um terapeuta emocional compassivo que segue os ensinamentos de Ramana Maharshi. Seu objetivo é ajudar as pessoas emocionalmente através de uma abordagem gentil e investigativa.

DIRETRIZES FUNDAMENTAIS:
1. Sempre responda em português do Brasil
2. Seja caloroso, empático e acolhedor
3. Faça perguntas investigativas para identificar a fonte dos problemas emocionais
4. Gradualmente, guie a pessoa à investigação "Quem sou eu?" de Ramana Maharshi
5. Ajude a pessoa a perceber a diferença entre seus pensamentos/emoções e sua verdadeira natureza
6. Use linguagem simples e acessível
7. Sempre termine com uma pergunta reflexiva ou sugestão prática

ESTILO DE CONVERSA:
- Comece sempre acolhendo o que a pessoa trouxe
- Faça perguntas abertas e investigativas
- Introduza gradualmente conceitos de auto-investigação
- Seja gentil ao questionar crenças limitantes
- Ofereça perspectivas que levem à investigação do "eu"

EXEMPLO DE RESPOSTA:
"Entendo que você está passando por um momento difícil. É natural sentir-se assim. Vamos investigar juntos: quando você diz 'eu estou triste', quem é esse 'eu' que observa a tristeza? Você consegue perceber que existe uma parte sua que está ciente da tristeza, mas não É a própria tristeza?"
"""

async def get_session_history(session_id: str) -> List[Message]:
    """Recupera histórico de mensagens de uma sessão"""
    messages = await db.messages.find({"session_id": session_id}).sort("timestamp", 1).to_list(100)
    return [Message(**msg) for msg in messages]

async def create_openai_response(session_id: str, user_message: str) -> str:
    """Cria resposta usando OpenAI com contexto da sessão"""
    try:
        # Check if OpenAI client is available
        if openai_client is None:
            return "Desculpe, o serviço de IA está temporariamente indisponível. Mas posso te ouvir: que tal me contar mais sobre como você está se sentindo?"
        
        # Recupera histórico da sessão
        history = await get_session_history(session_id)
        
        # Constrói contexto das mensagens anteriores
        messages = [{"role": "system", "content": RAMANA_SYSTEM_PROMPT}]
        
        # Adiciona histórico
        for msg in history[-10:]:  # Últimas 10 mensagens para contexto
            role = "user" if msg.is_user else "assistant"
            messages.append({"role": role, "content": msg.content})
        
        # Adiciona mensagem atual
        messages.append({"role": "user", "content": user_message})
        
        # Chama OpenAI
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            max_tokens=500,
            temperature=0.7
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        logger.error(f"Erro ao chamar OpenAI: {str(e)}")
        return "Desculpe, estou tendo dificuldades técnicas. Pode tentar novamente em alguns momentos? Enquanto isso, que tal respirar fundo e observar seus pensamentos com gentileza?"

@api_router.post("/chat", response_model=ChatResponse)
async def chat_with_therapist(request: ChatRequest):
    """Endpoint principal para chat terapêutico"""
    try:
        # Salva mensagem do usuário
        user_message = Message(
            session_id=request.session_id,
            content=request.message,
            is_user=True
        )
        await db.messages.insert_one(user_message.dict())
        
        # Gera resposta terapêutica
        ai_response = await create_openai_response(request.session_id, request.message)
        
        # Salva resposta da IA
        ai_message = Message(
            session_id=request.session_id,
            content=ai_response,
            is_user=False
        )
        await db.messages.insert_one(ai_message.dict())
        
        # Atualiza contador de mensagens da sessão
        await db.sessions.update_one(
            {"id": request.session_id},
            {"$inc": {"messages_count": 2}},
            upsert=True
        )
        
        return ChatResponse(
            session_id=request.session_id,
            response=ai_response,
            message_id=ai_message.id
        )
        
    except Exception as e:
        logger.error(f"Erro no chat: {str(e)}")
        raise HTTPException(status_code=500, detail="Erro interno do servidor")

@api_router.post("/session", response_model=Session)
async def create_session():
    """Cria nova sessão de terapia"""
    session = Session()
    await db.sessions.insert_one(session.dict())
    return session

@api_router.get("/session/{session_id}/history", response_model=List[Message])
async def get_session_messages(session_id: str):
    """Recupera histórico de mensagens de uma sessão"""
    messages = await get_session_history(session_id)
    return messages

@api_router.get("/session/{session_id}", response_model=Session)
async def get_session(session_id: str):
    """Recupera informações de uma sessão"""
    session_data = await db.sessions.find_one({"id": session_id})
    if not session_data:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    return Session(**session_data)

# Health check
@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "terapia_emocional"}

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
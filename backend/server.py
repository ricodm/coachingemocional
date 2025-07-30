from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timedelta
import bcrypt
import jwt
from openai import OpenAI
from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionResponse, CheckoutStatusResponse, CheckoutSessionRequest

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
openai_client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
logger.info("OpenAI API key configured")

# JWT settings
JWT_SECRET = os.environ.get('JWT_SECRET', 'your-secret-key-change-in-production')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24 * 7  # 7 days

# Stripe setup
stripe_api_key = os.environ.get('STRIPE_SECRET_KEY')
stripe_checkout = None

# Security
security = HTTPBearer()

# Create the main app without a prefix
app = FastAPI(title="Terapia Emocional API", version="1.0.0")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# SUBSCRIPTION PLANS
SUBSCRIPTION_PLANS = {
    "basico": {
        "name": "Básico",
        "price": 9.90,
        "messages_per_day": 7,
        "stripe_product_id": "prod_Sm9XiTHR0wr7fY"
    },
    "premium": {
        "name": "Premium", 
        "price": 29.90,
        "messages_per_day": 30,
        "stripe_product_id": "prod_Sm9XBfQdpJZ6r2"
    },
    "ilimitado": {
        "name": "Ilimitado",
        "price": 69.00,
        "messages_per_day": -1,  # -1 = unlimited
        "stripe_product_id": "prod_Sm9YN393efcIDr"
    }
}

# SUPPORT DOCUMENT FOR GPT
SUPPORT_DOCUMENT = """
DOCUMENTO DE SUPORTE - TERAPIA EMOCIONAL

**PERGUNTAS FREQUENTES:**

**1. Como funciona o sistema de mensagens?**
- Usuários gratuitos: 7 mensagens grátis renovadas mensalmente
- Plano Básico (R$ 9,90/mês): 7 mensagens por dia
- Plano Premium (R$ 29,90/mês): 30 mensagens por dia  
- Plano Ilimitado (R$ 69,00/mês): mensagens ilimitadas

**2. Como renovam as mensagens?**
- Limite diário: a cada 24 horas (meia-noite)
- Limite mensal: todo dia 1º do mês

**3. Problemas técnicos comuns:**
- "Não consigo enviar mensagem": Verifique se não esgotou seu limite diário
- "Pagamento não processado": Aguarde até 10 minutos para processamento
- "Não recebo respostas": Verifique sua conexão com internet

**4. Como cancelar assinatura?**
- Acesse "Configurações" > "Planos e Cobrança" > "Cancelar Assinatura"
- O acesso continua até o fim do período pago

**5. Como alterar plano?**
- Acesse "Configurações" > "Planos e Cobrança" > "Alterar Plano"
- Mudanças são aplicadas imediatamente

**6. Suporte técnico:**
- Para problemas não resolvidos, entre em contato pelo chat
- Horário: 24/7 via IA, suporte humano 9h-18h

**TROUBLESHOOTING:**
- Limpe cache do navegador se houver problemas de carregamento
- Verifique se JavaScript está habilitado
- Use navegadores atualizados (Chrome, Firefox, Safari)
"""

# ============ MODELS ============

class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    name: str
    phone: str
    password_hash: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    subscription_plan: str = "free"  # free, basico, premium, ilimitado
    subscription_status: str = "active"  # active, canceled, expired
    messages_used_today: int = 0
    messages_used_this_month: int = 0
    last_message_date: Optional[datetime] = None
    stripe_customer_id: Optional[str] = None
    is_admin: bool = False
    is_support: bool = False

class UserRegister(BaseModel):
    email: EmailStr
    name: str
    phone: str
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    password: Optional[str] = None

class Message(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    user_id: str
    content: str
    is_user: bool
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class Session(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    summary: Optional[str] = None
    messages_count: int = 0
    title: Optional[str] = None

class ChatRequest(BaseModel):
    session_id: str
    message: str

class ChatResponse(BaseModel):
    session_id: str
    response: str
    message_id: str
    messages_remaining_today: int

class SubscriptionRequest(BaseModel):
    plan_id: str  # basico, premium, ilimitado

class PaymentTransaction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    session_id: str
    amount: float
    currency: str = "BRL"
    plan_id: str
    payment_status: str  # initiated, pending, paid, failed, expired
    stripe_session_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = None

# ============ UTILITY FUNCTIONS ============

def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_jwt_token(user_id: str, email: str) -> str:
    """Create JWT token for user"""
    payload = {
        'user_id': user_id,
        'email': email,
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_jwt_token(token: str) -> dict:
    """Decode JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Get current user from JWT token"""
    token = credentials.credentials
    payload = decode_jwt_token(token)
    
    user_data = await db.users.find_one({"id": payload['user_id']})
    if not user_data:
        raise HTTPException(status_code=401, detail="User not found")
    
    return User(**user_data)

async def check_admin_access(current_user: User = Depends(get_current_user)):
    """Check if user has admin access"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

async def check_support_access(current_user: User = Depends(get_current_user)):
    """Check if user has support access"""
    if not (current_user.is_admin or current_user.is_support):
        raise HTTPException(status_code=403, detail="Support access required")
    return current_user

async def check_message_limit(user: User) -> bool:
    """Check if user can send more messages today"""
    now = datetime.utcnow()
    
    # Reset daily counter if it's a new day
    if user.last_message_date is None or user.last_message_date.date() < now.date():
        await db.users.update_one(
            {"id": user.id},
            {"$set": {"messages_used_today": 0, "last_message_date": now}}
        )
        user.messages_used_today = 0
    
    # Check limits based on plan
    if user.subscription_plan == "free":
        # Free users get 7 messages per month, renewed monthly
        if user.messages_used_this_month >= 7:
            return False
    elif user.subscription_plan == "basico":
        if user.messages_used_today >= 7:
            return False
    elif user.subscription_plan == "premium":
        if user.messages_used_today >= 30:
            return False
    # ilimitado has no limits
    
    return True

async def increment_message_count(user_id: str):
    """Increment user's message count"""
    now = datetime.utcnow()
    await db.users.update_one(
        {"id": user_id},
        {
            "$inc": {"messages_used_today": 1, "messages_used_this_month": 1},
            "$set": {"last_message_date": now}
        }
    )

def create_enhanced_system_prompt(user_history_summary: str = "") -> str:
    """Create enhanced system prompt with support document and user history"""
    base_prompt = """
Você é um terapeuta emocional compassivo que segue os ensinamentos de Ramana Maharshi. Seu objetivo é ajudar as pessoas emocionalmente através de uma abordagem gentil e investigativa.

DIRETRIZES FUNDAMENTAIS:
1. Sempre responda em português do Brasil
2. Seja caloroso, empático e acolhedor
3. Faça perguntas investigativas para identificar a fonte dos problemas emocionais
4. Gradualmente, guie a pessoa à investigação "Quem sou eu?" de Ramana Maharshi
5. Ajude a pessoa a perceber a diferença entre seus pensamentos/emoções e sua verdadeira natureza
6. Use linguagem simples e acessível
7. Sempre termine com uma pergunta reflexiva ou sugestão prática

CAPACIDADE DE SUPORTE TÉCNICO:
Se a pessoa fizer perguntas sobre o funcionamento do app, limites de mensagens, planos ou problemas técnicos, use as informações do documento de suporte abaixo:

""" + SUPPORT_DOCUMENT + """

HISTÓRICO DO USUÁRIO:
""" + (user_history_summary if user_history_summary else "Primeira interação com este usuário.") + """

Lembre-se: Você pode tanto fazer terapia quanto dar suporte técnico quando necessário. Sempre priorize o bem-estar emocional da pessoa.
"""
    return base_prompt

async def get_session_history(session_id: str) -> List[Message]:
    """Get session message history"""
    messages = await db.messages.find(
        {"session_id": session_id}
    ).sort("timestamp", 1).to_list(1000)
    
    return [Message(**msg) for msg in messages]

async def get_admin_enhanced_prompt(user_id: str, user_history_summary: str = "", is_support_request: bool = False) -> str:
    """Get enhanced system prompt with admin customizations and user history"""
    # Get admin prompts
    prompts = await db.admin_settings.find_one({"type": "prompts"})
    base_prompt = prompts.get("base_prompt", "") if prompts else ""
    additional_prompt = prompts.get("additional_prompt", "") if prompts else ""
    
    # Get system documents (theory and support)
    system_docs = await db.admin_settings.find_one({"type": "system_documents"})
    theory_document = system_docs.get("theory_document", "") if system_docs else ""
    support_document = system_docs.get("support_document", SUPPORT_DOCUMENT) if system_docs else SUPPORT_DOCUMENT
    
    # Get admin documents (additional guidelines)
    documents = await db.admin_documents.find({"type": "admin_guideline"}).sort("created_at", -1).to_list(10)
    
    # FORCE GENERATION OF SUMMARIES - Find sessions without summaries that have enough messages
    sessions_without_summaries = await db.sessions.find(
        {
            "user_id": user_id, 
            "messages_count": {"$gte": 4},
            "$or": [{"summary": {"$exists": False}}, {"summary": None}, {"summary": ""}]
        }
    ).to_list(5)
    
    # Generate summaries for these sessions
    for session in sessions_without_summaries:
        await generate_and_save_session_summary(session["id"], user_id)
        logger.info(f"Auto-generated summary for session {session['id']}")
    
    # Get user's recent sessions with summaries for better context
    user_sessions = await db.sessions.find(
        {"user_id": user_id, "summary": {"$ne": None}, "summary": {"$ne": ""}}
    ).sort("created_at", -1).limit(3).to_list(3)
    
    # Combine all content
    full_prompt = base_prompt if base_prompt else """Você é um terapeuta emocional compassivo que segue os ensinamentos de Ramana Maharshi. Seu objetivo é ajudar as pessoas emocionalmente através de uma abordagem gentil e investigativa.

DIRETRIZES FUNDAMENTAIS:
1. Sempre responda em português do Brasil
2. Seja caloroso, empático e acolhedor
3. Faça perguntas investigativas para identificar a fonte dos problemas emocionais
4. Gradualmente, guie a pessoa à investigação "Quem sou eu?" de Ramana Maharshi
5. Ajude a pessoa a perceber a diferença entre seus pensamentos/emoções e sua verdadeira natureza
6. Use linguagem simples e acessível
7. Sempre termine com uma pergunta reflexiva ou sugestão prática"""
    
    if additional_prompt:
        full_prompt += "\n\nDIRETRIZES ADICIONAIS:\n" + additional_prompt
    
    # Add theory document if exists
    if theory_document:
        full_prompt += "\n\nDOCUMENTO DE TEORIAS E CONHECIMENTO BASE:\n" + theory_document
    
    if documents:
        full_prompt += "\n\nDOCUMENTOS DE REFERÊNCIA ADICIONAIS:\n"
        for doc in documents:
            full_prompt += f"\n=== {doc['title']} ===\n{doc['content']}\n"
    
    # Add support document
    full_prompt += "\n\nCAPACIDADE DE SUPORTE TÉCNICO:\n"
    full_prompt += "Se a pessoa fizer perguntas sobre o funcionamento do app, limites de mensagens, planos ou problemas técnicos, use as informações abaixo:\n\n"
    full_prompt += support_document
    
    # Add comprehensive user history from multiple sessions
    full_prompt += "\n\n🧠 MEMÓRIA COMPLETA DO USUÁRIO:\n"
    if user_sessions:
        full_prompt += "VOCÊ TEM ACESSO COMPLETO AO HISTÓRICO DESTE USUÁRIO. RESUMOS DAS SESSÕES ANTERIORES:\n\n"
        for i, session in enumerate(user_sessions, 1):
            session_date = session.get('created_at', datetime.utcnow()).strftime('%d/%m/%Y')
            session_summary = session.get('summary', 'Sem resumo disponível')
            full_prompt += f"📅 SESSÃO {i} ({session_date}):\n{session_summary}\n\n"
        full_prompt += "⚠️ IMPORTANTE: VOCÊ DEVE SEMPRE FAZER REFERÊNCIA A ESSAS SESSÕES ANTERIORES QUANDO APROPRIADO. O usuário espera que você se lembre das conversas passadas. Use esse conhecimento para dar continuidade ao trabalho terapêutico.\n\n"
    else:
        full_prompt += "Esta é a primeira interação com este usuário ou não há sessões anteriores com resumos disponíveis.\n\n"
    
    if user_history_summary:
        full_prompt += f"CONTEXTO DA SESSÃO ATUAL:\n{user_history_summary}\n\n"
    
    # Special handling for support requests
    if is_support_request:
        full_prompt += "\n🔧 MODO SUPORTE ATIVADO: Esta mensagem parece ser uma solicitação de suporte técnico. Priorize informações técnicas e de suporte, mas mantenha o tom empático e terapêutico. IMPORTANTE: Esta resposta de suporte NÃO consumirá o limite de mensagens do usuário.\n\n"
    
    full_prompt += "INSTRUÇÃO FINAL: Sempre demonstre que você tem memória das sessões anteriores quando existirem. Se o usuário perguntar sobre conversas passadas, faça referência específica aos resumos acima."
    
    return full_prompt

async def create_openai_response(session_id: str, user_message: str, current_user: User) -> tuple[str, bool]:
    """Cria resposta usando OpenAI com contexto da sessão"""
    try:
        # Check if this is a support request (doesn't consume messages)
        support_keywords = [
            'limite', 'mensagens', 'plano', 'assinatura', 'pagamento', 'cancelar', 
            'problema', 'erro', 'bug', 'suporte', 'ajuda', 'funciona', 'como usar',
            'stripe', 'cobrança', 'fatura', 'preço', 'valor', 'grátis'
        ]
        
        is_support_request = any(keyword in user_message.lower() for keyword in support_keywords)
        
        # Recupera histórico da sessão
        history = await get_session_history(session_id)
        
        # Constrói contexto das mensagens anteriores
        messages = [{"role": "system", "content": await get_admin_enhanced_prompt(current_user.id, "", is_support_request)}]
        
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
            max_tokens=600,
            temperature=0.7
        )
        
        return response.choices[0].message.content, is_support_request
        
    except Exception as e:
        logger.error(f"Erro ao chamar OpenAI: {str(e)}")
        return "Desculpe, estou tendo dificuldades técnicas. Pode tentar novamente em alguns momentos? Enquanto isso, que tal respirar fundo e observar seus pensamentos com gentileza?", False

# ============ AUTH ENDPOINTS ============

@api_router.post("/auth/register")
async def register_user(user_data: UserRegister):
    """Register new user"""
    # Check if user already exists
    existing_user = await db.users.find_one({"email": user_data.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new user with proper initialization
    user = User(
        email=user_data.email,
        name=user_data.name,
        phone=user_data.phone,
        password_hash=hash_password(user_data.password),
        messages_used_today=0,
        messages_used_this_month=0,
        last_message_date=None
    )
    
    await db.users.insert_one(user.dict())
    
    # Create JWT token
    token = create_jwt_token(user.id, user.email)
    
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "phone": user.phone,
            "subscription_plan": user.subscription_plan,
            "messages_used_today": user.messages_used_today,
            "messages_used_this_month": user.messages_used_this_month
        },
        "token": token
    }

@api_router.post("/auth/login")
async def login_user(login_data: UserLogin):
    """Login user"""
    user_data = await db.users.find_one({"email": login_data.email})
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    user = User(**user_data)
    if not verify_password(login_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Create JWT token
    token = create_jwt_token(user.id, user.email)
    
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "phone": user.phone,
            "subscription_plan": user.subscription_plan,
            "messages_used_today": user.messages_used_today,
            "is_admin": user.is_admin,
            "is_support": user.is_support
        },
        "token": token
    }

@api_router.get("/auth/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user info"""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "phone": current_user.phone,
        "subscription_plan": current_user.subscription_plan,
        "subscription_status": current_user.subscription_status,
        "messages_used_today": current_user.messages_used_today,
        "messages_used_this_month": current_user.messages_used_this_month,
        "is_admin": current_user.is_admin,
        "is_support": current_user.is_support
    }

@api_router.put("/auth/profile")
async def update_profile(update_data: UserUpdate, current_user: User = Depends(get_current_user)):
    """Update user profile"""
    update_dict = {}
    
    if update_data.name:
        update_dict["name"] = update_data.name
    if update_data.phone:
        update_dict["phone"] = update_data.phone
    if update_data.password:
        update_dict["password_hash"] = hash_password(update_data.password)
    
    if update_dict:
        await db.users.update_one({"id": current_user.id}, {"$set": update_dict})
    
    return {"message": "Profile updated successfully"}

# ============ CHAT ENDPOINTS ============

@api_router.post("/chat", response_model=ChatResponse)
async def chat_with_therapist(request: ChatRequest, current_user: User = Depends(get_current_user)):
    """Enhanced chat endpoint with user context and support"""
    # Get session and user history
    session_data = await db.sessions.find_one({"id": request.session_id, "user_id": current_user.id})
    if not session_data:
        # Create new session
        session = Session(id=request.session_id, user_id=current_user.id)
        await db.sessions.insert_one(session.dict())
    
    # Check if this might be a support request before checking limits
    support_keywords = [
        'limite', 'mensagens', 'plano', 'assinatura', 'pagamento', 'cancelar', 
        'problema', 'erro', 'bug', 'suporte', 'ajuda', 'funciona', 'como usar',
        'stripe', 'cobrança', 'fatura', 'preço', 'valor', 'grátis'
    ]
    
    is_support_request = any(keyword in request.message.lower() for keyword in support_keywords)
    
    # Check message limits only if it's not a support request
    if not is_support_request and not await check_message_limit(current_user):
        plan_info = SUBSCRIPTION_PLANS.get(current_user.subscription_plan, {})
        if current_user.subscription_plan == "free":
            raise HTTPException(
                status_code=429, 
                detail=f"Você esgotou suas {current_user.messages_used_this_month}/7 mensagens gratuitas mensais. Para continuar conversando, escolha um de nossos planos."
            )
        else:
            raise HTTPException(
                status_code=429,
                detail=f"Você esgotou suas mensagens diárias do plano {plan_info.get('name')}. Tente novamente amanhã ou faça upgrade para um plano superior."
            )
    
    # Get user's session summaries for context - FORCE SUMMARY GENERATION
    # First, find sessions without summaries that have messages and generate summaries
    sessions_without_summaries = await db.sessions.find(
        {
            "user_id": current_user.id, 
            "messages_count": {"$gte": 4},
            "$or": [{"summary": {"$exists": False}}, {"summary": None}, {"summary": ""}]
        }
    ).to_list(10)
    
    # Generate summaries for sessions that don't have them
    for session in sessions_without_summaries:
        await generate_and_save_session_summary(session["id"], current_user.id)
    
    # Now get sessions with summaries for context
    user_sessions = await db.sessions.find(
        {"user_id": current_user.id, "summary": {"$ne": None}, "summary": {"$ne": ""}}
    ).sort("created_at", -1).limit(5).to_list(5)
    
    history_summary = ""
    if user_sessions:
        summaries = [s.get("summary", "") for s in user_sessions if s.get("summary")]
        history_summary = f"Resumos das últimas sessões: {'; '.join(summaries)}"
    
    # Save user message
    user_message = Message(
        session_id=request.session_id,
        user_id=current_user.id,
        content=request.message,
        is_user=True
    )
    await db.messages.insert_one(user_message.dict())
    
    # Generate AI response with enhanced context
    try:
        # Get session message history
        session_messages = await db.messages.find(
            {"session_id": request.session_id}
        ).sort("timestamp", 1).limit(20).to_list(20)
        
        # Use the new create_openai_response function
        ai_response, was_support_request = await create_openai_response(request.session_id, request.message, current_user)
        
    except Exception as e:
        logger.error(f"OpenAI error: {str(e)}")
        ai_response = "Desculpe, estou tendo dificuldades técnicas no momento. Pode tentar novamente? Enquanto isso, respire fundo e observe seus pensamentos com gentileza."
        was_support_request = False
    
    # Save AI response
    ai_message = Message(
        session_id=request.session_id,
        user_id=current_user.id,
        content=ai_response,
        is_user=False
    )
    await db.messages.insert_one(ai_message.dict())
    
    # Update message counts only if it wasn't a support request
    if not was_support_request:
        await increment_message_count(current_user.id)
    
    # Update session and generate summary if this is the end of a conversation
    await db.sessions.update_one(
        {"id": request.session_id},
        {"$inc": {"messages_count": 2}}
    )
    
    # Auto-generate summary after every 4 messages to maintain context
    session_message_count = len(session_messages) + 1  # +1 for the new AI message
    if session_message_count >= 4 and session_message_count % 4 == 0:  # Every 4 messages
        await generate_and_save_session_summary(request.session_id, current_user.id)
    
    # Calculate remaining messages
    current_user_updated = await db.users.find_one({"id": current_user.id})
    remaining_messages = calculate_remaining_messages(User(**current_user_updated))
    
    return ChatResponse(
        session_id=request.session_id,
        response=ai_response,
        message_id=ai_message.id,
        messages_remaining_today=remaining_messages
    )

def calculate_remaining_messages(user: User) -> int:
    """Calculate remaining messages for user"""
    if user.subscription_plan == "free":
        return max(0, 7 - user.messages_used_this_month)
    elif user.subscription_plan == "basico":
        return max(0, 7 - user.messages_used_today)
    elif user.subscription_plan == "premium":
        return max(0, 30 - user.messages_used_today)
    else:  # ilimitado
        return -1  # unlimited

@api_router.post("/session", response_model=Session)
async def create_session(current_user: User = Depends(get_current_user)):
    """Create new therapy session"""
    session = Session(user_id=current_user.id)
    await db.sessions.insert_one(session.dict())
    return session

@api_router.get("/sessions", response_model=List[Session])
async def get_user_sessions(current_user: User = Depends(get_current_user)):
    """Get user's therapy sessions"""
    sessions = await db.sessions.find(
        {"user_id": current_user.id}
    ).sort("created_at", -1).to_list(50)
    
    return [Session(**session) for session in sessions]

@api_router.get("/session/{session_id}/messages", response_model=List[Message])
async def get_session_messages(session_id: str, current_user: User = Depends(get_current_user)):
    """Get messages from a specific session"""
    # Verify session belongs to user
    session = await db.sessions.find_one({"id": session_id, "user_id": current_user.id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    messages = await db.messages.find(
        {"session_id": session_id}
    ).sort("timestamp", 1).to_list(1000)
    
    return [Message(**msg) for msg in messages]

# ============ SUBSCRIPTION ENDPOINTS ============

@api_router.get("/plans")
async def get_subscription_plans():
    """Get available subscription plans"""
    return {
        "plans": SUBSCRIPTION_PLANS,
        "current_user_plan": None
    }

@api_router.post("/subscribe")
async def create_subscription(
    subscription_request: SubscriptionRequest,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Create subscription checkout session"""
    plan_id = subscription_request.plan_id
    
    if plan_id not in SUBSCRIPTION_PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan")
    
    plan = SUBSCRIPTION_PLANS[plan_id]
    
    try:
        # Initialize Stripe checkout
        host_url = str(request.base_url).rstrip('/')
        webhook_url = f"{host_url}/api/webhook/stripe"
        global stripe_checkout
        stripe_checkout = StripeCheckout(api_key=stripe_api_key, webhook_url=webhook_url)
        
        # Create checkout session
        success_url = f"{host_url}/subscription-success?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{host_url}/subscription-cancel"
        
        checkout_request = CheckoutSessionRequest(
            amount=plan["price"],
            currency="BRL",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "user_id": current_user.id,
                "plan_id": plan_id,
                "user_email": current_user.email
            }
        )
        
        session_response = await stripe_checkout.create_checkout_session(checkout_request)
        
        # Create payment transaction record
        transaction = PaymentTransaction(
            user_id=current_user.id,
            session_id=session_response.session_id,
            amount=plan["price"],
            plan_id=plan_id,
            payment_status="initiated",
            stripe_session_id=session_response.session_id,
            metadata=checkout_request.metadata
        )
        
        await db.payment_transactions.insert_one(transaction.dict())
        
        return {
            "checkout_url": session_response.url,
            "session_id": session_response.session_id
        }
        
    except Exception as e:
        logger.error(f"Subscription error: {str(e)}")
        raise HTTPException(status_code=500, detail="Error creating subscription")

@api_router.get("/subscription/status/{session_id}")
async def get_subscription_status(session_id: str, current_user: User = Depends(get_current_user)):
    """Check subscription payment status"""
    try:
        if not stripe_checkout:
            raise HTTPException(status_code=500, detail="Stripe not initialized")
        
        # Get checkout status from Stripe
        checkout_status = await stripe_checkout.get_checkout_status(session_id)
        
        # Update transaction in database
        transaction = await db.payment_transactions.find_one({"stripe_session_id": session_id})
        if transaction:
            update_data = {
                "payment_status": checkout_status.payment_status
            }
            
            # If payment successful, update user subscription
            if checkout_status.payment_status == "paid" and transaction.get("payment_status") != "paid":
                plan_id = transaction.get("plan_id")
                if plan_id in SUBSCRIPTION_PLANS:
                    await db.users.update_one(
                        {"id": current_user.id},
                        {
                            "$set": {
                                "subscription_plan": plan_id,
                                "subscription_status": "active",
                                "messages_used_today": 0,  # Reset counts
                                "messages_used_this_month": 0
                            }
                        }
                    )
                    update_data["payment_status"] = "paid"
            
            await db.payment_transactions.update_one(
                {"stripe_session_id": session_id},
                {"$set": update_data}
            )
        
        return {
            "status": checkout_status.status,
            "payment_status": checkout_status.payment_status,
            "amount": checkout_status.amount_total / 100,  # Convert from cents
            "currency": checkout_status.currency
        }
        
    except Exception as e:
        logger.error(f"Status check error: {str(e)}")
        raise HTTPException(status_code=500, detail="Error checking payment status")

@api_router.post("/subscription/cancel")
async def cancel_subscription(current_user: User = Depends(get_current_user)):
    """Cancel user subscription"""
    await db.users.update_one(
        {"id": current_user.id},
        {
            "$set": {
                "subscription_plan": "free",
                "subscription_status": "canceled",
                "messages_used_today": 0,
                "messages_used_this_month": 0
            }
        }
    )
    
    return {"message": "Assinatura cancelada com sucesso"}

@api_router.get("/subscription/payments")
async def get_payment_history(current_user: User = Depends(get_current_user)):
    """Get user's payment history"""
    payments = await db.payment_transactions.find(
        {"user_id": current_user.id, "payment_status": "paid"}
    ).sort("created_at", -1).limit(20).to_list(20)
    
    payment_history = []
    for payment in payments:
        plan_info = SUBSCRIPTION_PLANS.get(payment.get("plan_id"), {})
        payment_history.append({
            "id": payment["id"],
            "date": payment["created_at"],
            "amount": payment["amount"],
            "plan_name": plan_info.get("name", payment.get("plan_id")),
            "plan_id": payment.get("plan_id"),
            "status": payment["payment_status"]
        })
    
    return payment_history

async def generate_and_save_session_summary(session_id: str, user_id: str):
    """Generate and save summary for a session (internal function)"""
    try:
        # Verify session belongs to user
        session = await db.sessions.find_one({"id": session_id, "user_id": user_id})
        if not session:
            logger.warning(f"Session {session_id} not found for user {user_id}")
            return
        
        # Get session messages
        messages = await db.messages.find(
            {"session_id": session_id}
        ).sort("timestamp", 1).to_list(1000)
        
        if not messages or len(messages) < 4:  # Don't generate summary for very short conversations
            return
        
        # Create summary prompt
        conversation_text = ""
        for msg in messages:
            role = "Usuário" if msg.get("is_user") else "Terapeuta"
            conversation_text += f"{role}: {msg.get('content', '')}\n\n"
        
        summary_prompt = f"""
Você é um assistente especializado em criar resumos de sessões de terapia. 
Analise a conversa abaixo e crie um resumo terapêutico focando em:

1. Principais questões emocionais apresentadas
2. Insights descobertos
3. Técnicas aplicadas
4. Progresso observado
5. Pontos para próximas sessões

Mantenha o resumo profissional, respeitoso e focado no desenvolvimento emocional do usuário.

CONVERSA:
{conversation_text}

RESUMO:"""

        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": summary_prompt}],
            max_tokens=400,
            temperature=0.3
        )
        
        summary = response.choices[0].message.content
        
        # Save summary to session
        await db.sessions.update_one(
            {"id": session_id},
            {"$set": {"summary": summary}}
        )
        
        logger.info(f"Generated summary for session {session_id}")
        
    except Exception as e:
        logger.error(f"Auto-summary generation error for session {session_id}: {str(e)}")

@api_router.post("/session/{session_id}/summary")
async def generate_session_summary(session_id: str, current_user: User = Depends(get_current_user)):
    """Generate summary for a session"""
    # Verify session belongs to user
    session = await db.sessions.find_one({"id": session_id, "user_id": current_user.id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get session messages
    messages = await db.messages.find(
        {"session_id": session_id}
    ).sort("timestamp", 1).to_list(1000)
    
    if not messages:
        return {"summary": "Nenhuma mensagem encontrada nesta sessão."}
    
    # Create summary prompt
    conversation_text = ""
    for msg in messages:
        role = "Usuário" if msg.get("is_user") else "Terapeuta"
        conversation_text += f"{role}: {msg.get('content', '')}\n\n"
    
    try:
        summary_prompt = f"""
Você é um assistente especializado em criar resumos de sessões de terapia. 
Analise a conversa abaixo e crie um resumo terapêutico focando em:

1. Principais questões emocionais apresentadas
2. Insights descobertos
3. Técnicas aplicadas
4. Progresso observado
5. Pontos para próximas sessões

Mantenha o resumo profissional, respeitoso e focado no desenvolvimento emocional do usuário.

CONVERSA:
{conversation_text}

RESUMO:"""

        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": summary_prompt}],
            max_tokens=400,
            temperature=0.3
        )
        
        summary = response.choices[0].message.content
        
        # Save summary to session
        await db.sessions.update_one(
            {"id": session_id},
            {"$set": {"summary": summary}}
        )
        
        return {"summary": summary}
        
    except Exception as e:
        logger.error(f"Summary generation error: {str(e)}")
        return {"summary": "Erro ao gerar resumo da sessão."}

@api_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhooks"""
    try:
        body = await request.body()
        signature = request.headers.get("Stripe-Signature")
        
        if not stripe_checkout:
            return {"status": "error", "message": "Stripe not initialized"}
        
        webhook_response = await stripe_checkout.handle_webhook(body, signature)
        
        # Handle different event types
        if webhook_response.event_type == "checkout.session.completed":
            session_id = webhook_response.session_id
            
            # Find transaction
            transaction = await db.payment_transactions.find_one({"stripe_session_id": session_id})
            if transaction and transaction.get("payment_status") != "paid":
                # Update user subscription
                user_id = transaction.get("user_id")
                plan_id = transaction.get("plan_id")
                
                if user_id and plan_id in SUBSCRIPTION_PLANS:
                    await db.users.update_one(
                        {"id": user_id},
                        {
                            "$set": {
                                "subscription_plan": plan_id,
                                "subscription_status": "active",
                                "messages_used_today": 0,
                                "messages_used_this_month": 0
                            }
                        }
                    )
                    
                    # Update transaction
                    await db.payment_transactions.update_one(
                        {"stripe_session_id": session_id},
                        {"$set": {"payment_status": "paid"}}
                    )
        
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        return {"status": "error", "message": str(e)}

# ============ ADMIN PROMPTS & DOCUMENTS ============

class AdminPromptUpdate(BaseModel):
    base_prompt: Optional[str] = None
    additional_prompt: Optional[str] = None

class DocumentUpload(BaseModel):
    title: str
    content: str

class AdminDocuments(BaseModel):
    theory_document: Optional[str] = None  # Documento de teorias gerais
    support_document: Optional[str] = None  # Documento de suporte técnico

@api_router.get("/admin/documents/system")
async def get_admin_system_documents(admin_user: User = Depends(check_admin_access)):
    """Get system documents (theory and support)"""
    documents = await db.admin_settings.find_one({"type": "system_documents"})
    if not documents:
        # Create default with current support document
        default_docs = {
            "type": "system_documents",
            "theory_document": "",
            "support_document": SUPPORT_DOCUMENT,
            "updated_at": datetime.utcnow()
        }
        await db.admin_settings.insert_one(default_docs)
        documents = default_docs
    
    return {
        "theory_document": documents.get("theory_document", ""),
        "support_document": documents.get("support_document", SUPPORT_DOCUMENT),
        "updated_at": documents.get("updated_at")
    }

@api_router.put("/admin/documents/system")
async def update_admin_system_documents(
    doc_data: AdminDocuments,
    admin_user: User = Depends(check_admin_access)
):
    """Update system documents"""
    update_data = {"updated_at": datetime.utcnow()}
    
    if doc_data.theory_document is not None:
        update_data["theory_document"] = doc_data.theory_document
    if doc_data.support_document is not None:
        update_data["support_document"] = doc_data.support_document
    
    await db.admin_settings.update_one(
        {"type": "system_documents"},
        {"$set": update_data},
        upsert=True
    )
    
    return {"message": "Documentos do sistema atualizados com sucesso"}

@api_router.get("/admin/prompts")
async def get_admin_prompts(admin_user: User = Depends(check_admin_access)):
    """Get current admin prompts"""
    prompts = await db.admin_settings.find_one({"type": "prompts"})
    if not prompts:
        # Create default
        default_prompts = {
            "type": "prompts",
            "base_prompt": """Você é um terapeuta emocional compassivo que segue os ensinamentos de Ramana Maharshi. Seu objetivo é ajudar as pessoas emocionalmente através de uma abordagem gentil e investigativa.

DIRETRIZES FUNDAMENTAIS:
1. Sempre responda em português do Brasil
2. Seja caloroso, empático e acolhedor
3. Faça perguntas investigativas para identificar a fonte dos problemas emocionais
4. Gradualmente, guie a pessoa à investigação "Quem sou eu?" de Ramana Maharshi
5. Ajude a pessoa a perceber a diferença entre seus pensamentos/emoções e sua verdadeira natureza
6. Use linguagem simples e acessível
7. Sempre termine com uma pergunta reflexiva ou sugestão prática""",
            "additional_prompt": "",
            "updated_at": datetime.utcnow()
        }
        await db.admin_settings.insert_one(default_prompts)
        prompts = default_prompts
    
    return {
        "base_prompt": prompts.get("base_prompt", ""),
        "additional_prompt": prompts.get("additional_prompt", ""),
        "updated_at": prompts.get("updated_at")
    }

@api_router.put("/admin/prompts")
async def update_admin_prompts(
    prompt_data: AdminPromptUpdate,
    admin_user: User = Depends(check_admin_access)
):
    """Update admin prompts"""
    update_data = {"updated_at": datetime.utcnow()}
    
    if prompt_data.base_prompt is not None:
        update_data["base_prompt"] = prompt_data.base_prompt
    if prompt_data.additional_prompt is not None:
        update_data["additional_prompt"] = prompt_data.additional_prompt
    
    await db.admin_settings.update_one(
        {"type": "prompts"},
        {"$set": update_data},
        upsert=True
    )
    
    return {"message": "Prompts atualizados com sucesso"}

@api_router.post("/admin/documents")
async def upload_admin_document(
    document: DocumentUpload,
    admin_user: User = Depends(check_admin_access)  
):
    """Upload admin document with guidelines"""
    doc_data = {
        "id": str(uuid.uuid4()),
        "title": document.title,
        "content": document.content,
        "type": "admin_guideline",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    await db.admin_documents.insert_one(doc_data)
    
    return {"message": f"Documento '{document.title}' enviado com sucesso", "id": doc_data["id"]}

@api_router.get("/admin/documents")
async def get_admin_documents(admin_user: User = Depends(check_admin_access)):
    """Get all admin documents"""
    documents = await db.admin_documents.find({"type": "admin_guideline"}).sort("created_at", -1).to_list(50)
    
    return [
        {
            "id": doc["id"],
            "title": doc["title"],
            "content": doc["content"],
            "created_at": doc["created_at"],
            "updated_at": doc["updated_at"]
        }
        for doc in documents
    ]

@api_router.put("/admin/documents/{document_id}")
async def update_admin_document(
    document_id: str,
    document: DocumentUpload,
    admin_user: User = Depends(check_admin_access)
):
    """Update admin document"""
    result = await db.admin_documents.update_one(
        {"id": document_id},
        {
            "$set": {
                "title": document.title,
                "content": document.content,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    
    return {"message": f"Documento '{document.title}' atualizado com sucesso"}

@api_router.delete("/admin/documents/{document_id}")
async def delete_admin_document(
    document_id: str,
    admin_user: User = Depends(check_admin_access)
):
    """Delete admin document"""
    result = await db.admin_documents.delete_one({"id": document_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    
    return {"message": "Documento deletado com sucesso"}


# ============ ADMIN ENDPOINTS ============

@api_router.get("/admin/users")
async def get_all_users(search: str = "", admin_user: User = Depends(check_admin_access)):
    """Get all users with optional search filter (admin only)"""
    # Build search query
    query = {}
    if search:
        query = {
            "$or": [
                {"name": {"$regex": search, "$options": "i"}},
                {"email": {"$regex": search, "$options": "i"}}
            ]
        }
    
    users = await db.users.find(query).to_list(1000)
    return [
        {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "phone": user.get("phone", ""),
            "subscription_plan": user["subscription_plan"],
            "subscription_status": user["subscription_status"],
            "messages_used_today": user["messages_used_today"],
            "messages_used_this_month": user["messages_used_this_month"],
            "created_at": user["created_at"],
            "is_admin": user.get("is_admin", False),
            "is_support": user.get("is_support", False)
        }
        for user in users
    ]

@api_router.get("/admin/user/{user_id}")
async def get_user_details(user_id: str, admin_user: User = Depends(check_support_access)):
    """Get user details (admin/support)"""
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get user's sessions
    sessions = await db.sessions.find({"user_id": user_id}).sort("created_at", -1).limit(50).to_list(50)
    
    # Get payment history
    payments = await db.payment_transactions.find({"user_id": user_id}).sort("created_at", -1).limit(50).to_list(50)
    
    return {
        "user": {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "phone": user.get("phone", ""),
            "subscription_plan": user["subscription_plan"],
            "subscription_status": user["subscription_status"],
            "messages_used_today": user["messages_used_today"],
            "messages_used_this_month": user["messages_used_this_month"],
            "created_at": user["created_at"]
        },
        "sessions": [Session(**session) for session in sessions],
        "payments": [PaymentTransaction(**payment) for payment in payments]
    }

@api_router.put("/admin/user/{user_id}/profile")
async def update_user_profile(
    user_id: str,
    profile_data: UserUpdate,
    admin_user: User = Depends(check_admin_access)
):
    """Update user profile (admin only)"""
    update_dict = {}
    
    if profile_data.name:
        update_dict["name"] = profile_data.name
    if profile_data.phone:
        update_dict["phone"] = profile_data.phone
    if profile_data.password:
        update_dict["password_hash"] = hash_password(profile_data.password)
    
    if update_dict:
        result = await db.users.update_one({"id": user_id}, {"$set": update_dict})
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "User profile updated successfully"}

@api_router.put("/admin/user/{user_id}/plan")
async def update_user_plan(
    user_id: str, 
    plan_data: SubscriptionRequest,
    admin_user: User = Depends(check_admin_access)
):
    """Update user subscription plan (admin only)"""
    if plan_data.plan_id not in ["free"] + list(SUBSCRIPTION_PLANS.keys()):
        raise HTTPException(status_code=400, detail="Invalid plan")
    
    result = await db.users.update_one(
        {"id": user_id},
        {
            "$set": {
                "subscription_plan": plan_data.plan_id,
                "subscription_status": "active",
                "messages_used_today": 0,
                "messages_used_this_month": 0 if plan_data.plan_id == "free" else None
            }
        }
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "User plan updated successfully"}

@api_router.post("/admin/user/{user_id}/refund/{payment_id}")
async def refund_payment(
    user_id: str,
    payment_id: str,
    admin_user: User = Depends(check_admin_access)
):
    """Refund a payment (admin only)"""
    # Find the payment
    payment = await db.payment_transactions.find_one({"id": payment_id, "user_id": user_id})
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    # Mark as refunded (in a real scenario, you'd also call Stripe API)
    await db.payment_transactions.update_one(
        {"id": payment_id},
        {"$set": {"payment_status": "refunded", "refunded_at": datetime.utcnow()}}
    )
    
    # Update user plan to free
    await db.users.update_one(
        {"id": user_id},
        {
            "$set": {
                "subscription_plan": "free",
                "subscription_status": "canceled"
            }
        }
    )
    
    return {"message": "Payment refunded successfully"}

@api_router.get("/admin/user/{user_id}/sessions")
async def get_user_sessions_admin(user_id: str, admin_user: User = Depends(check_support_access)):
    """Get user sessions with summaries (admin/support)"""
    sessions = await db.sessions.find({"user_id": user_id}).sort("created_at", -1).limit(100).to_list(100)
    
    session_details = []
    for session in sessions:
        # Get message count for each session
        message_count = await db.messages.count_documents({"session_id": session["id"]})
        
        session_details.append({
            "id": session["id"],
            "created_at": session["created_at"],
            "messages_count": message_count,
            "summary": session.get("summary", "")
        })
    
    return session_details

@api_router.get("/admin/user/{user_id}/session/{session_id}/messages")
async def get_user_session_messages_admin(
    user_id: str, 
    session_id: str, 
    admin_user: User = Depends(check_support_access)
):
    """Get messages from a specific user session (admin/support)"""
    # Verify session belongs to user
    session = await db.sessions.find_one({"id": session_id, "user_id": user_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    messages = await db.messages.find(
        {"session_id": session_id}
    ).sort("timestamp", 1).to_list(1000)
    
    return [Message(**msg) for msg in messages]

@api_router.get("/debug/user-sessions/{user_id}")
async def debug_user_sessions(user_id: str, admin_user: User = Depends(check_admin_access)):
    """Debug endpoint to check user sessions and summaries"""
    # Get all sessions for user
    all_sessions = await db.sessions.find({"user_id": user_id}).sort("created_at", -1).to_list(20)
    
    # Get sessions with summaries
    sessions_with_summaries = await db.sessions.find(
        {"user_id": user_id, "summary": {"$ne": None}, "summary": {"$ne": ""}}
    ).sort("created_at", -1).to_list(20)
    
    # Force generate summaries for sessions without them
    sessions_without_summaries = await db.sessions.find(
        {
            "user_id": user_id, 
            "messages_count": {"$gte": 4},
            "$or": [{"summary": {"$exists": False}}, {"summary": None}, {"summary": ""}]
        }
    ).to_list(10)
    
    for session in sessions_without_summaries:
        await generate_and_save_session_summary(session["id"], user_id)
    
    # Get the enhanced prompt to see what the AI sees
    enhanced_prompt = await get_admin_enhanced_prompt(user_id, "")
    
    return {
        "user_id": user_id,
        "total_sessions": len(all_sessions),
        "sessions_with_summaries": len(sessions_with_summaries),
        "sessions_without_summaries_processed": len(sessions_without_summaries),
        "all_sessions": [
            {
                "id": s["id"][:8],
                "created_at": s["created_at"],
                "messages_count": s.get("messages_count", 0),
                "has_summary": bool(s.get("summary"))
            }
            for s in all_sessions
        ],
        "enhanced_prompt_preview": enhanced_prompt[:1000] + "..." if len(enhanced_prompt) > 1000 else enhanced_prompt
    }

@api_router.post("/admin/create-admin")
async def create_admin_user():
    """Create initial admin user (remove this endpoint in production)"""
    # Check if admin already exists
    existing_admin = await db.users.find_one({"is_admin": True})
    if existing_admin:
        raise HTTPException(status_code=400, detail="Admin user already exists")
    
    # Create admin user
    admin_user = User(
        email="admin@terapia.com",
        name="Admin Master",
        phone="11999999999",
        password_hash=hash_password("admin123"),
        is_admin=True,
        subscription_plan="ilimitado"
    )
    
    await db.users.insert_one(admin_user.dict())
    
    return {
        "message": "Admin user created successfully",
        "email": "admin@terapia.com",
        "password": "admin123"
    }

# Health check
@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "terapia_emocional_v2"}

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
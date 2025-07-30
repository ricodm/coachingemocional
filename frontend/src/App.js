import React, { useState, useEffect, useRef } from 'react';
import './App.css';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// ============ AUTH CONTEXT ============
const AuthContext = React.createContext();

const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (token) {
      checkAuth();
    } else {
      setLoading(false);
    }
  }, [token]);

  const checkAuth = async () => {
    try {
      const response = await axios.get(`${API}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setUser(response.data);
    } catch (error) {
      logout();
    } finally {
      setLoading(false);
    }
  };

  const login = (userData, userToken) => {
    setUser(userData);
    setToken(userToken);
    localStorage.setItem('token', userToken);
    axios.defaults.headers.common['Authorization'] = `Bearer ${userToken}`;
  };

  const logout = () => {
    setUser(null);
    setToken(null);
    localStorage.removeItem('token');
    delete axios.defaults.headers.common['Authorization'];
  };

  return (
    <AuthContext.Provider value={{ user, token, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
};

const useAuth = () => {
  const context = React.useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

// ============ COMPONENTS ============

const LoginForm = () => {
  const [isLogin, setIsLogin] = useState(true);
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    name: '',
    phone: ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const { login } = useAuth();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const endpoint = isLogin ? '/auth/login' : '/auth/register';
      const response = await axios.post(`${API}${endpoint}`, formData);
      
      login(response.data.user, response.data.token);
    } catch (error) {
      setError(error.response?.data?.detail || 'Erro na autenticação');
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h2>{isLogin ? 'Entrar' : 'Criar Conta'}</h2>
        
        {error && <div className="error-message">{error}</div>}
        
        <form onSubmit={handleSubmit}>
          <input
            type="email"
            name="email"
            placeholder="Email"
            value={formData.email}
            onChange={handleChange}
            required
          />
          
          <input
            type="password"
            name="password"
            placeholder="Senha"
            value={formData.password}
            onChange={handleChange}
            required
          />
          
          {!isLogin && (
            <>
              <input
                type="text"
                name="name"
                placeholder="Nome completo"
                value={formData.name}
                onChange={handleChange}
                required
              />
              <input
                type="tel"
                name="phone"
                placeholder="Telefone"
                value={formData.phone}
                onChange={handleChange}
                required
              />
            </>
          )}
          
          <button type="submit" disabled={loading}>
            {loading ? 'Carregando...' : (isLogin ? 'Entrar' : 'Criar Conta')}
          </button>
        </form>
        
        <p className="auth-switch">
          {isLogin ? 'Não tem conta? ' : 'Já tem conta? '}
          <button type="button" onClick={() => setIsLogin(!isLogin)}>
            {isLogin ? 'Criar uma' : 'Entrar'}
          </button>
        </p>
      </div>
    </div>
  );
};

const Chat = () => {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [remainingMessages, setRemainingMessages] = useState(0);
  const [showPlansModal, setShowPlansModal] = useState(false);
  const messagesEndRef = useRef(null);
  const { user, token } = useAuth();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    createSession();
  }, []);

  const createSession = async () => {
    try {
      const response = await axios.post(`${API}/session`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSessionId(response.data.id);
      
      setMessages([{
        id: 'welcome',
        content: `Olá ${user.name}! 🌟 Sou sua terapeuta emocional virtual. Estou aqui para te ouvir com carinho e ajudar você a se conectar com sua essência mais profunda.

Como você está se sentindo hoje? O que trouxe você até aqui?`,
        is_user: false,
        timestamp: new Date()
      }]);
    } catch (error) {
      console.error('Erro ao criar sessão:', error);
    }
  };

  const sendMessage = async () => {
    if (!inputMessage.trim() || !sessionId || isLoading) return;

    const userMessage = {
      id: Date.now().toString(),
      content: inputMessage,
      is_user: true,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);

    try {
      const response = await axios.post(`${API}/chat`, {
        session_id: sessionId,
        message: inputMessage
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });

      const aiMessage = {
        id: response.data.message_id,
        content: response.data.response,
        is_user: false,
        timestamp: new Date()
      };

      setMessages(prev => [...prev, aiMessage]);
      setRemainingMessages(response.data.messages_remaining_today);
    } catch (error) {
      console.error('Erro ao enviar mensagem:', error);
      let errorMsg = 'Desculpe, houve um problema. Por favor, tente novamente.';
      
      if (error.response?.status === 429) {
        errorMsg = error.response.data.detail;
        // Show plans modal when messages are exhausted
        setShowPlansModal(true);
      }
      
      const errorMessage = {
        id: 'error-' + Date.now(),
        content: errorMsg,
        is_user: false,
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const formatTime = (timestamp) => {
    return new Date(timestamp).toLocaleTimeString('pt-BR', {
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  return (
    <>
      <div className="chat-container">
        <div className="chat-header">
          <div className="user-info">
            <span>Olá, {user.name}</span>
            <span className="plan-badge">{user.subscription_plan}</span>
            {remainingMessages >= 0 && (
              <span className="messages-count">
                {remainingMessages === -1 ? '∞' : remainingMessages} msgs restantes
              </span>
            )}
          </div>
        </div>

        <div className="messages-container">
          {messages.map((message) => (
            <div key={message.id} className={`message ${message.is_user ? 'user' : 'ai'}`}>
              <div className="message-content">
                <div className="message-text">
                  {message.content}
                </div>
                <div className="message-time">
                  {formatTime(message.timestamp)}
                </div>
              </div>
            </div>
          ))}
          
          {isLoading && (
            <div className="message ai">
              <div className="message-content">
                <div className="typing-indicator">
                  <div className="typing-dots">
                    <div className="dot"></div>
                    <div className="dot"></div>
                    <div className="dot"></div>
                  </div>
                  <span>Refletindo...</span>
                </div>
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>

        <div className="input-container">
          <div className="input-wrapper">
            <textarea
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Compartilhe seus sentimentos..."
              className="message-input"
              rows="1"
              disabled={isLoading}
            />
            <button
              onClick={sendMessage}
              disabled={!inputMessage.trim() || isLoading}
              className="send-button"
            >
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                <path d="M22 2L11 13" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M22 2L15 22L11 13L2 9L22 2Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
          </div>
        </div>
      </div>

      {/* Plans Modal */}
      {showPlansModal && <PlansModal onClose={() => setShowPlansModal(false)} />}
    </>
  );
};

// Plans Modal Component
const PlansModal = ({ onClose }) => {
  const [plans, setPlans] = useState({});
  const [loading, setLoading] = useState(false);
  const { token } = useAuth();

  useEffect(() => {
    fetchPlans();
  }, []);

  const fetchPlans = async () => {
    try {
      const response = await axios.get(`${API}/plans`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setPlans(response.data.plans);
    } catch (error) {
      console.error('Erro ao carregar planos:', error);
    }
  };

  const subscribeToPlan = async (planId) => {
    setLoading(true);
    try {
      const response = await axios.post(`${API}/subscribe`, 
        { plan_id: planId },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      
      // Redirect to Stripe checkout
      window.location.href = response.data.checkout_url;
    } catch (error) {
      console.error('Erro na assinatura:', error);
      alert('Erro ao processar assinatura. Tente novamente.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Suas mensagens esgotaram!</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        
        <p className="modal-subtitle">Escolha um plano para continuar conversando:</p>
        
        <div className="modal-plans">
          {Object.entries(plans).map(([planId, plan]) => (
            <div key={planId} className="modal-plan-card">
              <h3>{plan.name}</h3>
              <div className="modal-price">R$ {plan.price.toFixed(2)}/mês</div>
              <div className="modal-features">
                <p>
                  {plan.messages_per_day === -1 
                    ? 'Mensagens ilimitadas' 
                    : `${plan.messages_per_day} mensagens por dia`
                  }
                </p>
              </div>
              
              <button 
                onClick={() => subscribeToPlan(planId)}
                disabled={loading}
                className="modal-subscribe-btn"
              >
                {loading ? 'Processando...' : 'Assinar Agora'}
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

const SubscriptionPlans = () => {
  const [plans, setPlans] = useState({});
  const [paymentHistory, setPaymentHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const { user, token } = useAuth();

  useEffect(() => {
    fetchPlans();
    fetchPaymentHistory();
  }, []);

  const fetchPlans = async () => {
    try {
      const response = await axios.get(`${API}/plans`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setPlans(response.data.plans);
    } catch (error) {
      console.error('Erro ao carregar planos:', error);
    }
  };

  const fetchPaymentHistory = async () => {
    try {
      const response = await axios.get(`${API}/subscription/payments`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setPaymentHistory(response.data);
    } catch (error) {
      console.error('Erro ao carregar histórico:', error);
    }
  };

  const subscribeToPlan = async (planId) => {
    setLoading(true);
    try {
      const response = await axios.post(`${API}/subscribe`, 
        { plan_id: planId },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      
      // Redirect to Stripe checkout
      window.location.href = response.data.checkout_url;
    } catch (error) {
      console.error('Erro na assinatura:', error);
      alert('Erro ao processar assinatura. Tente novamente.');
    } finally {
      setLoading(false);
    }
  };

  const cancelSubscription = async () => {
    if (!confirm('Tem certeza que deseja cancelar sua assinatura?')) return;
    
    setLoading(true);
    try {
      await axios.post(`${API}/subscription/cancel`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      alert('Assinatura cancelada com sucesso!');
      window.location.reload();
    } catch (error) {
      console.error('Erro ao cancelar:', error);
      alert('Erro ao cancelar assinatura. Tente novamente.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="plans-container">
      <h2>Escolha seu Plano</h2>
      <p>Seu plano atual: <strong>{user.subscription_plan}</strong></p>
      
      {user.subscription_plan !== 'free' && (
        <div className="cancel-section">
          <button onClick={cancelSubscription} disabled={loading} className="cancel-btn">
            {loading ? 'Cancelando...' : 'Cancelar Assinatura'}
          </button>
        </div>
      )}
      
      <div className="plans-grid">
        {Object.entries(plans).map(([planId, plan]) => (
          <div key={planId} className={`plan-card ${user.subscription_plan === planId ? 'current' : ''}`}>
            <h3>{plan.name}</h3>
            <div className="price">R$ {plan.price.toFixed(2)}/mês</div>
            <div className="features">
              <p>
                {plan.messages_per_day === -1 
                  ? 'Mensagens ilimitadas' 
                  : `${plan.messages_per_day} mensagens por dia`
                }
              </p>
            </div>
            
            {user.subscription_plan !== planId && (
              <button 
                onClick={() => subscribeToPlan(planId)}
                disabled={loading}
                className="subscribe-btn"
              >
                {loading ? 'Processando...' : 'Assinar'}
              </button>
            )}
          </div>
        ))}
      </div>

      {paymentHistory.length > 0 && (
        <div className="payment-history">
          <h3>Histórico de Pagamentos</h3>
          <div className="payments-list">
            {paymentHistory.map((payment) => (
              <div key={payment.id} className="payment-card">
                <div className="payment-info">
                  <strong>{payment.plan_name}</strong>
                  <span className="payment-amount">R$ {payment.amount.toFixed(2)}</span>
                </div>
                <div className="payment-date">
                  {new Date(payment.date).toLocaleDateString('pt-BR')}
                </div>
                <div className="payment-status">✅ Pago</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

const Profile = () => {
  const [profileData, setProfileData] = useState({
    name: '',
    phone: '',
    email: '',
    password: '',
    confirmPassword: ''
  });
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const { user, token } = useAuth();

  useEffect(() => {
    setProfileData({
      name: user.name || '',
      phone: user.phone || '',
      email: user.email || '',
      password: '',
      confirmPassword: ''
    });
  }, [user]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage('');
    setError('');

    // Validate passwords if provided
    if (profileData.password && profileData.password !== profileData.confirmPassword) {
      setError('As senhas não coincidem');
      setLoading(false);
      return;
    }

    if (profileData.password && profileData.password.length < 6) {
      setError('A senha deve ter pelo menos 6 caracteres');
      setLoading(false);
      return;
    }

    try {
      const updateData = {};
      if (profileData.name !== user.name) updateData.name = profileData.name;
      if (profileData.phone !== user.phone) updateData.phone = profileData.phone;
      if (profileData.password) updateData.password = profileData.password;

      if (Object.keys(updateData).length > 0) {
        await axios.put(`${API}/auth/profile`, updateData, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setMessage('Perfil atualizado com sucesso!');
        setProfileData({...profileData, password: '', confirmPassword: ''});
      } else {
        setMessage('Nenhuma alteração detectada.');
      }
    } catch (error) {
      setError('Erro ao atualizar perfil');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="profile-container">
      <h2>Meu Perfil</h2>
      
      {message && <div className="success-message">{message}</div>}
      {error && <div className="error-message">{error}</div>}
      
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label>Email</label>
          <input
            type="email"
            value={profileData.email}
            disabled
            className="disabled-input"
          />
          <small>O email não pode ser alterado</small>
        </div>
        
        <div className="form-group">
          <label>Nome</label>
          <input
            type="text"
            placeholder="Nome completo"
            value={profileData.name}
            onChange={(e) => setProfileData({...profileData, name: e.target.value})}
          />
        </div>
        
        <div className="form-group">
          <label>Telefone</label>
          <input
            type="tel"
            placeholder="Telefone"
            value={profileData.phone}
            onChange={(e) => setProfileData({...profileData, phone: e.target.value})}
          />
        </div>
        
        <div className="form-group">
          <label>Nova Senha (deixe em branco para não alterar)</label>
          <input
            type="password"
            placeholder="Nova senha"
            value={profileData.password}
            onChange={(e) => setProfileData({...profileData, password: e.target.value})}
          />
        </div>
        
        {profileData.password && (
          <div className="form-group">
            <label>Confirmar Nova Senha</label>
            <input
              type="password"
              placeholder="Confirme a nova senha"
              value={profileData.confirmPassword}
              onChange={(e) => setProfileData({...profileData, confirmPassword: e.target.value})}
            />
          </div>
        )}
        
        <button type="submit" disabled={loading}>
          {loading ? 'Salvando...' : 'Salvar Alterações'}
        </button>
      </form>
      
      <div className="user-stats">
        <h3>Estatísticas</h3>
        <div className="stats-grid">
          <div className="stat-item">
            <label>Plano Atual:</label>
            <span>{user.subscription_plan}</span>
          </div>
          <div className="stat-item">
            <label>Mensagens Hoje:</label>
            <span>{user.messages_used_today}</span>
          </div>
          <div className="stat-item">
            <label>Mensagens Este Mês:</label>
            <span>{user.messages_used_this_month}</span>
          </div>
        </div>
      </div>
    </div>
  );
};

const SessionHistory = () => {
  const [sessions, setSessions] = useState([]);
  const [selectedSession, setSelectedSession] = useState(null);
  const [sessionDetails, setSessionDetails] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const { token } = useAuth();

  useEffect(() => {
    fetchSessions();
  }, []);

  const fetchSessions = async () => {
    try {
      const response = await axios.get(`${API}/sessions`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSessions(response.data);
    } catch (error) {
      console.error('Erro ao carregar sessões:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchSessionDetails = async (sessionId) => {
    setLoadingDetails(true);
    try {
      // Get messages
      const messagesResponse = await axios.get(`${API}/session/${sessionId}/messages`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      // Generate or get summary
      const summaryResponse = await axios.post(`${API}/session/${sessionId}/summary`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      setSessionDetails({
        messages: messagesResponse.data,
        summary: summaryResponse.data.summary
      });
    } catch (error) {
      console.error('Erro ao carregar detalhes:', error);
      alert('Erro ao carregar detalhes da sessão');
    } finally {
      setLoadingDetails(false);
    }
  };

  const openSession = (session) => {
    setSelectedSession(session);
    fetchSessionDetails(session.id);
  };

  const closeSession = () => {
    setSelectedSession(null);
    setSessionDetails(null);
  };

  if (loading) return <div className="loading">Carregando histórico...</div>;

  return (
    <div className="history-container">
      <h2>Histórico de Sessões</h2>
      
      {selectedSession ? (
        <div className="session-detail">
          <div className="session-detail-header">
            <h3>Sessão de {new Date(selectedSession.created_at).toLocaleDateString('pt-BR')}</h3>
            <button onClick={closeSession} className="close-btn">✖ Fechar</button>
          </div>
          
          {loadingDetails ? (
            <div className="loading">Carregando detalhes...</div>
          ) : sessionDetails ? (
            <div className="session-content">
              <div className="session-summary">
                <h4>Resumo da Sessão</h4>
                <div className="summary-text">
                  {sessionDetails.summary}
                </div>
              </div>
              
              <div className="session-messages">
                <h4>Conversa Completa ({sessionDetails.messages.length} mensagens)</h4>
                <div className="messages-list">
                  {sessionDetails.messages.map((message, index) => (
                    <div key={message.id} className={`history-message ${message.is_user ? 'user' : 'ai'}`}>
                      <div className="message-header">
                        <strong>{message.is_user ? 'Você' : 'Terapeuta'}</strong>
                        <span className="message-time">
                          {new Date(message.timestamp).toLocaleString('pt-BR')}
                        </span>
                      </div>
                      <div className="message-content">{message.content}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : null}
        </div>
      ) : (
        <>
          {sessions.length === 0 ? (
            <p>Nenhuma sessão encontrada.</p>
          ) : (
            <div className="sessions-list">
              {sessions.map((session) => (
                <div key={session.id} className="session-card" onClick={() => openSession(session)}>
                  <h3>{session.title || `Sessão ${session.id.slice(0, 8)}`}</h3>
                  <p>{session.messages_count} mensagens</p>
                  <p>{new Date(session.created_at).toLocaleDateString('pt-BR')}</p>
                  {session.summary && <p className="summary-preview">{session.summary.substring(0, 100)}...</p>}
                  <div className="session-action">Clique para ver detalhes →</div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
};

const AdminPanel = () => {
  const [activeTab, setActiveTab] = useState('prompts');
  const [prompts, setPrompts] = useState({ base_prompt: '', additional_prompt: '' });
  const [documents, setDocuments] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [newDocument, setNewDocument] = useState({ title: '', content: '' });
  const { token } = useAuth();

  useEffect(() => {
    if (activeTab === 'prompts') fetchPrompts();
    if (activeTab === 'documents') fetchDocuments();
    if (activeTab === 'users') fetchUsers();
  }, [activeTab]);

  const fetchPrompts = async () => {
    try {
      const response = await axios.get(`${API}/admin/prompts`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setPrompts(response.data);
    } catch (error) {
      console.error('Erro ao carregar prompts:', error);
    }
  };

  const updatePrompts = async () => {
    setLoading(true);
    try {
      await axios.put(`${API}/admin/prompts`, prompts, {
        headers: { Authorization: `Bearer ${token}` }
      });
      alert('Prompts atualizados com sucesso!');
    } catch (error) {
      alert('Erro ao atualizar prompts');
    } finally {
      setLoading(false);
    }
  };

  const fetchDocuments = async () => {
    try {
      const response = await axios.get(`${API}/admin/documents`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setDocuments(response.data);
    } catch (error) {
      console.error('Erro ao carregar documentos:', error);
    }
  };

  const uploadDocument = async () => {
    if (!newDocument.title || !newDocument.content) {
      alert('Preencha título e conteúdo');
      return;
    }

    setLoading(true);
    try {
      await axios.post(`${API}/admin/documents`, newDocument, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setNewDocument({ title: '', content: '' });
      fetchDocuments();
      alert('Documento enviado com sucesso!');
    } catch (error) {
      alert('Erro ao enviar documento');
    } finally {
      setLoading(false);
    }
  };

  const deleteDocument = async (docId) => {
    if (!confirm('Tem certeza que deseja deletar este documento?')) return;

    try {
      await axios.delete(`${API}/admin/documents/${docId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      fetchDocuments();
      alert('Documento deletado com sucesso!');
    } catch (error) {
      alert('Erro ao deletar documento');
    }
  };

  const fetchUsers = async () => {
    try {
      const response = await axios.get(`${API}/admin/users`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setUsers(response.data);
    } catch (error) {
      console.error('Erro ao carregar usuários:', error);
    }
  };

  return (
    <div className="admin-container">
      <h2>Painel Admin</h2>
      
      <div className="admin-tabs">
        <button 
          className={activeTab === 'prompts' ? 'active' : ''} 
          onClick={() => setActiveTab('prompts')}
        >
          Prompts do GPT
        </button>
        <button 
          className={activeTab === 'documents' ? 'active' : ''} 
          onClick={() => setActiveTab('documents')}
        >
          Documentos
        </button>
        <button 
          className={activeTab === 'users' ? 'active' : ''} 
          onClick={() => setActiveTab('users')}
        >
          Usuários
        </button>
      </div>

      {activeTab === 'prompts' && (
        <div className="admin-section">
          <h3>Configurar Prompts do GPT</h3>
          
          <div className="prompt-section">
            <label>Prompt Base:</label>
            <textarea
              value={prompts.base_prompt}
              onChange={(e) => setPrompts({...prompts, base_prompt: e.target.value})}
              rows="10"
              placeholder="Prompt principal para o GPT..."
            />
          </div>

          <div className="prompt-section">
            <label>Prompt Adicional:</label>
            <textarea
              value={prompts.additional_prompt}
              onChange={(e) => setPrompts({...prompts, additional_prompt: e.target.value})}
              rows="6"
              placeholder="Diretrizes adicionais..."
            />
          </div>

          <button onClick={updatePrompts} disabled={loading}>
            {loading ? 'Salvando...' : 'Salvar Prompts'}
          </button>
        </div>
      )}

      {activeTab === 'documents' && (
        <div className="admin-section">
          <h3>Documentos de Referência</h3>
          
          <div className="upload-section">
            <h4>Novo Documento</h4>
            <input
              type="text"
              placeholder="Título do documento"
              value={newDocument.title}
              onChange={(e) => setNewDocument({...newDocument, title: e.target.value})}
            />
            <textarea
              placeholder="Conteúdo do documento (teorias, diretrizes, etc.)"
              value={newDocument.content}
              onChange={(e) => setNewDocument({...newDocument, content: e.target.value})}
              rows="8"
            />
            <button onClick={uploadDocument} disabled={loading}>
              {loading ? 'Enviando...' : 'Enviar Documento'}
            </button>
          </div>

          <div className="documents-list">
            <h4>Documentos Existentes</h4>
            {documents.map((doc) => (
              <div key={doc.id} className="document-card">
                <h5>{doc.title}</h5>
                <p>{doc.content.substring(0, 200)}...</p>
                <small>{new Date(doc.created_at).toLocaleDateString('pt-BR')}</small>
                <button onClick={() => deleteDocument(doc.id)} className="delete-btn">
                  Deletar
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'users' && (
        <div className="admin-section">
          <h3>Gerenciar Usuários</h3>
          
          <div className="users-table">
            {users.map((user) => (
              <div key={user.id} className="user-row">
                <div>
                  <strong>{user.name}</strong>
                  <br />
                  {user.email}
                </div>
                <div>Plano: {user.subscription_plan}</div>
                <div>Msgs hoje: {user.messages_used_today}</div>
                <div>{new Date(user.created_at).toLocaleDateString('pt-BR')}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

const Navigation = () => {
  const [activeView, setActiveView] = useState('chat');
  const { user, logout } = useAuth();

  const views = {
    chat: <Chat />,
    plans: <SubscriptionPlans />,
    profile: <Profile />,
    history: <SessionHistory />,
    ...(user.is_admin && { admin: <AdminPanel /> })
  };

  return (
    <div className="app-container">
      <nav className="sidebar">
        <div className="nav-header">
          <h2>Terapia Emocional</h2>
        </div>
        
        <div className="nav-links">
          <button 
            className={activeView === 'chat' ? 'active' : ''} 
            onClick={() => setActiveView('chat')}
          >
            💬 Chat
          </button>
          <button 
            className={activeView === 'plans' ? 'active' : ''} 
            onClick={() => setActiveView('plans')}
          >
            💳 Planos
          </button>
          <button 
            className={activeView === 'profile' ? 'active' : ''} 
            onClick={() => setActiveView('profile')}
          >
            👤 Perfil
          </button>
          <button 
            className={activeView === 'history' ? 'active' : ''} 
            onClick={() => setActiveView('history')}
          >
            📝 Histórico
          </button>
          
          {user.is_admin && (
            <button 
              className={activeView === 'admin' ? 'active' : ''} 
              onClick={() => setActiveView('admin')}
            >
              ⚙️ Admin
            </button>
          )}
        </div>
        
        <div className="nav-footer">
          <button onClick={logout} className="logout-btn">
            🚪 Sair
          </button>
        </div>
      </nav>
      
      <main className="main-content">
        {views[activeView]}
      </main>
    </div>
  );
};

// ============ MAIN APP ============

function App() {
  return (
    <AuthProvider>
      <div className="App">
        <AppContent />
      </div>
    </AuthProvider>
  );
}

const AppContent = () => {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="loading-container">
        <div className="loading-spinner"></div>
        <p>Carregando...</p>
      </div>
    );
  }

  return user ? <Navigation /> : <LoginForm />;
};

export default App;
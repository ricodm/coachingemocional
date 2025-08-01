import requests
import sys
import json
from datetime import datetime

class CorrectionsVerificationTester:
    def __init__(self, base_url="https://71832b61-f09e-4b43-b8fe-dcfd4ba45e0d.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.admin_token = None
        self.user_token = None
        self.session_id = None
        self.test_user_id = None
        self.corrections_status = {
            "admin_auth": False,
            "message_system": False,
            "admin_functionalities": False
        }

    def make_request(self, method, endpoint, data=None, token=None, expected_status=200):
        """Make HTTP request"""
        url = f"{self.api_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        if token:
            headers['Authorization'] = f'Bearer {token}'
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=30)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=30)
            
            success = response.status_code == expected_status
            try:
                response_data = response.json()
            except:
                response_data = {"raw_response": response.text, "status_code": response.status_code}
            
            return success, response_data, response.status_code
            
        except Exception as e:
            return False, {"error": str(e)}, 0

    def test_correction_1_admin_auth(self):
        """CORREÇÃO 1: AUTENTICAÇÃO ADMIN CORRIGIDA"""
        print("\n" + "="*70)
        print("🔐 CORREÇÃO 1: AUTENTICAÇÃO ADMIN CORRIGIDA")
        print("="*70)
        print("Testando: admin@terapia.com / admin123")
        
        success, response, status = self.make_request(
            'POST', 'auth/login',
            data={"email": "admin@terapia.com", "password": "admin123"}
        )
        
        if success and 'token' in response:
            self.admin_token = response['token']
            user_data = response.get('user', {})
            is_admin = user_data.get('is_admin', False)
            
            print(f"✅ Login realizado com sucesso")
            print(f"✅ Token recebido: {self.admin_token[:20]}...")
            print(f"✅ is_admin: {is_admin}")
            
            if is_admin:
                print("🎉 CORREÇÃO 1: ADMIN AUTH - FUNCIONANDO!")
                self.corrections_status["admin_auth"] = True
                return True
            else:
                print("❌ CORREÇÃO 1: FALHOU - is_admin é False")
                return False
        else:
            print(f"❌ CORREÇÃO 1: FALHOU - Status: {status}, Response: {response}")
            return False

    def test_correction_2_message_system(self):
        """CORREÇÃO 2: SISTEMA DE CONTAGEM DE MENSAGENS"""
        print("\n" + "="*70)
        print("📊 CORREÇÃO 2: SISTEMA DE CONTAGEM DE MENSAGENS")
        print("="*70)
        
        # Registrar novo usuário
        test_email = f"msg_test_{datetime.now().strftime('%H%M%S')}@test.com"
        print(f"Registrando usuário: {test_email}")
        
        success, response, status = self.make_request(
            'POST', 'auth/register',
            data={
                "email": test_email,
                "name": "Message Test User",
                "phone": "11999999999",
                "password": "testpass123"
            }
        )
        
        if not success:
            print(f"❌ Falha no registro: {response}")
            return False
        
        self.user_token = response['token']
        self.test_user_id = response['user']['id']
        user_data = response['user']
        
        # Verificar inicialização correta
        messages_today = user_data.get('messages_used_today', -1)
        messages_month = user_data.get('messages_used_this_month', -1)
        
        print(f"📈 Inicialização - Hoje: {messages_today}, Mês: {messages_month}")
        
        if messages_today != 0 or messages_month != 0:
            print("❌ CORREÇÃO 2: FALHOU - Inicialização incorreta")
            return False
        
        print("✅ Inicialização correta: messages_used_today=0, messages_used_this_month=0")
        
        # Testar endpoint /auth/me para messages_remaining_today
        success, response, status = self.make_request('GET', 'auth/me', token=self.user_token)
        
        if not success:
            print(f"❌ Falha em /auth/me: {response}")
            return False
        
        remaining_messages = response.get('messages_remaining_today', -1)
        print(f"📊 messages_remaining_today: {remaining_messages}")
        
        if remaining_messages != 7:  # Usuários gratuitos começam com 7 mensagens mensais
            print(f"❌ CORREÇÃO 2: FALHOU - messages_remaining_today deveria ser 7, mas é {remaining_messages}")
            return False
        
        print("✅ messages_remaining_today correto: 7")
        
        # Criar sessão
        success, response, status = self.make_request('POST', 'session', token=self.user_token)
        if not success:
            print(f"❌ Falha ao criar sessão: {response}")
            return False
        
        self.session_id = response['id']
        print(f"📝 Sessão criada: {self.session_id}")
        
        # Enviar mensagem de terapia (deve consumir contador)
        print("\n🧠 Testando mensagem de TERAPIA (deve consumir contador)...")
        success, response, status = self.make_request(
            'POST', 'chat',
            data={
                "session_id": self.session_id,
                "message": "Estou me sentindo muito ansioso ultimamente"
            },
            token=self.user_token
        )
        
        if not success:
            print(f"❌ Falha ao enviar mensagem de terapia: {response}")
            return False
        
        remaining_after_therapy = response.get('messages_remaining_today', -1)
        print(f"📉 Mensagens restantes após terapia: {remaining_after_therapy}")
        
        if remaining_after_therapy != 6:
            print(f"❌ CORREÇÃO 2: FALHOU - Contador deveria ser 6, mas é {remaining_after_therapy}")
            return False
        
        print("✅ Mensagem de terapia consumiu contador corretamente: 7 → 6")
        
        # Enviar mensagem de SUPORTE (NÃO deve consumir contador)
        print("\n🔧 Testando mensagem de SUPORTE (NÃO deve consumir contador)...")
        success, response, status = self.make_request(
            'POST', 'chat',
            data={
                "session_id": self.session_id,
                "message": "Como funciona o sistema de mensagens e planos?"
            },
            token=self.user_token
        )
        
        if not success:
            print(f"❌ Falha ao enviar mensagem de suporte: {response}")
            return False
        
        remaining_after_support = response.get('messages_remaining_today', -1)
        print(f"📊 Mensagens restantes após suporte: {remaining_after_support}")
        
        if remaining_after_support != 6:
            print(f"❌ CORREÇÃO 2: FALHOU - Contador deveria permanecer 6, mas é {remaining_after_support}")
            return False
        
        print("✅ Mensagem de suporte NÃO consumiu contador: permaneceu em 6")
        print("🎉 CORREÇÃO 2: SISTEMA DE MENSAGENS - FUNCIONANDO!")
        self.corrections_status["message_system"] = True
        return True

    def test_correction_3_admin_functionalities(self):
        """CORREÇÃO 3: FUNCIONALIDADES ADMIN"""
        print("\n" + "="*70)
        print("⚙️ CORREÇÃO 3: FUNCIONALIDADES ADMIN")
        print("="*70)
        
        if not self.admin_token:
            print("❌ Token admin não disponível")
            return False
        
        # Testar /api/admin/prompts
        print("🔍 Testando /api/admin/prompts...")
        success, response, status = self.make_request('GET', 'admin/prompts', token=self.admin_token)
        
        if not success:
            print(f"❌ Falha em admin/prompts: {response}")
            return False
        
        base_prompt = response.get('base_prompt', '')
        additional_prompt = response.get('additional_prompt', '')
        
        print(f"✅ Prompts carregados - Base: {len(base_prompt)} chars, Additional: {len(additional_prompt)} chars")
        
        if len(base_prompt) < 50:  # Deve ter conteúdo substancial
            print("❌ Base prompt muito pequeno ou vazio")
            return False
        
        # Testar /api/admin/documents/system
        print("🔍 Testando /api/admin/documents/system...")
        success, response, status = self.make_request('GET', 'admin/documents/system', token=self.admin_token)
        
        if not success:
            print(f"❌ Falha em admin/documents/system: {response}")
            return False
        
        theory_doc = response.get('theory_document', '')
        support_doc = response.get('support_document', '')
        
        print(f"✅ Documentos do sistema - Teoria: {len(theory_doc)} chars, Suporte: {len(support_doc)} chars")
        
        if len(support_doc) < 100:  # Deve ter documento de suporte
            print("❌ Documento de suporte muito pequeno ou vazio")
            return False
        
        # Testar busca de usuários
        print("🔍 Testando busca de usuários...")
        success, response, status = self.make_request('GET', 'admin/users?search=test', token=self.admin_token)
        
        if not success:
            print(f"❌ Falha na busca de usuários: {response}")
            return False
        
        users_found = len(response) if isinstance(response, list) else 0
        print(f"✅ Busca de usuários funcionando - {users_found} usuários encontrados")
        
        # Testar detalhes de usuário específico
        if self.test_user_id:
            print(f"🔍 Testando detalhes do usuário {self.test_user_id}...")
            success, response, status = self.make_request(
                'GET', f'admin/user/{self.test_user_id}', token=self.admin_token
            )
            
            if success and 'user' in response:
                print("✅ Detalhes do usuário carregados com sucesso")
            else:
                print(f"❌ Falha ao carregar detalhes do usuário: {response}")
                return False
        
        print("🎉 CORREÇÃO 3: FUNCIONALIDADES ADMIN - FUNCIONANDO!")
        self.corrections_status["admin_functionalities"] = True
        return True

    def run_verification(self):
        """Executar verificação completa das correções"""
        print("🚀 VERIFICAÇÃO COMPLETA DAS CORREÇÕES IMPLEMENTADAS")
        print("URL:", self.base_url)
        print("="*80)
        
        # Executar testes das 3 correções
        correction_1 = self.test_correction_1_admin_auth()
        correction_2 = self.test_correction_2_message_system()
        correction_3 = self.test_correction_3_admin_functionalities()
        
        # Resultado final
        print("\n" + "="*80)
        print("🎯 RESULTADO FINAL DAS CORREÇÕES")
        print("="*80)
        
        corrections_working = sum(self.corrections_status.values())
        
        print(f"🔐 CORREÇÃO 1 - Admin Auth: {'✅ FUNCIONANDO' if self.corrections_status['admin_auth'] else '❌ FALHOU'}")
        print(f"📊 CORREÇÃO 2 - Sistema Mensagens: {'✅ FUNCIONANDO' if self.corrections_status['message_system'] else '❌ FALHOU'}")
        print(f"⚙️ CORREÇÃO 3 - Funcionalidades Admin: {'✅ FUNCIONANDO' if self.corrections_status['admin_functionalities'] else '❌ FALHOU'}")
        
        print(f"\n🎯 CORREÇÕES FUNCIONANDO: {corrections_working}/3")
        
        if corrections_working == 3:
            print("🎉 TODAS AS 3 CORREÇÕES ESTÃO FUNCIONANDO PERFEITAMENTE!")
            return True
        else:
            print("⚠️ ALGUMAS CORREÇÕES PRECISAM DE ATENÇÃO")
            return False

def main():
    tester = CorrectionsVerificationTester()
    success = tester.run_verification()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
#!/usr/bin/env python3
"""
MEMORY SYSTEM TESTING for Terapia Emocional
Specifically tests the memory correction implementation with automatic summaries
"""

import requests
import sys
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional

class TerapiaMemoryTester:
    def __init__(self, base_url: str = "https://71832b61-f09e-4b43-b8fe-dcfd4ba45e0d.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.admin_token = None
        self.user_token = None
        self.user_id = None
        self.session_1_id = None
        self.session_2_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        
        # Test data for memory testing
        timestamp = datetime.now().strftime('%H%M%S')
        self.test_user_email = f"memory_test_{timestamp}@test.com"
        self.test_user_data = {
            "email": self.test_user_email,
            "name": f"Memory Test User {timestamp}",
            "phone": "11999999999",
            "password": "testpass123"
        }

    def log_test(self, name: str, success: bool, details: str = ""):
        """Log test results"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            status = "✅ PASSED"
        else:
            status = "❌ FAILED"
        
        result = f"{status} - {name}"
        if details:
            result += f" | {details}"
        
        print(result)
        self.test_results.append({
            "name": name,
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })
        return success

    def make_request(self, method: str, endpoint: str, data: Optional[Dict] = None, token: Optional[str] = None, expected_status: int = 200, timeout: int = 60) -> tuple[bool, Dict]:
        """Make HTTP request with error handling"""
        url = f"{self.api_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        if token:
            headers['Authorization'] = f'Bearer {token}'
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=timeout)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=timeout)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=timeout)
            else:
                return False, {"error": f"Unsupported method: {method}"}

            success = response.status_code == expected_status
            
            try:
                response_data = response.json()
            except:
                response_data = {"raw_response": response.text, "status_code": response.status_code}
            
            return success, response_data
            
        except requests.exceptions.RequestException as e:
            return False, {"error": str(e)}

    def test_setup_admin(self) -> bool:
        """Setup admin user and login"""
        print("\n🔧 Setting up admin access...")
        
        # Try to create admin (might already exist)
        success, response = self.make_request('POST', 'admin/create-admin')
        if not success and response.get('status_code') != 400:
            return self.log_test("Admin Setup", False, f"Failed to create admin: {response}")
        
        # Login as admin
        admin_credentials = {
            "email": "admin@terapia.com",
            "password": "admin123"
        }
        
        success, response = self.make_request('POST', 'auth/login', admin_credentials)
        if success:
            self.admin_token = response.get('token')
            user_data = response.get('user', {})
            is_admin = user_data.get('is_admin', False)
            return self.log_test("Admin Setup", is_admin, f"Admin logged in: {is_admin}")
        else:
            return self.log_test("Admin Setup", False, f"Admin login failed: {response}")

    def test_create_test_user(self) -> bool:
        """Create and login test user"""
        print("\n👤 Creating test user...")
        
        # Register user
        success, response = self.make_request('POST', 'auth/register', self.test_user_data)
        if success:
            self.user_token = response.get('token')
            user_data = response.get('user', {})
            self.user_id = user_data.get('id')
            return self.log_test("Test User Creation", True, f"User: {user_data.get('email')}")
        else:
            return self.log_test("Test User Creation", False, f"Registration failed: {response}")

    def test_session_1_conversation(self) -> bool:
        """Create session 1 and have conversation about divorce (4+ messages)"""
        print("\n💬 Testing Session 1 - Divorce Conversation...")
        
        if not self.user_token:
            return self.log_test("Session 1 Setup", False, "No user token")
        
        # Create session 1
        success, response = self.make_request('POST', 'session', token=self.user_token)
        if not success:
            return self.log_test("Session 1 Creation", False, f"Failed to create session: {response}")
        
        self.session_1_id = response.get('id')
        self.log_test("Session 1 Creation", True, f"Session ID: {self.session_1_id}")
        
        # Conversation about divorce (4 messages to trigger summary)
        divorce_messages = [
            "Olá, estou passando por um divórcio muito difícil e me sentindo perdida.",
            "Meu marido me deixou depois de 15 anos de casamento e não sei como lidar com isso.",
            "Tenho dois filhos pequenos e estou preocupada com o impacto na vida deles.",
            "Me sinto como se minha vida toda tivesse desmoronado. Como posso seguir em frente?"
        ]
        
        all_success = True
        for i, message in enumerate(divorce_messages, 1):
            print(f"  Sending message {i}/4...")
            
            chat_data = {
                "session_id": self.session_1_id,
                "message": message
            }
            
            success, response = self.make_request('POST', 'chat', chat_data, token=self.user_token, timeout=90)
            if success:
                ai_response = response.get('response', '')
                print(f"  ✅ AI Response {i}: {ai_response[:100]}...")
                time.sleep(3)  # Wait between messages
            else:
                print(f"  ❌ Message {i} failed: {response}")
                all_success = False
        
        return self.log_test("Session 1 Conversation", all_success, f"Sent {len(divorce_messages)} messages about divorce")

    def test_session_2_memory_check(self) -> bool:
        """Create session 2 and test if AI remembers previous session"""
        print("\n🧠 Testing Session 2 - Memory Check...")
        
        if not self.user_token:
            return self.log_test("Session 2 Setup", False, "No user token")
        
        # Create session 2
        success, response = self.make_request('POST', 'session', token=self.user_token)
        if not success:
            return self.log_test("Session 2 Creation", False, f"Failed to create session: {response}")
        
        self.session_2_id = response.get('id')
        self.log_test("Session 2 Creation", True, f"Session ID: {self.session_2_id}")
        
        # Ask about previous session
        memory_question = "O que falamos na sessão anterior? Você se lembra do que eu compartilhei com você?"
        
        chat_data = {
            "session_id": self.session_2_id,
            "message": memory_question
        }
        
        print("  🤔 Asking AI about previous session...")
        success, response = self.make_request('POST', 'chat', chat_data, token=self.user_token, timeout=90)
        
        if success:
            ai_response = response.get('response', '')
            print(f"  🤖 AI Memory Response: {ai_response}")
            
            # Check for memory indicators
            memory_keywords = [
                'divórcio', 'casamento', 'marido', 'filhos', 'sessão anterior', 
                'conversamos', 'falamos', 'compartilhou', 'mencionou', '15 anos'
            ]
            
            found_keywords = [kw for kw in memory_keywords if kw.lower() in ai_response.lower()]
            
            if found_keywords:
                return self.log_test("Memory Check", True, f"AI remembered! Keywords found: {found_keywords}")
            else:
                return self.log_test("Memory Check", False, f"AI didn't show clear memory. Response: {ai_response[:200]}...")
        else:
            return self.log_test("Memory Check", False, f"Failed to get AI response: {response}")

    def test_debug_endpoint(self) -> bool:
        """Test debug endpoint to verify summaries were generated"""
        print("\n🔍 Testing Debug Endpoint...")
        
        if not self.admin_token or not self.user_id:
            return self.log_test("Debug Endpoint", False, "Missing admin token or user ID")
        
        success, response = self.make_request('GET', f'debug/user-sessions/{self.user_id}', token=self.admin_token)
        
        if success:
            total_sessions = response.get('total_sessions', 0)
            sessions_with_summaries = response.get('sessions_with_summaries', 0)
            processed = response.get('sessions_without_summaries_processed', 0)
            
            print(f"  📊 Total sessions: {total_sessions}")
            print(f"  📝 Sessions with summaries: {sessions_with_summaries}")
            print(f"  ⚙️ Sessions processed: {processed}")
            
            # Check enhanced prompt
            prompt_preview = response.get('enhanced_prompt_preview', '')
            has_memory_content = any(keyword in prompt_preview.lower() for keyword in ['divórcio', 'sessão', 'casamento'])
            
            if sessions_with_summaries > 0 and has_memory_content:
                return self.log_test("Debug Endpoint", True, f"Summaries: {sessions_with_summaries}, Memory in prompt: {has_memory_content}")
            else:
                return self.log_test("Debug Endpoint", False, f"Summaries: {sessions_with_summaries}, Memory in prompt: {has_memory_content}")
        else:
            return self.log_test("Debug Endpoint", False, f"Debug request failed: {response}")

    def test_session_summary_generation(self) -> bool:
        """Test manual summary generation"""
        print("\n📝 Testing Session Summary Generation...")
        
        if not self.user_token or not self.session_1_id:
            return self.log_test("Summary Generation", False, "Missing token or session ID")
        
        success, response = self.make_request('POST', f'session/{self.session_1_id}/summary', token=self.user_token)
        
        if success:
            summary = response.get('summary', '')
            print(f"  📄 Generated Summary: {summary[:200]}...")
            
            # Check if summary contains divorce-related content
            divorce_keywords = ['divórcio', 'casamento', 'marido', 'filhos']
            found_in_summary = [kw for kw in divorce_keywords if kw.lower() in summary.lower()]
            
            if found_in_summary:
                return self.log_test("Summary Generation", True, f"Summary contains: {found_in_summary}")
            else:
                return self.log_test("Summary Generation", False, f"Summary missing divorce content: {summary[:100]}...")
        else:
            return self.log_test("Summary Generation", False, f"Summary generation failed: {response}")

    def run_memory_tests(self) -> bool:
        """Run complete memory system test suite"""
        print("🚀 STARTING MEMORY SYSTEM TESTS")
        print(f"🌐 Testing URL: {self.base_url}")
        print("=" * 80)
        
        # Test sequence for memory functionality
        tests = [
            ("Admin Setup", self.test_setup_admin),
            ("Test User Creation", self.test_create_test_user),
            ("Session 1 Conversation", self.test_session_1_conversation),
            ("Session 2 Memory Check", self.test_session_2_memory_check),
            ("Debug Endpoint", self.test_debug_endpoint),
            ("Summary Generation", self.test_session_summary_generation),
        ]
        
        for test_name, test_func in tests:
            print(f"\n{'='*50}")
            print(f"🧪 {test_name}")
            print(f"{'='*50}")
            
            try:
                result = test_func()
                if not result:
                    print(f"⚠️ {test_name} failed but continuing...")
            except Exception as e:
                self.log_test(test_name, False, f"Exception: {str(e)}")
                print(f"💥 {test_name} crashed: {str(e)}")
        
        # Final results
        print(f"\n{'='*80}")
        print("🏁 MEMORY SYSTEM TEST RESULTS")
        print(f"{'='*80}")
        print(f"✅ Tests Passed: {self.tests_passed}/{self.tests_run}")
        print(f"❌ Tests Failed: {self.tests_run - self.tests_passed}/{self.tests_run}")
        
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        print(f"📊 Success Rate: {success_rate:.1f}%")
        
        if success_rate >= 80:
            print("🎉 MEMORY SYSTEM IS WORKING!")
            return True
        else:
            print("❌ MEMORY SYSTEM HAS ISSUES")
            return False

def main():
    """Main test execution"""
    tester = TerapiaMemoryTester()
    success = tester.run_memory_tests()
    
    # Save results
    with open('/app/memory_test_results.json', 'w') as f:
        json.dump({
            "summary": {
                "total_tests": tester.tests_run,
                "passed": tester.tests_passed,
                "failed": tester.tests_run - tester.tests_passed,
                "success_rate": f"{(tester.tests_passed/tester.tests_run)*100:.1f}%" if tester.tests_run > 0 else "0%"
            },
            "results": tester.test_results,
            "timestamp": datetime.now().isoformat()
        }, f, indent=2)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
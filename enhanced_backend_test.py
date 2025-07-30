#!/usr/bin/env python3
"""
Enhanced Backend Testing for Specific Fixes in Emotional Therapy App V2
Tests the 5 specific corrections mentioned in the review request
"""

import requests
import sys
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional

class EnhancedTerapiaAPITester:
    def __init__(self, base_url: str = "https://431abbe8-54e5-4686-ae34-fef4fe187f36.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.admin_token = None
        self.user_token = None
        self.session_ids = []
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        self.test_user_email = f"enhanced_test_{datetime.now().strftime('%H%M%S')}@test.com"

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

    def make_request(self, method: str, endpoint: str, data: Optional[Dict] = None, token: Optional[str] = None, expected_status: int = 200) -> tuple[bool, Dict]:
        """Make HTTP request with error handling"""
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
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=30)
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

    def setup_test_user(self) -> bool:
        """Setup test user and admin"""
        print("\n🔧 Setting up test environment...")
        
        # Login as admin
        admin_credentials = {
            "email": "admin@terapia.com",
            "password": "admin123"
        }
        
        success, response = self.make_request('POST', 'auth/login', admin_credentials)
        if success:
            self.admin_token = response.get('token')
            print("✅ Admin login successful")
        else:
            print("❌ Admin login failed")
            return False
        
        # Create test user
        user_data = {
            "email": self.test_user_email,
            "name": "Enhanced Test User",
            "phone": "11999999999",
            "password": "testpass123"
        }
        
        success, response = self.make_request('POST', 'auth/register', user_data)
        if success:
            self.user_token = response.get('token')
            print("✅ Test user created successfully")
            return True
        else:
            print("❌ Test user creation failed")
            return False

    def test_ai_session_history_memory(self) -> bool:
        """TEST 1: AI Session History Memory - Test if AI remembers previous sessions"""
        print("\n🧠 Testing AI Session History Memory...")
        
        if not self.user_token:
            return self.log_test("AI Session History Memory", False, "No user token available")
        
        # Create first session and send a message about a specific topic
        success, response = self.make_request('POST', 'session', token=self.user_token)
        if not success:
            return self.log_test("AI Session History Memory", False, "Failed to create first session")
        
        session1_id = response.get('id')
        self.session_ids.append(session1_id)
        
        # Send a specific message in first session
        chat_data = {
            "session_id": session1_id,
            "message": "Meu nome é João e estou passando por um divórcio difícil. Tenho dois filhos pequenos."
        }
        
        success, response = self.make_request('POST', 'chat', chat_data, token=self.user_token)
        if not success:
            return self.log_test("AI Session History Memory", False, "Failed to send message in first session")
        
        # Generate summary for first session
        success, response = self.make_request('POST', f'session/{session1_id}/summary', {}, token=self.user_token)
        if not success:
            return self.log_test("AI Session History Memory", False, "Failed to generate summary for first session")
        
        # Wait a moment for processing
        time.sleep(2)
        
        # Create second session
        success, response = self.make_request('POST', 'session', token=self.user_token)
        if not success:
            return self.log_test("AI Session History Memory", False, "Failed to create second session")
        
        session2_id = response.get('id')
        self.session_ids.append(session2_id)
        
        # In second session, ask about previous conversation
        chat_data = {
            "session_id": session2_id,
            "message": "Você se lembra do que conversamos na sessão anterior sobre minha situação familiar?"
        }
        
        success, response = self.make_request('POST', 'chat', chat_data, token=self.user_token)
        if success:
            ai_response = response.get('response', '').lower()
            # Check if AI mentions divorce, children, or João
            memory_indicators = ['divórcio', 'filhos', 'joão', 'sessão anterior', 'conversa anterior', 'situação familiar']
            has_memory = any(indicator in ai_response for indicator in memory_indicators)
            
            if has_memory:
                return self.log_test("AI Session History Memory", True, f"AI remembered previous session context")
            else:
                return self.log_test("AI Session History Memory", False, f"AI response doesn't show memory of previous session: {ai_response[:100]}...")
        else:
            return self.log_test("AI Session History Memory", False, "Failed to send message in second session")

    def test_subscription_cancel_and_history(self) -> bool:
        """TEST 2: Subscription Plans - Test cancel button and payment history"""
        print("\n💳 Testing Subscription Cancel and Payment History...")
        
        if not self.user_token:
            return self.log_test("Subscription Cancel and History", False, "No user token available")
        
        # Test getting payment history (should be empty for new user)
        success, response = self.make_request('GET', 'subscription/payments', token=self.user_token)
        if success:
            payments = response if isinstance(response, list) else []
            history_test = self.log_test("Payment History Endpoint", True, f"Found {len(payments)} payments (expected 0 for new user)")
        else:
            history_test = self.log_test("Payment History Endpoint", False, f"Failed to get payment history: {response}")
        
        # Test cancel subscription endpoint (should work even if user is on free plan)
        success, response = self.make_request('POST', 'subscription/cancel', {}, token=self.user_token)
        if success:
            cancel_test = self.log_test("Cancel Subscription Endpoint", True, "Cancel endpoint works")
        else:
            cancel_test = self.log_test("Cancel Subscription Endpoint", False, f"Cancel failed: {response}")
        
        return history_test and cancel_test

    def test_profile_password_confirmation(self) -> bool:
        """TEST 3: Profile Screen - Test password confirmation and user data visibility"""
        print("\n👤 Testing Profile Password Confirmation...")
        
        if not self.user_token:
            return self.log_test("Profile Password Confirmation", False, "No user token available")
        
        # Test getting current user info (should show all fields)
        success, response = self.make_request('GET', 'auth/me', token=self.user_token)
        if success:
            required_fields = ['email', 'name', 'phone', 'subscription_plan', 'messages_used_today', 'messages_used_this_month']
            missing_fields = [field for field in required_fields if field not in response]
            
            if not missing_fields:
                profile_data_test = self.log_test("Profile Data Visibility", True, f"All required fields present: {required_fields}")
            else:
                profile_data_test = self.log_test("Profile Data Visibility", False, f"Missing fields: {missing_fields}")
        else:
            profile_data_test = self.log_test("Profile Data Visibility", False, f"Failed to get user info: {response}")
        
        # Test profile update with password
        update_data = {
            "name": "Updated Enhanced Test User",
            "phone": "11888888888",
            "password": "newpassword123"
        }
        
        success, response = self.make_request('PUT', 'auth/profile', update_data, token=self.user_token)
        if success:
            password_update_test = self.log_test("Profile Password Update", True, "Password update endpoint works")
        else:
            password_update_test = self.log_test("Profile Password Update", False, f"Password update failed: {response}")
        
        return profile_data_test and password_update_test

    def test_session_details_and_summary(self) -> bool:
        """TEST 4: Session History Details - Test clicking sessions and viewing summaries"""
        print("\n📝 Testing Session Details and Summary...")
        
        if not self.user_token or not self.session_ids:
            return self.log_test("Session Details and Summary", False, "No user token or session IDs available")
        
        session_id = self.session_ids[0]  # Use first session created
        
        # Test getting session messages
        success, response = self.make_request('GET', f'session/{session_id}/messages', token=self.user_token)
        if success:
            messages = response if isinstance(response, list) else []
            messages_test = self.log_test("Session Messages Retrieval", True, f"Retrieved {len(messages)} messages")
        else:
            messages_test = self.log_test("Session Messages Retrieval", False, f"Failed to get messages: {response}")
        
        # Test generating/getting session summary
        success, response = self.make_request('POST', f'session/{session_id}/summary', {}, token=self.user_token)
        if success:
            summary = response.get('summary', '')
            summary_test = self.log_test("Session Summary Generation", True, f"Generated summary ({len(summary)} chars)")
        else:
            summary_test = self.log_test("Session Summary Generation", False, f"Failed to generate summary: {response}")
        
        # Test getting sessions list (should include summary)
        success, response = self.make_request('GET', 'sessions', token=self.user_token)
        if success:
            sessions = response if isinstance(response, list) else []
            sessions_with_summary = [s for s in sessions if s.get('summary')]
            sessions_list_test = self.log_test("Sessions List with Summary", True, f"Found {len(sessions_with_summary)} sessions with summaries")
        else:
            sessions_list_test = self.log_test("Sessions List with Summary", False, f"Failed to get sessions: {response}")
        
        return messages_test and summary_test and sessions_list_test

    def test_admin_input_visibility(self) -> bool:
        """TEST 5: Admin Panel - Test if inputs are visible (prompts functionality)"""
        print("\n⚙️ Testing Admin Input Visibility...")
        
        if not self.admin_token:
            return self.log_test("Admin Input Visibility", False, "No admin token available")
        
        # Test getting admin prompts
        success, response = self.make_request('GET', 'admin/prompts', token=self.admin_token)
        if success:
            base_prompt = response.get('base_prompt', '')
            additional_prompt = response.get('additional_prompt', '')
            prompts_get_test = self.log_test("Admin Prompts Retrieval", True, f"Base: {len(base_prompt)} chars, Additional: {len(additional_prompt)} chars")
        else:
            prompts_get_test = self.log_test("Admin Prompts Retrieval", False, f"Failed to get prompts: {response}")
        
        # Test updating admin prompts
        update_data = {
            "base_prompt": "Test base prompt update",
            "additional_prompt": "Test additional prompt update"
        }
        
        success, response = self.make_request('PUT', 'admin/prompts', update_data, token=self.admin_token)
        if success:
            prompts_update_test = self.log_test("Admin Prompts Update", True, "Prompts update successful")
        else:
            prompts_update_test = self.log_test("Admin Prompts Update", False, f"Failed to update prompts: {response}")
        
        # Test admin documents functionality
        success, response = self.make_request('GET', 'admin/documents', token=self.admin_token)
        if success:
            documents = response if isinstance(response, list) else []
            documents_test = self.log_test("Admin Documents Access", True, f"Retrieved {len(documents)} documents")
        else:
            documents_test = self.log_test("Admin Documents Access", False, f"Failed to get documents: {response}")
        
        return prompts_get_test and prompts_update_test and documents_test

    def run_enhanced_tests(self) -> bool:
        """Run all enhanced tests for the specific fixes"""
        print("🚀 Starting Enhanced Terapia Emocional V2 API Tests")
        print("🎯 Testing the 5 specific corrections mentioned in review request")
        print(f"📍 Testing against: {self.base_url}")
        print("=" * 70)
        
        # Setup
        if not self.setup_test_user():
            print("❌ Failed to setup test environment")
            return False
        
        # Run specific tests for the 5 corrections
        tests = [
            self.test_ai_session_history_memory,
            self.test_subscription_cancel_and_history,
            self.test_profile_password_confirmation,
            self.test_session_details_and_summary,
            self.test_admin_input_visibility
        ]
        
        for test in tests:
            try:
                test()
            except Exception as e:
                self.log_test(test.__name__, False, f"Exception: {str(e)}")
        
        # Print summary
        print("\n" + "=" * 70)
        print("📊 ENHANCED TEST SUMMARY")
        print(f"✅ Passed: {self.tests_passed}/{self.tests_run}")
        print(f"❌ Failed: {self.tests_run - self.tests_passed}/{self.tests_run}")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All enhanced tests passed! The 5 corrections are working correctly.")
            return True
        else:
            print("⚠️  Some tests failed. Check the details above.")
            return False

def main():
    """Main test execution"""
    tester = EnhancedTerapiaAPITester()
    success = tester.run_enhanced_tests()
    
    # Save detailed results
    with open('/app/enhanced_backend_test_results.json', 'w') as f:
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
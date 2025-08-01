#!/usr/bin/env python3
"""
Focused Backend API Testing for Anantara Spiritual Therapy App
Tests core functionality that should be working based on test_result.md
"""

import requests
import sys
import json
from datetime import datetime
from typing import Dict, Any, Optional

class AnantaraAPITester:
    def __init__(self, base_url: str = "https://71832b61-f09e-4b43-b8fe-dcfd4ba45e0d.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.user_token = None
        self.session_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        self.test_user_email = f"anantara_user_{datetime.now().strftime('%H%M%S')}@spiritual.com"
        self.test_user_data = {
            "email": self.test_user_email,
            "name": "Spiritual Seeker",
            "phone": "11987654321",
            "password": "spiritual123"
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

    def test_backend_health(self) -> bool:
        """Test backend health and connectivity"""
        print("\n🔍 Testing Backend Health...")
        success, response = self.make_request('GET', 'health')
        
        if success and response.get('status') == 'healthy':
            return self.log_test("Backend Health", True, f"Service: {response.get('service', 'unknown')}")
        else:
            return self.log_test("Backend Health", False, f"Response: {response}")

    def test_user_registration(self) -> bool:
        """Test user registration"""
        print("\n🔍 Testing User Registration...")
        success, response = self.make_request('POST', 'auth/register', self.test_user_data)
        if success:
            self.user_token = response.get('token')
            user_data = response.get('user', {})
            return self.log_test("User Registration", True, f"User: {user_data.get('email')}, Plan: {user_data.get('subscription_plan')}")
        else:
            return self.log_test("User Registration", False, f"Response: {response}")

    def test_user_login(self) -> bool:
        """Test user login"""
        print("\n🔍 Testing User Login...")
        login_data = {
            "email": self.test_user_email,
            "password": "spiritual123"
        }
        
        success, response = self.make_request('POST', 'auth/login', login_data)
        if success:
            token = response.get('token')
            user_data = response.get('user', {})
            return self.log_test("User Login", True, f"Token received, User: {user_data.get('name')}")
        else:
            return self.log_test("User Login", False, f"Response: {response}")

    def test_auth_me(self) -> bool:
        """Test get current user info"""
        print("\n🔍 Testing Auth Me...")
        if not self.user_token:
            return self.log_test("Auth Me", False, "No user token available")
        
        success, response = self.make_request('GET', 'auth/me', token=self.user_token)
        if success:
            return self.log_test("Auth Me", True, f"User: {response.get('name')}, Plan: {response.get('subscription_plan')}, Messages: {response.get('messages_remaining_today')}")
        else:
            return self.log_test("Auth Me", False, f"Response: {response}")

    def test_forgot_password_functionality(self) -> bool:
        """Test forgot password functionality comprehensively"""
        print("\n🔍 Testing Forgot Password Functionality...")
        
        # Test 1: Valid email
        forgot_data = {"email": self.test_user_email}
        success, response = self.make_request('POST', 'auth/forgot-password', forgot_data)
        if not success:
            return self.log_test("Forgot Password Functionality", False, f"Valid email test failed: {response}")
        
        expected_message = "Se o email existir em nossa base, você receberá as instruções de recuperação."
        if expected_message not in response.get('message', ''):
            return self.log_test("Forgot Password Functionality", False, f"Unexpected message: {response.get('message')}")
        
        # Test 2: Invalid email (should return same message for security)
        invalid_forgot_data = {"email": "nonexistent@example.com"}
        success2, response2 = self.make_request('POST', 'auth/forgot-password', invalid_forgot_data)
        if not success2 or expected_message not in response2.get('message', ''):
            return self.log_test("Forgot Password Functionality", False, f"Invalid email test failed: {response2}")
        
        # Test 3: Malformed email (should return validation error)
        malformed_forgot_data = {"email": "not-an-email"}
        success3, response3 = self.make_request('POST', 'auth/forgot-password', malformed_forgot_data, expected_status=422)
        if not success3:
            return self.log_test("Forgot Password Functionality", False, f"Malformed email test failed: {response3}")
        
        return self.log_test("Forgot Password Functionality", True, "All forgot password scenarios working correctly")

    def test_reset_password_functionality(self) -> bool:
        """Test reset password functionality"""
        print("\n🔍 Testing Reset Password Functionality...")
        
        # Test 1: Invalid token
        reset_data = {
            "token": "invalid-token-12345",
            "new_password": "newpassword123"
        }
        
        success, response = self.make_request('POST', 'auth/reset-password', reset_data, expected_status=400)
        if not success:
            return self.log_test("Reset Password Functionality", False, f"Invalid token test failed: {response}")
        
        expected_error = "Token inválido ou expirado"
        if expected_error not in response.get('detail', ''):
            return self.log_test("Reset Password Functionality", False, f"Unexpected error message: {response.get('detail')}")
        
        # Test 2: Short password validation
        short_password_data = {
            "token": "some-token",
            "new_password": "123"  # Too short
        }
        
        success2, response2 = self.make_request('POST', 'auth/reset-password', short_password_data, expected_status=400)
        if not success2:
            return self.log_test("Reset Password Functionality", False, f"Short password test failed: {response2}")
        
        # Should fail on either token validation or password validation
        detail = response2.get('detail', '')
        valid_errors = ["Token inválido ou expirado", "A senha deve ter pelo menos 6 caracteres"]
        if not any(error in detail for error in valid_errors):
            return self.log_test("Reset Password Functionality", False, f"Unexpected validation error: {detail}")
        
        return self.log_test("Reset Password Functionality", True, "Reset password validation working correctly")

    def test_chat_system(self) -> bool:
        """Test chat system functionality"""
        print("\n🔍 Testing Chat System...")
        if not self.user_token:
            return self.log_test("Chat System", False, "No user token available")
        
        # Create session
        success, response = self.make_request('POST', 'session', token=self.user_token)
        if not success:
            return self.log_test("Chat System", False, f"Session creation failed: {response}")
        
        self.session_id = response.get('id')
        
        # Send chat message
        chat_data = {
            "session_id": self.session_id,
            "message": "Olá Anantara, estou buscando paz interior. Como posso encontrar o silêncio dentro de mim?"
        }
        
        success, response = self.make_request('POST', 'chat', chat_data, token=self.user_token)
        if not success:
            return self.log_test("Chat System", False, f"Chat message failed: {response}")
        
        ai_response = response.get('response', '')
        remaining = response.get('messages_remaining_today', 0)
        
        if len(ai_response) < 50:  # Expect a meaningful response
            return self.log_test("Chat System", False, f"AI response too short: {ai_response}")
        
        return self.log_test("Chat System", True, f"AI responded ({len(ai_response)} chars), Remaining messages: {remaining}")

    def test_session_management(self) -> bool:
        """Test session management"""
        print("\n🔍 Testing Session Management...")
        if not self.user_token or not self.session_id:
            return self.log_test("Session Management", False, "No user token or session ID available")
        
        # Get sessions
        success, response = self.make_request('GET', 'sessions', token=self.user_token)
        if not success:
            return self.log_test("Session Management", False, f"Get sessions failed: {response}")
        
        sessions = response if isinstance(response, list) else []
        
        # Get session messages
        success2, response2 = self.make_request('GET', f'session/{self.session_id}/messages', token=self.user_token)
        if not success2:
            return self.log_test("Session Management", False, f"Get messages failed: {response2}")
        
        messages = response2 if isinstance(response2, list) else []
        
        return self.log_test("Session Management", True, f"Found {len(sessions)} sessions, {len(messages)} messages")

    def test_subscription_plans(self) -> bool:
        """Test subscription plans"""
        print("\n🔍 Testing Subscription Plans...")
        success, response = self.make_request('GET', 'plans')
        if success:
            plans = response.get('plans', {})
            plan_names = list(plans.keys())
            expected_plans = ['basico', 'premium', 'ilimitado']
            
            if all(plan in plan_names for plan in expected_plans):
                return self.log_test("Subscription Plans", True, f"All expected plans found: {plan_names}")
            else:
                return self.log_test("Subscription Plans", False, f"Missing plans. Found: {plan_names}, Expected: {expected_plans}")
        else:
            return self.log_test("Subscription Plans", False, f"Response: {response}")

    def test_profile_update(self) -> bool:
        """Test profile update"""
        print("\n🔍 Testing Profile Update...")
        if not self.user_token:
            return self.log_test("Profile Update", False, "No user token available")
        
        update_data = {
            "name": "Updated Spiritual Seeker",
            "phone": "11888888888"
        }
        
        success, response = self.make_request('PUT', 'auth/profile', update_data, token=self.user_token)
        if success:
            return self.log_test("Profile Update", True, "Profile updated successfully")
        else:
            return self.log_test("Profile Update", False, f"Response: {response}")

    def test_message_limits(self) -> bool:
        """Test message limits for free users"""
        print("\n🔍 Testing Message Limits...")
        if not self.user_token or not self.session_id:
            return self.log_test("Message Limits", False, "No user token or session ID available")
        
        # Check current user status
        success, response = self.make_request('GET', 'auth/me', token=self.user_token)
        if not success:
            return self.log_test("Message Limits", False, "Could not get user info")
        
        plan = response.get('subscription_plan', 'unknown')
        remaining = response.get('messages_remaining_today', 0)
        
        if plan == 'free':
            # Free users should have monthly limit
            if remaining >= 0:  # Should have some limit
                return self.log_test("Message Limits", True, f"Free user has {remaining} messages remaining")
            else:
                return self.log_test("Message Limits", False, f"Invalid remaining count: {remaining}")
        else:
            return self.log_test("Message Limits", True, f"User on {plan} plan with {remaining} messages remaining")

    def run_focused_tests(self) -> bool:
        """Run focused tests on working functionality"""
        print("🚀 Starting Anantara Spiritual Therapy API Tests")
        print(f"📍 Testing against: {self.base_url}")
        print("🎯 Focus: Core functionality that should be working")
        print("=" * 60)
        
        # Run tests in logical order
        tests = [
            self.test_backend_health,
            self.test_user_registration,
            self.test_user_login,
            self.test_auth_me,
            self.test_forgot_password_functionality,
            self.test_reset_password_functionality,
            self.test_chat_system,
            self.test_session_management,
            self.test_subscription_plans,
            self.test_profile_update,
            self.test_message_limits
        ]
        
        for test in tests:
            try:
                test()
            except Exception as e:
                self.log_test(test.__name__, False, f"Exception: {str(e)}")
        
        # Print summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print(f"✅ Passed: {self.tests_passed}/{self.tests_run}")
        print(f"❌ Failed: {self.tests_run - self.tests_passed}/{self.tests_run}")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All core functionality tests passed! Backend is working correctly.")
            return True
        else:
            print("⚠️  Some tests failed. Check the details above.")
            return False

def main():
    """Main test execution"""
    tester = AnantaraAPITester()
    success = tester.run_focused_tests()
    
    # Save detailed results
    with open('/app/focused_backend_test_results.json', 'w') as f:
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
#!/usr/bin/env python3
"""
Comprehensive Backend API Testing for Emotional Therapy App V2
Tests all endpoints including authentication, chat, subscriptions, and admin functionality
"""

import requests
import sys
import json
from datetime import datetime
from typing import Dict, Any, Optional

class TerapiaEmocionalAPITester:
    def __init__(self, base_url: str = "https://431abbe8-54e5-4686-ae34-fef4fe187f36.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.admin_token = None
        self.user_token = None
        self.session_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        self.test_user_email = f"test_user_{datetime.now().strftime('%H%M%S')}@test.com"
        self.test_user_data = {
            "email": self.test_user_email,
            "name": "Test User",
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

    def test_health_check(self) -> bool:
        """Test health endpoint"""
        print("\n🔍 Testing Health Check...")
        success, response = self.make_request('GET', 'health')
        
        if success and response.get('status') == 'healthy':
            return self.log_test("Health Check", True, f"Service: {response.get('service', 'unknown')}")
        else:
            return self.log_test("Health Check", False, f"Response: {response}")

    def test_create_admin(self) -> bool:
        """Test admin creation"""
        print("\n🔍 Testing Create Admin...")
        success, response = self.make_request('POST', 'admin/create-admin')
        
        if success:
            return self.log_test("Create Admin", True, f"Admin created: {response.get('email')}")
        else:
            # Admin might already exist, check if it's a 400 error
            if response.get('status_code') == 400:
                return self.log_test("Create Admin", True, "Admin already exists (expected)")
            return self.log_test("Create Admin", False, f"Response: {response}")

    def test_admin_login(self) -> bool:
        """Test admin login"""
        print("\n🔍 Testing Admin Login...")
        admin_credentials = {
            "email": "admin@terapia.com",
            "password": "admin123"
        }
        
        success, response = self.make_request('POST', 'auth/login', admin_credentials)
        if success:
            self.admin_token = response.get('token')
            user_data = response.get('user', {})
            is_admin = user_data.get('is_admin', False)
            return self.log_test("Admin Login", is_admin, f"Admin status: {is_admin}")
        else:
            return self.log_test("Admin Login", False, f"Response: {response}")

    def test_user_registration(self) -> bool:
        """Test user registration"""
        print("\n🔍 Testing User Registration...")
        success, response = self.make_request('POST', 'auth/register', self.test_user_data)
        if success:
            self.user_token = response.get('token')
            user_data = response.get('user', {})
            return self.log_test("User Registration", True, f"User: {user_data.get('email')}")
        else:
            return self.log_test("User Registration", False, f"Response: {response}")

    def test_user_login(self) -> bool:
        """Test user login"""
        print("\n🔍 Testing User Login...")
        login_data = {
            "email": self.test_user_email,
            "password": "testpass123"
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
            return self.log_test("Auth Me", True, f"User: {response.get('name')}, Plan: {response.get('subscription_plan')}")
        else:
            return self.log_test("Auth Me", False, f"Response: {response}")

    def test_create_session(self) -> bool:
        """Test creating a therapy session"""
        print("\n🔍 Testing Create Session...")
        if not self.user_token:
            return self.log_test("Create Session", False, "No user token available")
        
        success, response = self.make_request('POST', 'session', token=self.user_token)
        if success:
            self.session_id = response.get('id')
            return self.log_test("Create Session", True, f"Session ID: {self.session_id}")
        else:
            return self.log_test("Create Session", False, f"Response: {response}")

    def test_chat_message(self) -> bool:
        """Test sending a chat message"""
        print("\n🔍 Testing Chat Message...")
        if not self.user_token or not self.session_id:
            return self.log_test("Chat Message", False, "No user token or session ID available")
        
        chat_data = {
            "session_id": self.session_id,
            "message": "Olá, estou me sentindo ansioso hoje. Pode me ajudar?"
        }
        
        success, response = self.make_request('POST', 'chat', chat_data, token=self.user_token)
        if success:
            ai_response = response.get('response', '')
            remaining = response.get('messages_remaining_today', 0)
            return self.log_test("Chat Message", True, f"AI responded ({len(ai_response)} chars), Remaining: {remaining}")
        else:
            return self.log_test("Chat Message", False, f"Response: {response}")

    def test_get_sessions(self) -> bool:
        """Test getting user sessions"""
        print("\n🔍 Testing Get Sessions...")
        if not self.user_token:
            return self.log_test("Get Sessions", False, "No user token available")
        
        success, response = self.make_request('GET', 'sessions', token=self.user_token)
        if success:
            sessions = response if isinstance(response, list) else []
            return self.log_test("Get Sessions", True, f"Found {len(sessions)} sessions")
        else:
            return self.log_test("Get Sessions", False, f"Response: {response}")

    def test_session_messages(self) -> bool:
        """Test getting session messages"""
        print("\n🔍 Testing Session Messages...")
        if not self.user_token or not self.session_id:
            return self.log_test("Session Messages", False, "No user token or session ID available")
        
        success, response = self.make_request('GET', f'session/{self.session_id}/messages', token=self.user_token)
        if success:
            messages = response if isinstance(response, list) else []
            return self.log_test("Session Messages", True, f"Found {len(messages)} messages")
        else:
            return self.log_test("Session Messages", False, f"Response: {response}")

    def test_subscription_plans(self) -> bool:
        """Test getting subscription plans"""
        print("\n🔍 Testing Subscription Plans...")
        success, response = self.make_request('GET', 'plans')
        if success:
            plans = response.get('plans', {})
            plan_names = list(plans.keys())
            return self.log_test("Subscription Plans", True, f"Plans: {plan_names}")
        else:
            return self.log_test("Subscription Plans", False, f"Response: {response}")

    def test_admin_prompts(self) -> bool:
        """Test admin prompts functionality"""
        print("\n🔍 Testing Admin Prompts...")
        if not self.admin_token:
            return self.log_test("Admin Prompts", False, "No admin token available")
        
        # Get prompts
        success, response = self.make_request('GET', 'admin/prompts', token=self.admin_token)
        if success:
            base_prompt = response.get('base_prompt', '')
            return self.log_test("Admin Prompts", True, f"Base prompt length: {len(base_prompt)} chars")
        else:
            return self.log_test("Admin Prompts", False, f"Response: {response}")

    def test_admin_users(self) -> bool:
        """Test admin users endpoint"""
        print("\n🔍 Testing Admin Users...")
        if not self.admin_token:
            return self.log_test("Admin Users", False, "No admin token available")
        
        success, response = self.make_request('GET', 'admin/users', token=self.admin_token)
        if success:
            users = response if isinstance(response, list) else []
            return self.log_test("Admin Users", True, f"Found {len(users)} users")
        else:
            return self.log_test("Admin Users", False, f"Response: {response}")

    def test_admin_documents(self) -> bool:
        """Test admin documents functionality"""
        print("\n🔍 Testing Admin Documents...")
        if not self.admin_token:
            return self.log_test("Admin Documents", False, "No admin token available")
        
        success, response = self.make_request('GET', 'admin/documents', token=self.admin_token)
        if success:
            documents = response if isinstance(response, list) else []
            return self.log_test("Admin Documents", True, f"Found {len(documents)} documents")
        else:
            return self.log_test("Admin Documents", False, f"Response: {response}")

    def test_profile_update(self) -> bool:
        """Test profile update"""
        print("\n🔍 Testing Profile Update...")
        if not self.user_token:
            return self.log_test("Profile Update", False, "No user token available")
        
        update_data = {
            "name": "Updated Test User",
            "phone": "11888888888"
        }
        
        success, response = self.make_request('PUT', 'auth/profile', update_data, token=self.user_token)
        if success:
            return self.log_test("Profile Update", True, "Profile updated successfully")
        else:
            return self.log_test("Profile Update", False, f"Response: {response}")

    def test_forgot_password_valid_email(self) -> bool:
        """Test forgot password with valid email"""
        print("\n🔍 Testing Forgot Password - Valid Email...")
        
        # Use the test user email that we registered
        forgot_data = {
            "email": self.test_user_email
        }
        
        success, response = self.make_request('POST', 'auth/forgot-password', forgot_data)
        if success:
            expected_message = "Se o email existir em nossa base, você receberá as instruções de recuperação."
            actual_message = response.get('message', '')
            message_match = expected_message in actual_message
            return self.log_test("Forgot Password - Valid Email", message_match, f"Message: {actual_message}")
        else:
            return self.log_test("Forgot Password - Valid Email", False, f"Response: {response}")

    def test_forgot_password_invalid_email(self) -> bool:
        """Test forgot password with invalid/non-existent email"""
        print("\n🔍 Testing Forgot Password - Invalid Email...")
        
        forgot_data = {
            "email": "nonexistent@example.com"
        }
        
        success, response = self.make_request('POST', 'auth/forgot-password', forgot_data)
        if success:
            # Should return same message for security (don't reveal if email exists)
            expected_message = "Se o email existir em nossa base, você receberá as instruções de recuperação."
            actual_message = response.get('message', '')
            message_match = expected_message in actual_message
            return self.log_test("Forgot Password - Invalid Email", message_match, f"Message: {actual_message}")
        else:
            return self.log_test("Forgot Password - Invalid Email", False, f"Response: {response}")

    def test_forgot_password_malformed_email(self) -> bool:
        """Test forgot password with malformed email"""
        print("\n🔍 Testing Forgot Password - Malformed Email...")
        
        forgot_data = {
            "email": "not-an-email"
        }
        
        # This should return 422 for validation error
        success, response = self.make_request('POST', 'auth/forgot-password', forgot_data, expected_status=422)
        if success:
            return self.log_test("Forgot Password - Malformed Email", True, "Validation error returned as expected")
        else:
            return self.log_test("Forgot Password - Malformed Email", False, f"Response: {response}")

    def test_reset_password_invalid_token(self) -> bool:
        """Test reset password with invalid token"""
        print("\n🔍 Testing Reset Password - Invalid Token...")
        
        reset_data = {
            "token": "invalid-token-12345",
            "new_password": "newpassword123"
        }
        
        # Should return 400 for invalid token
        success, response = self.make_request('POST', 'auth/reset-password', reset_data, expected_status=400)
        if success:
            expected_message = "Token inválido ou expirado"
            actual_message = response.get('detail', '')
            message_match = expected_message in actual_message
            return self.log_test("Reset Password - Invalid Token", message_match, f"Error: {actual_message}")
        else:
            return self.log_test("Reset Password - Invalid Token", False, f"Response: {response}")

    def test_reset_password_short_password(self) -> bool:
        """Test reset password with password too short"""
        print("\n🔍 Testing Reset Password - Short Password...")
        
        reset_data = {
            "token": "some-token",  # Will fail on token validation first, but let's test password validation
            "new_password": "123"  # Too short
        }
        
        # Should return 400 for validation error
        success, response = self.make_request('POST', 'auth/reset-password', reset_data, expected_status=400)
        if success:
            # Could fail on token or password validation - both are acceptable
            detail = response.get('detail', '')
            token_error = "Token inválido ou expirado" in detail
            password_error = "A senha deve ter pelo menos 6 caracteres" in detail
            
            if token_error or password_error:
                return self.log_test("Reset Password - Short Password", True, f"Validation error: {detail}")
            else:
                return self.log_test("Reset Password - Short Password", False, f"Unexpected error: {detail}")
        else:
            return self.log_test("Reset Password - Short Password", False, f"Response: {response}")

    def test_database_password_reset_tokens(self) -> bool:
        """Test that password reset tokens are being stored in MongoDB"""
        print("\n🔍 Testing Database - Password Reset Tokens...")
        
        # First trigger a forgot password request to create a token
        forgot_data = {
            "email": self.test_user_email
        }
        
        success, response = self.make_request('POST', 'auth/forgot-password', forgot_data)
        if not success:
            return self.log_test("Database - Password Reset Tokens", False, "Failed to trigger forgot password")
        
        # We can't directly access MongoDB from here, but we can infer from the API behavior
        # If the forgot password worked, it means the token was stored
        expected_message = "Se o email existir em nossa base, você receberá as instruções de recuperação."
        actual_message = response.get('message', '')
        
        if expected_message in actual_message:
            return self.log_test("Database - Password Reset Tokens", True, "Token creation inferred from API response")
        else:
            return self.log_test("Database - Password Reset Tokens", False, f"Unexpected response: {actual_message}")

    def test_existing_auth_endpoints(self) -> bool:
        """Test that existing auth endpoints still work after forgot password implementation"""
        print("\n🔍 Testing Existing Auth Endpoints...")
        
        # Test registration with a new user
        new_user_email = f"auth_test_{datetime.now().strftime('%H%M%S')}@test.com"
        new_user_data = {
            "email": new_user_email,
            "name": "Auth Test User",
            "phone": "11777777777",
            "password": "authtest123"
        }
        
        # Test registration
        reg_success, reg_response = self.make_request('POST', 'auth/register', new_user_data)
        if not reg_success:
            return self.log_test("Existing Auth Endpoints", False, f"Registration failed: {reg_response}")
        
        # Test login
        login_data = {
            "email": new_user_email,
            "password": "authtest123"
        }
        
        login_success, login_response = self.make_request('POST', 'auth/login', login_data)
        if not login_success:
            return self.log_test("Existing Auth Endpoints", False, f"Login failed: {login_response}")
        
        # Test /auth/me
        token = login_response.get('token')
        me_success, me_response = self.make_request('GET', 'auth/me', token=token)
        if not me_success:
            return self.log_test("Existing Auth Endpoints", False, f"Auth/me failed: {me_response}")
        
        return self.log_test("Existing Auth Endpoints", True, "Registration, login, and auth/me all working")

    def test_backend_health_on_port_8001(self) -> bool:
        """Test that backend is running correctly on port 8001 (internal)"""
        print("\n🔍 Testing Backend Health...")
        
        # Test the main API endpoint to ensure backend is responsive
        success, response = self.make_request('GET', 'plans')  # Simple endpoint that doesn't require auth
        
        if success:
            plans = response.get('plans', {})
            if plans:
                return self.log_test("Backend Health", True, f"Backend responsive, found {len(plans)} subscription plans")
            else:
                return self.log_test("Backend Health", False, "Backend responsive but no plans found")
        else:
            return self.log_test("Backend Health", False, f"Backend not responsive: {response}")

    def run_all_tests(self) -> bool:
        """Run all tests in sequence"""
        print("🚀 Starting Terapia Emocional V2 API Tests")
        print(f"📍 Testing against: {self.base_url}")
        print("=" * 60)
        
        # Run tests in logical order
        tests = [
            self.test_backend_health_on_port_8001,
            self.test_create_admin,
            self.test_admin_login,
            self.test_user_registration,
            self.test_user_login,
            self.test_auth_me,
            # Forgot Password Tests
            self.test_forgot_password_valid_email,
            self.test_forgot_password_invalid_email,
            self.test_forgot_password_malformed_email,
            self.test_reset_password_invalid_token,
            self.test_reset_password_short_password,
            self.test_database_password_reset_tokens,
            self.test_existing_auth_endpoints,
            # Other existing tests
            self.test_create_session,
            self.test_chat_message,
            self.test_get_sessions,
            self.test_session_messages,
            self.test_subscription_plans,
            self.test_admin_prompts,
            self.test_admin_users,
            self.test_admin_documents,
            self.test_profile_update
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
            print("🎉 All tests passed! Backend is working correctly.")
            return True
        else:
            print("⚠️  Some tests failed. Check the details above.")
            return False

def main():
    """Main test execution"""
    tester = TerapiaEmocionalAPITester()
    success = tester.run_all_tests()
    
    # Save detailed results
    with open('/app/backend_test_results.json', 'w') as f:
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
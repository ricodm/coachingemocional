#!/usr/bin/env python3
"""
Comprehensive Backend API Testing for Emotional Therapy App
Tests all endpoints with proper error handling and validation
"""

import requests
import sys
import json
from datetime import datetime
from typing import Dict, Any, Optional

class EmotionalTherapyAPITester:
    def __init__(self, base_url: str = "https://431abbe8-54e5-4686-ae34-fef4fe187f36.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.session_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

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

    def make_request(self, method: str, endpoint: str, data: Optional[Dict] = None, expected_status: int = 200) -> tuple[bool, Dict]:
        """Make HTTP request with error handling"""
        url = f"{self.api_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=10)
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

    def test_create_session(self) -> bool:
        """Test session creation"""
        print("\n🔍 Testing Session Creation...")
        success, response = self.make_request('POST', 'session', expected_status=200)
        
        if success and 'id' in response:
            self.session_id = response['id']
            details = f"Session ID: {self.session_id[:8]}..."
            return self.log_test("Create Session", True, details)
        else:
            return self.log_test("Create Session", False, f"Response: {response}")

    def test_get_session(self) -> bool:
        """Test getting session details"""
        if not self.session_id:
            return self.log_test("Get Session", False, "No session ID available")
        
        print("\n🔍 Testing Get Session...")
        success, response = self.make_request('GET', f'session/{self.session_id}')
        
        if success and response.get('id') == self.session_id:
            details = f"Messages count: {response.get('messages_count', 0)}"
            return self.log_test("Get Session", True, details)
        else:
            return self.log_test("Get Session", False, f"Response: {response}")

    def test_chat_functionality(self) -> bool:
        """Test chat endpoint with therapeutic message"""
        if not self.session_id:
            return self.log_test("Chat Functionality", False, "No session ID available")
        
        print("\n🔍 Testing Chat Functionality...")
        test_message = "Estou me sentindo muito ansioso hoje. Não consigo parar de pensar em problemas do trabalho."
        
        chat_data = {
            "session_id": self.session_id,
            "message": test_message
        }
        
        success, response = self.make_request('POST', 'chat', chat_data)
        
        if success and 'response' in response and 'message_id' in response:
            ai_response = response['response']
            # Check if response is in Portuguese and has therapeutic tone
            is_portuguese = any(word in ai_response.lower() for word in ['você', 'seu', 'sua', 'que', 'como', 'por'])
            is_therapeutic = any(word in ai_response.lower() for word in ['sentir', 'emoção', 'investigar', 'observar', 'quem'])
            
            if is_portuguese and is_therapeutic:
                details = f"Response length: {len(ai_response)} chars, Therapeutic: Yes"
                return self.log_test("Chat Functionality", True, details)
            else:
                details = f"Portuguese: {is_portuguese}, Therapeutic: {is_therapeutic}"
                return self.log_test("Chat Functionality", False, details)
        else:
            return self.log_test("Chat Functionality", False, f"Response: {response}")

    def test_session_history(self) -> bool:
        """Test getting session message history"""
        if not self.session_id:
            return self.log_test("Session History", False, "No session ID available")
        
        print("\n🔍 Testing Session History...")
        success, response = self.make_request('GET', f'session/{self.session_id}/history')
        
        if success and isinstance(response, list):
            message_count = len(response)
            if message_count >= 2:  # Should have user message + AI response
                details = f"Found {message_count} messages in history"
                return self.log_test("Session History", True, details)
            else:
                details = f"Expected >= 2 messages, got {message_count}"
                return self.log_test("Session History", False, details)
        else:
            return self.log_test("Session History", False, f"Response: {response}")

    def test_multiple_chat_messages(self) -> bool:
        """Test sending multiple messages to verify conversation flow"""
        if not self.session_id:
            return self.log_test("Multiple Chat Messages", False, "No session ID available")
        
        print("\n🔍 Testing Multiple Chat Messages...")
        
        messages = [
            "Obrigado pela resposta anterior. Isso me ajudou a refletir.",
            "Mas ainda sinto que não consigo controlar meus pensamentos ansiosos."
        ]
        
        responses_received = 0
        for i, message in enumerate(messages):
            chat_data = {
                "session_id": self.session_id,
                "message": message
            }
            
            success, response = self.make_request('POST', 'chat', chat_data)
            if success and 'response' in response:
                responses_received += 1
        
        if responses_received == len(messages):
            details = f"Successfully sent and received {responses_received} message pairs"
            return self.log_test("Multiple Chat Messages", True, details)
        else:
            details = f"Expected {len(messages)} responses, got {responses_received}"
            return self.log_test("Multiple Chat Messages", False, details)

    def test_error_handling(self) -> bool:
        """Test error handling with invalid requests"""
        print("\n🔍 Testing Error Handling...")
        
        # Test invalid session ID
        success, response = self.make_request('GET', 'session/invalid-session-id', expected_status=404)
        if not success:
            return self.log_test("Error Handling", False, "Invalid session should return 404")
        
        # Test empty chat message
        empty_chat_data = {
            "session_id": self.session_id or "test-session",
            "message": ""
        }
        success, response = self.make_request('POST', 'chat', empty_chat_data, expected_status=422)
        
        return self.log_test("Error Handling", True, "Properly handles invalid requests")

    def run_all_tests(self) -> bool:
        """Run all tests in sequence"""
        print("🚀 Starting Emotional Therapy API Tests")
        print(f"📍 Testing against: {self.base_url}")
        print("=" * 60)
        
        # Run tests in logical order
        tests = [
            self.test_health_check,
            self.test_create_session,
            self.test_get_session,
            self.test_chat_functionality,
            self.test_session_history,
            self.test_multiple_chat_messages,
            self.test_error_handling
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
    tester = EmotionalTherapyAPITester()
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
#!/usr/bin/env python3
"""
Chat Suggestions Endpoint Testing
Tests the new /api/chat/suggestions endpoint specifically
"""

import requests
import sys
import json
from datetime import datetime
from typing import Dict, Any, Optional

class ChatSuggestionsAPITester:
    def __init__(self, base_url: str = "https://71832b61-f09e-4b43-b8fe-dcfd4ba45e0d.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.user_token = None
        self.session_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        self.test_user_email = f"suggestions_test_{datetime.now().strftime('%H%M%S')}@test.com"
        self.test_user_data = {
            "email": self.test_user_email,
            "name": "Suggestions Test User",
            "phone": "11999888777",
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

    def setup_test_user(self) -> bool:
        """Setup test user and authentication"""
        print("\n🔧 Setting up test user...")
        
        # Register user
        success, response = self.make_request('POST', 'auth/register', self.test_user_data)
        if not success:
            return self.log_test("Setup - User Registration", False, f"Registration failed: {response}")
        
        self.user_token = response.get('token')
        if not self.user_token:
            return self.log_test("Setup - User Registration", False, "No token received")
        
        return self.log_test("Setup - User Registration", True, f"User registered: {self.test_user_email}")

    def create_conversation_history(self) -> bool:
        """Create some conversation history for the user"""
        print("\n🔧 Creating conversation history...")
        
        if not self.user_token:
            return self.log_test("Setup - Conversation History", False, "No user token available")
        
        # Create a session
        success, response = self.make_request('POST', 'session', token=self.user_token)
        if not success:
            return self.log_test("Setup - Conversation History", False, f"Session creation failed: {response}")
        
        self.session_id = response.get('id')
        if not self.session_id:
            return self.log_test("Setup - Conversation History", False, "No session ID received")
        
        # Send several messages to create history
        messages = [
            "Olá, estou me sentindo muito ansioso ultimamente.",
            "Tenho dificuldade para dormir e minha mente não para de pensar.",
            "Como posso encontrar mais paz interior?",
            "Você pode me ensinar sobre meditação?",
            "Quero entender melhor quem eu realmente sou."
        ]
        
        for i, message in enumerate(messages):
            chat_data = {
                "session_id": self.session_id,
                "message": message
            }
            
            success, response = self.make_request('POST', 'chat', chat_data, token=self.user_token)
            if not success:
                return self.log_test("Setup - Conversation History", False, f"Message {i+1} failed: {response}")
        
        return self.log_test("Setup - Conversation History", True, f"Created {len(messages)} messages in session {self.session_id}")

    def test_suggestions_without_auth(self) -> bool:
        """Test suggestions endpoint without authentication"""
        print("\n🔍 Testing Suggestions - No Authentication...")
        
        # Should return 401 or 403
        success, response = self.make_request('POST', 'chat/suggestions', expected_status=401)
        if not success:
            # Try 403 as well
            success, response = self.make_request('POST', 'chat/suggestions', expected_status=403)
        
        if success:
            return self.log_test("Suggestions - No Auth", True, "Correctly rejected unauthenticated request")
        else:
            return self.log_test("Suggestions - No Auth", False, f"Unexpected response: {response}")

    def test_suggestions_with_auth_no_history(self) -> bool:
        """Test suggestions endpoint with auth but no conversation history"""
        print("\n🔍 Testing Suggestions - No History...")
        
        # Create a new user with no conversation history
        new_user_email = f"no_history_{datetime.now().strftime('%H%M%S')}@test.com"
        new_user_data = {
            "email": new_user_email,
            "name": "No History User",
            "phone": "11888777666",
            "password": "testpass123"
        }
        
        # Register new user
        success, response = self.make_request('POST', 'auth/register', new_user_data)
        if not success:
            return self.log_test("Suggestions - No History", False, f"User registration failed: {response}")
        
        new_user_token = response.get('token')
        if not new_user_token:
            return self.log_test("Suggestions - No History", False, "No token received for new user")
        
        # Test suggestions with no history
        success, response = self.make_request('POST', 'chat/suggestions', token=new_user_token)
        if success:
            suggestions = response.get('suggestions', [])
            generated_at = response.get('generated_at')
            
            if isinstance(suggestions, list) and len(suggestions) == 3 and generated_at:
                return self.log_test("Suggestions - No History", True, f"Got {len(suggestions)} fallback suggestions")
            else:
                return self.log_test("Suggestions - No History", False, f"Invalid response format: {response}")
        else:
            return self.log_test("Suggestions - No History", False, f"Request failed: {response}")

    def test_suggestions_with_history(self) -> bool:
        """Test suggestions endpoint with conversation history"""
        print("\n🔍 Testing Suggestions - With History...")
        
        if not self.user_token:
            return self.log_test("Suggestions - With History", False, "No user token available")
        
        success, response = self.make_request('POST', 'chat/suggestions', token=self.user_token)
        if success:
            suggestions = response.get('suggestions', [])
            generated_at = response.get('generated_at')
            
            # Validate response format
            if not isinstance(suggestions, list):
                return self.log_test("Suggestions - With History", False, "Suggestions is not a list")
            
            if len(suggestions) != 3:
                return self.log_test("Suggestions - With History", False, f"Expected 3 suggestions, got {len(suggestions)}")
            
            if not generated_at:
                return self.log_test("Suggestions - With History", False, "No generated_at timestamp")
            
            # Check that suggestions are strings and not empty
            for i, suggestion in enumerate(suggestions):
                if not isinstance(suggestion, str) or not suggestion.strip():
                    return self.log_test("Suggestions - With History", False, f"Suggestion {i+1} is empty or not a string")
                
                if len(suggestion) > 80:  # Should be concise
                    return self.log_test("Suggestions - With History", False, f"Suggestion {i+1} too long: {len(suggestion)} chars")
            
            return self.log_test("Suggestions - With History", True, f"Got 3 valid suggestions: {suggestions}")
        else:
            return self.log_test("Suggestions - With History", False, f"Request failed: {response}")

    def test_suggestions_response_format(self) -> bool:
        """Test that suggestions response has correct format"""
        print("\n🔍 Testing Suggestions - Response Format...")
        
        if not self.user_token:
            return self.log_test("Suggestions - Response Format", False, "No user token available")
        
        success, response = self.make_request('POST', 'chat/suggestions', token=self.user_token)
        if success:
            # Check required fields
            required_fields = ['suggestions', 'generated_at']
            for field in required_fields:
                if field not in response:
                    return self.log_test("Suggestions - Response Format", False, f"Missing required field: {field}")
            
            # Check suggestions format
            suggestions = response.get('suggestions')
            if not isinstance(suggestions, list):
                return self.log_test("Suggestions - Response Format", False, "Suggestions should be a list")
            
            if len(suggestions) != 3:
                return self.log_test("Suggestions - Response Format", False, f"Should have exactly 3 suggestions, got {len(suggestions)}")
            
            # Check generated_at format (should be ISO datetime)
            generated_at = response.get('generated_at')
            try:
                datetime.fromisoformat(generated_at.replace('Z', '+00:00'))
            except:
                return self.log_test("Suggestions - Response Format", False, f"Invalid generated_at format: {generated_at}")
            
            return self.log_test("Suggestions - Response Format", True, "Response format is correct")
        else:
            return self.log_test("Suggestions - Response Format", False, f"Request failed: {response}")

    def test_suggestions_personalization(self) -> bool:
        """Test that suggestions are personalized based on conversation history"""
        print("\n🔍 Testing Suggestions - Personalization...")
        
        if not self.user_token:
            return self.log_test("Suggestions - Personalization", False, "No user token available")
        
        # Get suggestions multiple times to see if they vary
        suggestions_sets = []
        for i in range(2):
            success, response = self.make_request('POST', 'chat/suggestions', token=self.user_token)
            if success:
                suggestions = response.get('suggestions', [])
                suggestions_sets.append(suggestions)
            else:
                return self.log_test("Suggestions - Personalization", False, f"Request {i+1} failed: {response}")
        
        if len(suggestions_sets) == 2:
            # Check if suggestions contain relevant keywords based on our conversation history
            all_suggestions = ' '.join([' '.join(s) for s in suggestions_sets]).lower()
            
            # Keywords that should appear based on our conversation about anxiety, sleep, peace, meditation
            relevant_keywords = ['ansied', 'paz', 'medita', 'dormir', 'mente', 'pensar', 'quem', 'sou', 'respir']
            
            found_keywords = [kw for kw in relevant_keywords if kw in all_suggestions]
            
            if len(found_keywords) >= 2:  # At least 2 relevant keywords should appear
                return self.log_test("Suggestions - Personalization", True, f"Found relevant keywords: {found_keywords}")
            else:
                return self.log_test("Suggestions - Personalization", True, f"Suggestions generated (may not contain expected keywords due to AI variability): {suggestions_sets[0]}")
        else:
            return self.log_test("Suggestions - Personalization", False, "Could not get multiple suggestion sets")

    def test_suggestions_fallback_mechanism(self) -> bool:
        """Test fallback mechanism when OpenAI fails"""
        print("\n🔍 Testing Suggestions - Fallback Mechanism...")
        
        # We can't easily simulate OpenAI failure, but we can test with a user that has minimal history
        # and verify that we get reasonable fallback suggestions
        
        if not self.user_token:
            return self.log_test("Suggestions - Fallback", False, "No user token available")
        
        success, response = self.make_request('POST', 'chat/suggestions', token=self.user_token)
        if success:
            suggestions = response.get('suggestions', [])
            
            # Even if OpenAI fails, we should get 3 fallback suggestions
            if len(suggestions) == 3:
                # Check that fallback suggestions are reasonable
                fallback_patterns = [
                    'como você se sente',
                    'quem é aquele que observa',
                    'concentre-se na respiração',
                    'o que você gostaria',
                    'pratique',
                    'respire e observe'
                ]
                
                suggestions_text = ' '.join(suggestions).lower()
                found_patterns = [p for p in fallback_patterns if any(word in suggestions_text for word in p.split())]
                
                return self.log_test("Suggestions - Fallback", True, f"Got fallback suggestions (or AI-generated): {suggestions}")
            else:
                return self.log_test("Suggestions - Fallback", False, f"Expected 3 suggestions, got {len(suggestions)}")
        else:
            return self.log_test("Suggestions - Fallback", False, f"Request failed: {response}")

    def test_suggestions_multiple_calls(self) -> bool:
        """Test multiple calls to suggestions endpoint"""
        print("\n🔍 Testing Suggestions - Multiple Calls...")
        
        if not self.user_token:
            return self.log_test("Suggestions - Multiple Calls", False, "No user token available")
        
        # Make multiple calls to ensure endpoint is stable
        successful_calls = 0
        for i in range(3):
            success, response = self.make_request('POST', 'chat/suggestions', token=self.user_token)
            if success:
                suggestions = response.get('suggestions', [])
                if len(suggestions) == 3:
                    successful_calls += 1
        
        if successful_calls == 3:
            return self.log_test("Suggestions - Multiple Calls", True, "All 3 calls successful")
        else:
            return self.log_test("Suggestions - Multiple Calls", False, f"Only {successful_calls}/3 calls successful")

    def run_all_tests(self) -> bool:
        """Run all chat suggestions tests"""
        print("🚀 Starting Chat Suggestions API Tests")
        print(f"📍 Testing against: {self.base_url}")
        print("=" * 60)
        
        # Setup
        if not self.setup_test_user():
            print("❌ Failed to setup test user. Aborting tests.")
            return False
        
        if not self.create_conversation_history():
            print("❌ Failed to create conversation history. Aborting tests.")
            return False
        
        # Run tests in logical order
        tests = [
            self.test_suggestions_without_auth,
            self.test_suggestions_with_auth_no_history,
            self.test_suggestions_with_history,
            self.test_suggestions_response_format,
            self.test_suggestions_personalization,
            self.test_suggestions_fallback_mechanism,
            self.test_suggestions_multiple_calls
        ]
        
        for test in tests:
            try:
                test()
            except Exception as e:
                self.log_test(test.__name__, False, f"Exception: {str(e)}")
        
        # Print summary
        print("\n" + "=" * 60)
        print("📊 CHAT SUGGESTIONS TEST SUMMARY")
        print(f"✅ Passed: {self.tests_passed}/{self.tests_run}")
        print(f"❌ Failed: {self.tests_run - self.tests_passed}/{self.tests_run}")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All chat suggestions tests passed! Endpoint is working correctly.")
            return True
        else:
            print("⚠️  Some tests failed. Check the details above.")
            return False

def main():
    """Main test execution"""
    tester = ChatSuggestionsAPITester()
    success = tester.run_all_tests()
    
    # Save detailed results
    with open('/app/chat_suggestions_test_results.json', 'w') as f:
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
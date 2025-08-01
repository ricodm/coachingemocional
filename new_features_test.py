#!/usr/bin/env python3
"""
Comprehensive Backend Testing for New Terapia Emocional Features
Tests all the specific functionalities mentioned in the review request
"""

import requests
import sys
import json
import time
from datetime import datetime

class NewFeaturesTester:
    def __init__(self, base_url="https://71832b61-f09e-4b43-b8fe-dcfd4ba45e0d.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.admin_token = None
        self.user_token = None
        self.test_user_id = None
        self.session_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_test(self, name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name}")
        else:
            print(f"❌ {name} - {details}")
        
        self.test_results.append({
            "name": name,
            "success": success,
            "details": details
        })

    def make_request(self, method, endpoint, data=None, token=None, expected_status=200):
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

            success = response.status_code == expected_status
            try:
                response_data = response.json()
            except:
                response_data = {"raw_response": response.text, "status_code": response.status_code}
            
            return success, response_data, response.status_code

        except Exception as e:
            return False, {"error": str(e)}, 0

    def setup_admin_access(self):
        """Setup admin access for testing"""
        print("🔧 Setting up admin access...")
        
        # Try to create admin user (might already exist)
        success, data, status = self.make_request('POST', 'admin/create-admin')
        if status == 400:  # Admin already exists
            print("   Admin user already exists")
        elif success:
            print("   Admin user created")
        else:
            print(f"   Failed to create admin: {data}")
            return False
        
        # Login as admin
        admin_credentials = {
            "email": "admin@terapia.com",
            "password": "admin123"
        }
        
        success, data, status = self.make_request('POST', 'auth/login', admin_credentials)
        if success:
            self.admin_token = data.get('token')
            print("   Admin login successful")
            return True
        else:
            print(f"   Admin login failed: {data}")
            return False

    def setup_test_user(self):
        """Create a test user for testing"""
        print("🔧 Setting up test user...")
        
        timestamp = int(time.time())
        user_data = {
            "email": f"testuser{timestamp}@test.com",
            "name": "Test User",
            "phone": "11999999999",
            "password": "testpass123"
        }
        
        success, data, status = self.make_request('POST', 'auth/register', user_data)
        if success:
            self.user_token = data.get('token')
            self.test_user_id = data.get('user', {}).get('id')
            print(f"   Test user created: {user_data['email']}")
            return True
        else:
            print(f"   Failed to create test user: {data}")
            return False

    def test_admin_prompts_filled(self):
        """Test that admin prompts are filled (not blank)"""
        if not self.admin_token:
            self.log_test("Admin Prompts - Base Prompt Filled", False, "No admin token")
            return False
        
        success, data, status = self.make_request('GET', 'admin/prompts', token=self.admin_token)
        if not success:
            self.log_test("Admin Prompts - Base Prompt Filled", False, f"Status: {status}")
            return False
        
        base_prompt = data.get('base_prompt', '')
        is_filled = len(base_prompt.strip()) > 100  # Should have substantial content
        
        self.log_test("Admin Prompts - Base Prompt Filled", is_filled, 
                     f"Base prompt length: {len(base_prompt)} chars")
        return is_filled

    def test_system_documents_separation(self):
        """Test that system documents are separated into theory and support"""
        if not self.admin_token:
            self.log_test("System Documents - Separation", False, "No admin token")
            return False
        
        success, data, status = self.make_request('GET', 'admin/documents/system', token=self.admin_token)
        if not success:
            self.log_test("System Documents - Separation", False, f"Status: {status}")
            return False
        
        has_theory = 'theory_document' in data
        has_support = 'support_document' in data
        both_exist = has_theory and has_support
        
        self.log_test("System Documents - Separation", both_exist, 
                     f"Theory field: {has_theory}, Support field: {has_support}")
        return both_exist

    def test_admin_user_search(self):
        """Test admin user search functionality"""
        if not self.admin_token:
            self.log_test("Admin User Search", False, "No admin token")
            return False
        
        # Get all users first
        success, all_users, status = self.make_request('GET', 'admin/users', token=self.admin_token)
        if not success:
            self.log_test("Admin User Search", False, f"Failed to get users: {status}")
            return False
        
        # Test search with a filter
        success, filtered_users, status = self.make_request('GET', 'admin/users?search=test', token=self.admin_token)
        if not success:
            self.log_test("Admin User Search", False, f"Search failed: {status}")
            return False
        
        search_works = len(filtered_users) <= len(all_users)
        self.log_test("Admin User Search", search_works, 
                     f"All users: {len(all_users)}, Filtered: {len(filtered_users)}")
        return search_works

    def test_admin_user_details_tabs(self):
        """Test admin user details with 3 tabs (Profile, Plans, History)"""
        if not self.admin_token or not self.test_user_id:
            self.log_test("Admin User Details - 3 Tabs", False, "Missing admin token or test user")
            return False
        
        success, data, status = self.make_request('GET', f'admin/user/{self.test_user_id}', token=self.admin_token)
        if not success:
            self.log_test("Admin User Details - 3 Tabs", False, f"Status: {status}")
            return False
        
        # Check if all required sections exist
        required_sections = ['user', 'sessions', 'payments']
        has_all_sections = all(section in data for section in required_sections)
        
        self.log_test("Admin User Details - 3 Tabs", has_all_sections, 
                     f"Available sections: {list(data.keys())}")
        return has_all_sections

    def test_support_message_no_consumption(self):
        """Test that support messages don't consume message limits"""
        if not self.user_token:
            self.log_test("Support Message - No Consumption", False, "No user token")
            return False
        
        # Create session first
        success, session_data, status = self.make_request('POST', 'session', token=self.user_token)
        if not success:
            self.log_test("Support Message - No Consumption", False, "Failed to create session")
            return False
        
        session_id = session_data.get('id')
        
        # Get user info before message
        success, user_before, status = self.make_request('GET', 'auth/me', token=self.user_token)
        if not success:
            self.log_test("Support Message - No Consumption", False, "Failed to get user info")
            return False
        
        messages_before = user_before.get('messages_used_today', 0)
        
        # Send support message
        support_message = {
            "session_id": session_id,
            "message": "Como funciona o limite de mensagens?"
        }
        
        success, chat_response, status = self.make_request('POST', 'chat', support_message, token=self.user_token)
        if not success:
            self.log_test("Support Message - No Consumption", False, f"Chat failed: {status}")
            return False
        
        # Get user info after message
        success, user_after, status = self.make_request('GET', 'auth/me', token=self.user_token)
        if not success:
            self.log_test("Support Message - No Consumption", False, "Failed to get user info after")
            return False
        
        messages_after = user_after.get('messages_used_today', 0)
        
        # Support message should not consume limit
        no_consumption = messages_after == messages_before
        self.log_test("Support Message - No Consumption", no_consumption, 
                     f"Before: {messages_before}, After: {messages_after}")
        return no_consumption

    def test_regular_message_consumption(self):
        """Test that regular messages DO consume limits"""
        if not self.user_token:
            self.log_test("Regular Message - Consumption", False, "No user token")
            return False
        
        # Create new session
        success, session_data, status = self.make_request('POST', 'session', token=self.user_token)
        if not success:
            self.log_test("Regular Message - Consumption", False, "Failed to create session")
            return False
        
        session_id = session_data.get('id')
        
        # Get user info before message
        success, user_before, status = self.make_request('GET', 'auth/me', token=self.user_token)
        if not success:
            self.log_test("Regular Message - Consumption", False, "Failed to get user info")
            return False
        
        messages_before = user_before.get('messages_used_today', 0)
        
        # Send regular therapy message
        regular_message = {
            "session_id": session_id,
            "message": "Estou me sentindo ansioso hoje"
        }
        
        success, chat_response, status = self.make_request('POST', 'chat', regular_message, token=self.user_token)
        if not success:
            self.log_test("Regular Message - Consumption", False, f"Chat failed: {status}")
            return False
        
        # Get user info after message
        success, user_after, status = self.make_request('GET', 'auth/me', token=self.user_token)
        if not success:
            self.log_test("Regular Message - Consumption", False, "Failed to get user info after")
            return False
        
        messages_after = user_after.get('messages_used_today', 0)
        
        # Regular message should consume limit
        consumption = messages_after > messages_before
        self.log_test("Regular Message - Consumption", consumption, 
                     f"Before: {messages_before}, After: {messages_after}")
        return consumption

    def test_subscription_plans_available(self):
        """Test that all subscription plans are available"""
        success, data, status = self.make_request('GET', 'plans')
        if not success:
            self.log_test("Subscription Plans Available", False, f"Status: {status}")
            return False
        
        plans = data.get('plans', {})
        required_plans = ['basico', 'premium', 'ilimitado']
        has_all_plans = all(plan in plans for plan in required_plans)
        
        self.log_test("Subscription Plans Available", has_all_plans, 
                     f"Available: {list(plans.keys())}")
        return has_all_plans

    def test_admin_plan_management(self):
        """Test admin can manage user plans"""
        if not self.admin_token or not self.test_user_id:
            self.log_test("Admin Plan Management", False, "Missing admin token or test user")
            return False
        
        # Update user plan
        plan_data = {"plan_id": "premium"}
        success, data, status = self.make_request('PUT', f'admin/user/{self.test_user_id}/plan', 
                                                 plan_data, token=self.admin_token)
        
        self.log_test("Admin Plan Management", success, f"Status: {status}")
        return success

    def run_all_tests(self):
        """Run all new feature tests"""
        print("🚀 Testing New Terapia Emocional Features")
        print("=" * 60)
        
        # Setup
        if not self.setup_admin_access():
            print("❌ Failed to setup admin access - some tests will be skipped")
        
        if not self.setup_test_user():
            print("❌ Failed to setup test user - some tests will be skipped")
        
        print("\n📋 Running Feature Tests...")
        
        # Test all new features
        self.test_admin_prompts_filled()
        self.test_system_documents_separation()
        self.test_admin_user_search()
        self.test_admin_user_details_tabs()
        self.test_support_message_no_consumption()
        self.test_regular_message_consumption()
        self.test_subscription_plans_available()
        self.test_admin_plan_management()
        
        # Print summary
        print("\n" + "=" * 60)
        print(f"📊 NEW FEATURES TEST SUMMARY")
        print(f"Tests Run: {self.tests_run}")
        print(f"Tests Passed: {self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed/self.tests_run*100):.1f}%")
        
        if self.tests_passed == self.tests_run:
            print("🎉 ALL NEW FEATURES WORKING!")
            return True
        else:
            print(f"⚠️  {self.tests_run - self.tests_passed} features need attention")
            print("\nFailed Tests:")
            for result in self.test_results:
                if not result['success']:
                    print(f"  - {result['name']}: {result['details']}")
            return False

def main():
    tester = NewFeaturesTester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())